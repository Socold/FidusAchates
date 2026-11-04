"""What a stolen or observed typing rhythm is worth to an impostor, on CMU.

`python -m fidus_lab.mimicry_eval --cmu <csv> --out <dir>` writes
`metrics.json`.

For each subject (the victim), the verifier is fitted on the first 200
repetitions and its threshold is set where false accepts equal false rejects
against the published zero-effort impostors (the subject's EER point). Then
200 forged attempts are scored against that threshold, and I report the share
accepted. The forgers:

- `zero_effort`: the other subjects' own typing (the published impostors).
- `template_exact`: replays the stolen template's centre every time.
- `template_sampled`: draws each attempt from the stolen template (scaled
  Manhattan: the mean plus Laplace noise of the template's own mean absolute
  deviation; keystroke expert: each hold and latency from the template's
  log-normal for its class).
- `observed_n`: never saw the template, but captured n of the victim's
  repetitions (a page measuring keystrokes) and builds the same kind of
  template from them. Optionally the victim was behind kloak at 100 ms when
  they were captured: a naive forger copies the inflated spread, a
  kloak-aware one (`observed_kloak_deflated_n`) keeps the means, which kloak
  leaves in place, and removes kloak's known variance D^2 / 6 from the spread.
  Its attempts are scaled-Manhattan forgeries, scored by both verifiers.

For the sampled forgeries I also report the share the attribution channel
labels automation: a forgery must look human as well as look like the victim.

Session consistency: a forger who draws every attempt independently from the
template is right on average and wrong in its texture. A person drifts from
one repetition to the next (warming up, tiring), so consecutive repetitions
are correlated; independent draws are not. `session_consistency` reads two
statistics of the total typing time over windows of k consecutive
repetitions, genuine against forged, as detection EERs: its lag-1
autocorrelation, and its coefficient of variation (a real window comes from
one sitting, the template mixes several).

The keystroke expert is the engine's (one repetition per segment, wide
fallback reference); the scaled-Manhattan detector is the CMU baseline. The
observed repetitions are drawn from the victim's genuine test half, and the
attempts are scored against the same threshold; the attempts themselves are
always synthetic. Seeded, deterministic.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys

from .attribution import ActorLabel, attribute
from .corpus import (
    CmuSample,
    ScaledManhattan,
    _cmu_key_class,
    cmu_columns,
    cmu_digraph_classes,
    cmu_keys,
    load_cmu,
)
from .experts import KeystrokeExpert, KeystrokeTemplate
from .kloak import obfuscate_corpus
from .kloak_eval import _by_subject
from .public_eval import _rep_segment, cmu_split
from .registry import SanctionRegistry
from .stats import LogNormalMixture
from .trace import has_digraph

SEED = 20261104
N_ATTEMPTS = 200
OBSERVED = (5, 20, 50)


def threshold_at_eer(genuine: list[float], impostor: list[float]) -> float:
    """The threshold `eer_exact` reads its EER at: a score below it is
    accepted."""
    g, i = sorted(genuine), sorted(impostor)
    ng, ni = len(g), len(i)
    best_gap, best_t = 2.0, max(g[-1], i[-1]) + 1.0
    gi = ii = 0
    for t in sorted(set(g) | set(i)) + [max(g[-1], i[-1]) + 1.0]:
        while gi < ng and g[gi] < t:
            gi += 1
        while ii < ni and i[ii] < t:
            ii += 1
        gap = abs(ii / ni - (ng - gi) / ng)
        if gap < best_gap:
            best_gap, best_t = gap, t
    return best_t


def _accept(scores: list[float], t: float) -> float:
    return sum(s < t for s in scores) / len(scores)


def _features(subject: str, holds: list[float], dds: list[float], columns: list[str]) -> CmuSample:
    """H (s), DD (s) per key and pair, UD derived, in column order."""
    keys = cmu_keys(columns)
    vals: dict[str, float] = {}
    for i, name in enumerate(keys):
        vals[f"H.{name}"] = holds[i]
        if i + 1 < len(keys):
            vals[f"DD.{name}.{keys[i + 1]}"] = dds[i]
            vals[f"UD.{name}.{keys[i + 1]}"] = dds[i] - holds[i]
    return CmuSample(subject, [vals[c] for c in columns])


def _laplace(rng: random.Random, b: float) -> float:
    u = rng.random() - 0.5
    return -b * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))


def manhattan_forgery(model: ScaledManhattan, columns: list[str], rng: random.Random,
                      exact: bool) -> CmuSample:
    keys = cmu_keys(columns)
    pos = {c: i for i, c in enumerate(columns)}

    def draw(col: str, floor: float) -> float:
        m = model.mean[pos[col]]
        return m if exact else max(m + _laplace(rng, model.mad[pos[col]]), floor)

    holds = [draw(f"H.{k}", 0.005) for k in keys]
    dds = [draw(f"DD.{a}.{b}", 0.01) for a, b in zip(keys, keys[1:], strict=False)]
    return _features("forger", holds, dds, columns)


def deflate(est: ScaledManhattan, columns: list[str], max_delay_ms: float) -> ScaledManhattan:
    """Remove kloak's variance from a template estimated through kloak. H and
    DD each carry the difference of two uniform delays (variance D^2 / 6);
    the mean absolute deviation is turned into a variance as for a Laplace law
    (var = 2 b^2), reduced, floored at a fifth of the observed spread, and
    turned back. UD is rebuilt from H and DD by the forger anyway."""
    noise = (max_delay_ms / 1000.0) ** 2 / 6.0
    mad = []
    for c, b in zip(columns, est.mad, strict=True):
        if c.startswith(("H.", "DD.")):
            var = max(2 * b * b - noise, 2 * (0.2 * b) ** 2)
            b = math.sqrt(var / 2)
        mad.append(b)
    return ScaledManhattan(mean=list(est.mean), mad=mad)


def _automation(samples: list[CmuSample], columns: list[str]) -> float:
    reg = SanctionRegistry()
    bad = (ActorLabel.AUTOMATION_SANCTIONED, ActorLabel.AUTOMATION_UNSANCTIONED)
    return sum(attribute(_rep_segment(s, columns, False), reg).label in bad
               for s in samples) / len(samples)


def _sample(dist, rng: random.Random) -> float:
    if isinstance(dist, LogNormalMixture):
        j = 0 if rng.random() < dist.weights[0] else 1
        return math.exp(rng.gauss(dist.mus[j], dist.sigmas[j]))
    return math.exp(rng.gauss(dist.mu, dist.sigma))


def expert_forgery(tpl: KeystrokeTemplate, columns: list[str], rng: random.Random) -> CmuSample:
    """Each hold from the template's class, each classed latency from its
    digraph class; a pair the template has no class for gets the median of
    the class medians, which the expert does not score anyway."""
    keys = cmu_keys(columns)
    classes = cmu_digraph_classes(columns)
    fallback_dd = statistics.median(math.exp(d.mu) for d in tpl.digraph.values()) \
        if tpl.digraph else 200_000.0
    holds = []
    for k in keys:
        d = tpl.hold.get(int(_cmu_key_class(k)))
        holds.append((_sample(d, rng) if d else 90_000.0) / 1e6)
    dds = []
    for c in classes:
        d = tpl.digraph.get(c) if has_digraph(c) else None
        dds.append((_sample(d, rng) if d else fallback_dd) / 1e6)
    return _features("forger", holds, dds, columns)


def lag1_autocorrelation(xs: list[float]) -> float:
    m = statistics.fmean(xs)
    den = sum((x - m) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((a - m) * (b - m) for a, b in zip(xs, xs[1:], strict=False)) / den


def _total_time(s: CmuSample, columns: list[str]) -> float:
    return sum(v for c, v in zip(columns, s.features, strict=True) if c.startswith("DD."))


def session_consistency(clean: list[CmuSample], columns: list[str],
                        ks: tuple[int, ...] = (10, 20, 50)) -> dict:
    """Detection EER of independent forgeries against real consecutive
    repetitions, from the lag-1 autocorrelation of the total time, per
    window length. The forger samples the victim's own template (the
    strongest forger of `run`)."""
    from .metrics import eer_exact

    out = {}
    by = _by_subject(clean)
    for k in ks:
        gen, forged = {"autocorr": [], "cv": []}, {"autocorr": [], "cv": []}
        for subj, rows in by.items():
            rng = random.Random(f"{SEED}-session-{subj}-{k}")
            m = ScaledManhattan.train(rows[:200])
            test = rows[200:]
            for i in range(0, len(test) - k + 1, k):
                real = [_total_time(x, columns) for x in test[i:i + k]]
                fake = [_total_time(manhattan_forgery(m, columns, rng, False), columns)
                        for _ in range(k)]
                for into, w in ((gen, real), (forged, fake)):
                    into["autocorr"].append(lag1_autocorrelation(w))
                    into["cv"].append(statistics.pstdev(w) / statistics.fmean(w))
        out[f"k{k}"] = {}
        for stat in ("autocorr", "cv"):
            e = eer_exact(gen[stat], forged[stat])  # read both ways below
            out[f"k{k}"][stat] = {"eer": round(min(e, 1 - e), 4),
                                  "genuine_median": round(statistics.median(gen[stat]), 3),
                                  "forged_median": round(statistics.median(forged[stat]), 3)}
    return out


def run(path: str) -> dict:
    clean = load_cmu(path)
    columns = cmu_columns(path)
    kloaked = _by_subject(obfuscate_corpus(clean, columns, 100, SEED + 100))
    split = cmu_split(clean)
    by = _by_subject(clean)
    expert, empty = KeystrokeExpert(), KeystrokeTemplate()

    def seg(s: CmuSample):
        return _rep_segment(s, columns, False)

    out: dict[str, dict[str, dict[str, float]]] = {"manhattan": {}, "expert": {}, "attribution": {}}

    def add(det: str, name: str, subj: str, v: float) -> None:
        out[det].setdefault(name, {})[subj] = v

    for subj, (train, gen, imp) in split.items():
        rng = random.Random(f"{SEED}-{subj}")
        deflated: dict[int, list[CmuSample]] = {}
        # Scaled Manhattan.
        m = ScaledManhattan.train(train)
        t = threshold_at_eer([m.score(x) for x in gen], [m.score(x) for x in imp])
        add("manhattan", "zero_effort", subj, _accept([m.score(x) for x in imp], t))
        add("manhattan", "template_exact", subj,
            _accept([m.score(manhattan_forgery(m, columns, rng, True))], t))
        forged = [manhattan_forgery(m, columns, rng, False) for _ in range(N_ATTEMPTS)]
        add("manhattan", "template_sampled", subj, _accept([m.score(x) for x in forged], t))
        add("attribution", "template_sampled_manhattan", subj, _automation(forged, columns))
        for src_name, src in (("observed", by[subj]), ("observed_kloak", kloaked[subj])):
            pool = src[200:]
            for n in OBSERVED:
                seen = rng.sample(pool, n)
                est = ScaledManhattan.train(seen)
                add("manhattan", f"{src_name}_{n}", subj, _accept(
                    [m.score(manhattan_forgery(est, columns, rng, False))
                     for _ in range(N_ATTEMPTS)], t))
                if src_name == "observed_kloak":
                    deflated[n] = [manhattan_forgery(deflate(est, columns, 100), columns,
                                                     rng, False) for _ in range(N_ATTEMPTS)]
                    add("manhattan", f"observed_kloak_deflated_{n}", subj,
                        _accept([m.score(x) for x in deflated[n]], t))
        # Keystroke expert.
        tpl = KeystrokeTemplate.fit([seg(x) for x in train])

        def score(x: CmuSample, tpl: KeystrokeTemplate = tpl) -> float:
            ev, _ = expert.evidence(seg(x), tpl, empty)
            return sum(ev.values())

        te = threshold_at_eer([score(x) for x in gen], [score(x) for x in imp])
        add("expert", "zero_effort", subj, _accept([score(x) for x in imp], te))
        forged_e = [expert_forgery(tpl, columns, rng) for _ in range(N_ATTEMPTS)]
        add("expert", "template_sampled", subj, _accept([score(x) for x in forged_e], te))
        add("attribution", "template_sampled_expert", subj, _automation(forged_e, columns))
        for n, xs in deflated.items():
            add("expert", f"observed_kloak_deflated_{n}", subj, _accept([score(x) for x in xs], te))
        for src_name, src in (("observed", by[subj]), ("observed_kloak", kloaked[subj])):
            pool = src[200:]
            for n in OBSERVED:
                est = KeystrokeTemplate.fit([seg(x) for x in rng.sample(pool, n)])
                add("expert", f"{src_name}_{n}", subj, _accept(
                    [score(expert_forgery(est, columns, rng)) for _ in range(N_ATTEMPTS)], te))
        print(f"{subj} done", file=sys.stderr)

    res: dict = {"corpus": "CMU DSL-StrongPasswordData", "seed": SEED,
                 "attempts_per_victim": N_ATTEMPTS, "acceptance": {},
                 "session_consistency": session_consistency(clean, columns)}
    for det, attacks in out.items():
        res["acceptance"][det] = {
            name: {"mean": round(statistics.fmean(v.values()), 4),
                   "victims_over_half": sum(x > 0.5 for x in v.values()),
                   "n_victims": len(v)}
            for name, v in attacks.items()}
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.mimicry_eval")
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
