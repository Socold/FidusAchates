"""Whether a forgery keeps a typist's texture over a session, on CMU.

`python -m fidus_lab.session_eval --cmu <csv> --out <dir>` writes
`metrics.json`.

`mimicry_eval` scores forged attempts one at a time and finds that a stolen
or observed template passes most of them. Its first session check read only
the total typing time and barely separated anything. This one reads the
structure between keys.

A repetition is the vector of log holds and log down-down latencies (21
values on the CMU password). A person's repetitions are correlated across
keys: a slow attempt is slow almost everywhere, and some pairs move
together because the same finger or hand is involved. A forger who draws
each key independently gets every marginal right and this structure wrong.

Per victim, I fit a Gaussian on the first 200 repetitions twice: with its
full covariance (shrunk towards the diagonal) and with the diagonal only.
The texture score of one repetition is the log-likelihood ratio full minus
diagonal: positive when the attempt has the victim's correlations. Over a
window of k consecutive attempts I report:

- `texture`: the mean texture score.
- `speed_autocorr`: the lag-1 autocorrelation of the attempts' projection on
  the victim's first principal component (overall speed). A sitting drifts;
  independent draws do not.

Genuine windows come from repetitions 300 to 399. The forgers:

- `laplace_independent`: the `mimicry_eval` template forger (scaled
  Manhattan template, independent Laplace noise per feature).
- `gauss_diagonal`: independent log-normal draws from the victim's own
  marginals, the fairest independent forger.
- `gauss_full`: the stolen full covariance, attempts independent.
- `gauss_full_drift`: the same, with the attempts following an AR(1) whose
  coefficient is the victim's own speed autocorrelation in training.
- `observed_n`: a full-covariance forger estimated from n of the victim's
  repetitions 200 to 299 (what a page timing keystrokes collects), with the
  shrinkage the estimate needs at that n.

Each result is a detection EER, genuine windows against forged windows, with
lower meaning the forgery is harder to tell apart (0.5 is chance). Seeded,
deterministic, standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys

from .corpus import CmuSample, ScaledManhattan, cmu_columns, load_cmu
from .kloak_eval import _by_subject
from .metrics import eer_exact
from .mimicry_eval import lag1_autocorrelation, manhattan_forgery

SEED = 20261105
WINDOWS = (1, 5, 10, 20, 50)
OBSERVED = (5, 20, 50)
TRAIN, OBSERVE, GENUINE = slice(0, 200), slice(200, 300), slice(300, 400)


# --- small dense linear algebra --------------------------------------------


def cholesky(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    low = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = a[i][j] - sum(low[i][k] * low[j][k] for k in range(j))
            if i == j:
                if s <= 0:
                    raise ValueError("matrix is not positive definite")
                low[i][i] = math.sqrt(s)
            else:
                low[i][j] = s / low[j][j]
    return low


def _solve_lower(low: list[list[float]], b: list[float]) -> list[float]:
    y = []
    for i, row in enumerate(low):
        y.append((b[i] - sum(row[k] * y[k] for k in range(i))) / row[i])
    return y


def first_component(a: list[list[float]], iters: int = 200) -> list[float]:
    """Leading eigenvector by power iteration, sign fixed so its sum is
    positive (slower everywhere = larger projection)."""
    n = len(a)
    v = [1.0 / math.sqrt(n)] * n
    for _ in range(iters):
        w = [sum(a[i][j] * v[j] for j in range(n)) for i in range(n)]
        norm = math.sqrt(sum(x * x for x in w)) or 1.0
        v = [x / norm for x in w]
    return v if sum(v) >= 0 else [-x for x in v]


# --- the texture model -------------------------------------------------------


def log_vector(s: CmuSample, columns: list[str]) -> list[float]:
    """Log holds and log down-down latencies, in column order. UD is left out:
    it is DD minus H, so it carries no structure of its own."""
    return [math.log(max(v, 1e-3)) for c, v in zip(columns, s.features, strict=True)
            if c.startswith(("H.", "DD."))]


def shrinkage_for(n: int, d: int) -> float:
    """Weight moved from the sample covariance to its diagonal: light with
    plenty of data, total when the sample cannot estimate the covariance."""
    return min(1.0, max(0.1, d / n))


class Texture:
    """A Gaussian on log timings, full covariance and diagonal side by side."""

    def __init__(self, rows: list[list[float]], shrink: float | None = None) -> None:
        n, d = len(rows), len(rows[0])
        self.mean = [statistics.fmean(c) for c in zip(*rows, strict=True)]
        centred = [[x - m for x, m in zip(r, self.mean, strict=True)] for r in rows]
        cov = [[sum(r[i] * r[j] for r in centred) / max(n - 1, 1) for j in range(d)]
               for i in range(d)]
        lam = shrinkage_for(n, d) if shrink is None else shrink
        self.var = [max(cov[i][i], 1e-6) for i in range(d)]
        self.cov = [[(1 - lam) * cov[i][j] if i != j else self.var[i] for j in range(d)]
                    for i in range(d)]
        self.low = cholesky(self.cov)
        self.logdet = 2 * sum(math.log(self.low[i][i]) for i in range(d))
        self.pc1 = first_component(self.cov)
        speeds = [self.speed(r) for r in rows]
        self.speed_autocorr = lag1_autocorrelation(speeds) if n > 2 else 0.0

    def texture(self, x: list[float]) -> float:
        """log N(x; mean, cov) - log N(x; mean, diag)."""
        diff = [a - m for a, m in zip(x, self.mean, strict=True)]
        y = _solve_lower(self.low, diff)
        full = -0.5 * (sum(v * v for v in y) + self.logdet)
        diag = -0.5 * sum(v * v / s + math.log(s) for v, s in zip(diff, self.var, strict=True))
        return full - diag

    def speed(self, x: list[float]) -> float:
        return sum((a - m) * w for a, m, w in zip(x, self.mean, self.pc1, strict=True))

    def draw(self, rng: random.Random, n: int, phi: float = 0.0,
             diagonal: bool = False) -> list[list[float]]:
        """n attempts; with phi > 0 they follow x_t = phi x_{t-1} + noise,
        stationary on the same covariance."""
        d = len(self.mean)
        out, prev = [], [0.0] * d
        scale = math.sqrt(max(1 - phi * phi, 0.0))
        for t in range(n):
            z = [rng.gauss(0, 1) for _ in range(d)]
            if diagonal:
                e = [math.sqrt(s) * v for s, v in zip(self.var, z, strict=True)]
            else:
                e = [sum(self.low[i][k] * z[k] for k in range(i + 1)) for i in range(d)]
            cur = e if t == 0 else [phi * p + scale * v for p, v in zip(prev, e, strict=True)]
            prev = cur
            out.append([m + v for m, v in zip(self.mean, cur, strict=True)])
        return out


# --- evaluation --------------------------------------------------------------


def window_stats(model: Texture, attempts: list[list[float]], k: int) -> dict[str, list[float]]:
    """Suspicion per window (higher = less like the victim), so that
    `eer_exact` reads genuine low against forged high."""
    out: dict[str, list[float]] = {"texture": [], "speed_autocorr": []}
    for i in range(0, len(attempts) - k + 1, k):
        w = attempts[i:i + k]
        out["texture"].append(-statistics.fmean(model.texture(x) for x in w))
        if k >= 5:
            out["speed_autocorr"].append(
                -lag1_autocorrelation([model.speed(x) for x in w]))
    return out


def run(path: str) -> dict:
    clean = load_cmu(path)
    columns = cmu_columns(path)
    by = _by_subject(clean)
    gen: dict[int, dict[str, list[float]]] = {}
    forged: dict[str, dict[int, dict[str, list[float]]]] = {}
    fitted_phi = []

    def add(into: dict, k: int, stats: dict[str, list[float]]) -> None:
        for name, v in stats.items():
            into.setdefault(k, {}).setdefault(name, []).extend(v)

    for subj, rows in by.items():
        rng = random.Random(f"{SEED}-{subj}")
        vec = [log_vector(r, columns) for r in rows]
        model = Texture(vec[TRAIN])
        fitted_phi.append(model.speed_autocorr)
        genuine = vec[GENUINE]
        n = len(genuine)
        manhattan = ScaledManhattan.train(rows[TRAIN])
        attempts = {
            "laplace_independent": [
                log_vector(manhattan_forgery(manhattan, columns, rng, False), columns)
                for _ in range(n)],
            "gauss_diagonal": model.draw(rng, n, diagonal=True),
            "gauss_full": model.draw(rng, n),
            "gauss_full_drift": model.draw(rng, n, phi=max(model.speed_autocorr, 0.0)),
        }
        pool = vec[OBSERVE]
        for m in OBSERVED:
            est = Texture(rng.sample(pool, m))
            attempts[f"observed_{m}"] = est.draw(rng, n)
        for k in WINDOWS:
            add(gen, k, window_stats(model, genuine, k))
            for name, xs in attempts.items():
                add(forged.setdefault(name, {}), k, window_stats(model, xs, k))
        print(f"{subj} done", file=sys.stderr)

    res: dict = {"corpus": "CMU DSL-StrongPasswordData", "seed": SEED,
                 "victims": len(by), "dimensions": len(log_vector(clean[0], columns)),
                 "training_speed_autocorr_median": round(statistics.median(fitted_phi), 3),
                 "eer": {}}
    for name, per_k in forged.items():
        res["eer"][name] = {
            f"k{k}": {stat: round(eer_exact(gen[k][stat], v), 4)
                      for stat, v in per_k[k].items() if v}
            for k in WINDOWS}
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.session_eval")
    ap.add_argument("--cmu", required=True)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    text = json.dumps(run(args.cmu), indent=2)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "metrics.json"), "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
