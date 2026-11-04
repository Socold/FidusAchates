"""Hiding a typist for real, being seen hiding, and a remote hand, on CMU.

`python -m fidus_lab.input_paths_eval --cmu <csv> --out <dir>` writes
`metrics.json`. Three questions, all on the CMU benchmark and the protocols of
`kloak_eval`:

1. Can kloak be seen? A detector that does not know the typist looks at one
   window of k repetitions and decides "kloak or not", from the share of very
   short holds or from the spread of the holds. A detector that knows the
   typist (my own case) uses the scaled-Manhattan distance to the clean
   template. Detection EER: clean windows against obfuscated ones.
2. Does a buffer that re-times keys hide the typist? `input_paths.cadence`
   (fixed clock) and `input_paths.foreign` (another person's rhythm), against
   a kloak-aware observer averaging k repetitions, with the lag they cost and
   the share of keys that leak through because the typist was slower. The
   engine's attribution channel is run on each repetition to see whether it
   calls the output automation.
3. What a remote-desktop hop does to the timing the recorder sees
   (`input_paths.remote`): can it be detected (signal E11), and does it hide
   the typist?

Everything is seeded and deterministic.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys

from .attribution import ActorLabel, attribute
from .corpus import CmuSample, ScaledManhattan, cmu_columns, load_cmu
from .input_paths import cadence, foreign, lag_ms, remote
from .kloak import cmu_events, cmu_from_events, obfuscate_corpus
from .kloak_eval import _by_subject, verify_and_identify, windowed
from .metrics import eer_exact
from .public_eval import _rep_segment, _summary
from .registry import SanctionRegistry

SEED = 20261104
WINDOWS = (1, 5, 10, 20)
DETECT_WINDOWS = (1, 5)
SHORT_HOLD_MS = 30.0
BURST_GAP_MS = 1.0
REMOTE = {
    "lan": {"frame_ms": 16.0, "latency_ms": 2.0, "jitter_ms": 1.0},
    "wan": {"frame_ms": 16.0, "latency_ms": 40.0, "jitter_ms": 10.0},
    "far": {"frame_ms": 16.0, "latency_ms": 150.0, "jitter_ms": 40.0},
}


# --- per-window statistics a detector can compute without knowing the typist


def _holds(rows: list[CmuSample], columns: list[str]) -> list[float]:
    idx = [i for i, c in enumerate(columns) if c.startswith("H.")]
    return [r.features[i] * 1000 for r in rows for i in idx]


def short_hold_share(rows: list[CmuSample], columns: list[str]) -> float:
    h = _holds(rows, columns)
    return sum(x < SHORT_HOLD_MS for x in h) / len(h)


def hold_spread(rows: list[CmuSample], columns: list[str]) -> float:
    return statistics.pstdev(_holds(rows, columns))


def burst_share(rows: list[CmuSample], columns: list[str]) -> float:
    """Share of consecutive key events less than 1 ms apart."""
    hit = tot = 0
    for r in rows:
        ts = [t for t, _, _ in cmu_events(r, columns).events]
        for a, b in zip(ts, ts[1:], strict=False):
            hit += (b - a) < BURST_GAP_MS
            tot += 1
    return hit / tot


STATS = {"short_holds": short_hold_share, "hold_spread": hold_spread, "bursts": burst_share}


def _test_windows(samples: list[CmuSample], k: int, n_train: int = 200) -> list[list[CmuSample]]:
    out = []
    for rows in _by_subject(samples).values():
        test = rows[n_train:]
        out += [test[i:i + k] for i in range(0, len(test) - k + 1, k)]
    return out


def _two_sided(e: float) -> float:
    """A statistic that moves the wrong way (constant holds have a smaller
    spread, not a larger one) separates just as well: read it both ways."""
    return min(e, 1.0 - e)


def blind_detection(clean: list[CmuSample], other: list[CmuSample], columns: list[str]) -> dict:
    """EER of telling clean windows from transformed ones, per statistic,
    read in whichever direction the statistic moves."""
    out = {}
    for k in DETECT_WINDOWS:
        cw, ow = _test_windows(clean, k), _test_windows(other, k)
        out[f"k{k}"] = {name: round(_two_sided(eer_exact([f(w, columns) for w in cw],
                                                         [f(w, columns) for w in ow])), 4)
                        for name, f in STATS.items()}
    return out


def aware_detection(clean: list[CmuSample], other: list[CmuSample], n_train: int = 200) -> float:
    """Mean over subjects of the EER between the subject's clean test
    repetitions and the same repetitions transformed, scored against the
    subject's clean template: does my own model notice the path changed?"""
    c, o = _by_subject(clean), _by_subject(other)
    per = {}
    for s in c:
        m = ScaledManhattan.train(c[s][:n_train])
        per[s] = eer_exact([m.score(x) for x in c[s][n_train:]],
                           [m.score(x) for x in o[s][n_train:]])
    return round(_summary(per).mean, 4)


def automation_share(samples: list[CmuSample], columns: list[str]) -> float:
    """Share of repetitions the attribution channel labels automation."""
    reg = SanctionRegistry()
    n = 0
    for s in samples:
        lab = attribute(_rep_segment(s, columns, False), reg).label
        n += lab in (ActorLabel.AUTOMATION_SANCTIONED, ActorLabel.AUTOMATION_UNSANCTIONED)
    return round(n / len(samples), 4)


# --- transformed corpora


def transformed(samples: list[CmuSample], columns: list[str], make) -> tuple[list[CmuSample], dict]:
    """Apply a path built by `make(rng)` to every repetition; returns the new
    corpus and the lag and leak figures."""
    rng = random.Random(SEED)
    out, lags, extras = [], [], []
    for s in samples:
        before = cmu_events(s, columns).events
        after, extra = make(rng)(before)
        # The lag is read on the raw events: a rebuilt repetition starts at 0
        # again and would hide the delay of its first key.
        out.append(cmu_from_events(s.subject, after, columns))
        lags += lag_ms(before, after)
        extras.append(extra)
    lags.sort()
    info = {"lag_mean_ms": round(statistics.fmean(lags), 1),
            "lag_p95_ms": round(lags[int(0.95 * (len(lags) - 1))], 1),
            "lag_max_ms": round(lags[-1], 1)}
    return out, {"info": info, "extras": extras}


def identity(samples: list[CmuSample]) -> dict:
    return {f"k{k}": verify_and_identify(windowed(samples, samples, k)) for k in WINDOWS}


def _donor(samples: list[CmuSample], columns: list[str], which: str) -> str:
    dd = [i for i, c in enumerate(columns) if c.startswith("DD.")]
    speed = {s: statistics.fmean(r.features[i] for r in rows for i in dd)
             for s, rows in _by_subject(samples).items()}
    ranked = sorted(speed, key=speed.get)
    return ranked[-1] if which == "slowest" else ranked[len(ranked) // 2]


def _cadence_path(period_ms: float):
    def make(rng: random.Random):
        return lambda ev: cadence(ev, period_ms, 90.0)
    return make


def _foreign_path(pool: list):
    def make(rng: random.Random):
        donor = rng.choice(pool)
        return lambda ev: foreign(ev, donor)
    return make


def _remote_path(cfg: dict):
    def make(rng: random.Random):
        return lambda ev: remote(ev, rng, **cfg)
    return make


def run(path: str) -> dict:
    clean = load_cmu(path)
    columns = cmu_columns(path)
    n_keys = sum(c.startswith("H.") for c in columns)
    res: dict = {"corpus": "CMU DSL-StrongPasswordData", "seed": SEED,
                 "short_hold_ms": SHORT_HOLD_MS, "burst_gap_ms": BURST_GAP_MS,
                 "clean": {"automation_share": automation_share(clean, columns)}}

    # 1. Can kloak be seen?
    res["kloak_detection"] = {}
    for d in (25, 50, 100, 200):
        obf = obfuscate_corpus(clean, columns, d, SEED + d)
        res["kloak_detection"][f"{d}ms"] = {
            "blind": blind_detection(clean, obf, columns),
            "aware_of_typist": aware_detection(clean, obf),
            "automation_share": automation_share(obf, columns),
        }
        print(f"kloak {d} ms done", file=sys.stderr)

    # 2. Buffers that re-time the keys.
    res["buffers"] = {}
    configs = {f"cadence_{p}ms": _cadence_path(p) for p in (150, 250, 400)}
    by = _by_subject(clean)
    for which in ("median", "slowest"):
        donor = _donor(clean, columns, which)
        pool = [cmu_events(r, columns).events for r in by[donor]]
        configs[f"foreign_{which}_donor"] = _foreign_path(pool)
    for name, make in configs.items():
        new, meta = transformed(clean, columns, make)
        leak = sum(meta["extras"]) / (len(clean) * (n_keys - 1))
        res["buffers"][name] = {
            **meta["info"], "leak_share": round(leak, 4),
            "identity_aware": identity(new),
            "automation_share": automation_share(new, columns),
            "blind_detection": blind_detection(clean, new, columns),
        }
        print(f"{name} done", file=sys.stderr)

    # 3. Remote hand.
    res["remote"] = {}
    for name, cfg in REMOTE.items():
        new, meta = transformed(clean, columns, _remote_path(cfg))
        res["remote"][name] = {
            **cfg, **meta["info"],
            "events_per_packet": round(len(clean) * 2 * n_keys / sum(meta["extras"]), 2),
            "blind_detection": blind_detection(clean, new, columns),
            "aware_of_typist": aware_detection(clean, new),
            "identity_aware": identity(new),
            "identity_profiled_clean": verify_and_identify(windowed(clean, new, 1)),
        }
        print(f"remote {name} done", file=sys.stderr)
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.input_paths_eval")
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
