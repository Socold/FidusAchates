"""A careful remote operator, and a device between the keyboard and the
machine, on CMU.

`python -m fidus_lab.delivery_eval --cmu <csv> --out <dir>` writes
`metrics.json`. Two questions left open by the input-path study:

1. **A careful remote operator.** A long remote path packs keys into
   near-simultaneous bursts (E11, `input_paths.remote`). An operator who
   knows it can smooth the delivery: spread each packet over a frame
   (`input_paths.spread`) or replay every event at its send-side time through
   a jitter buffer (`input_paths.playout`). For the raw hop and each
   smoothing, I report whether a detector that does not know the typist still
   sees the path (bursts, and the share of exactly repeated gaps that
   spreading creates), whether my own template sees that my typing came
   through it, and how often another person typing through it is accepted as
   me, against the same person typing locally.
2. **A device in the middle.** A microcontroller between my keyboard and the
   machine, emitting a forger's timings (the stolen-template forger of
   `mimicry_eval`), has to report them on its own USB polling grid; my
   keyboard reports on its own. I simulate both grids, 1 ms (1000 Hz) and 8
   ms (125 Hz), with a random phase per repetition and 0.05 ms of
   timestamping jitter, and ask: does the rig's quantisation cost the forger
   acceptance, and can a grid test (E02) tell the rig's grid from my
   keyboard's, from the residues of the intervals on 1 and 8 ms?

The verifier is the scaled-Manhattan detector, its threshold at each
subject's EER point against the published zero-effort impostors, as in
`mimicry_eval`. Seeded, deterministic, standard library only.
"""

from __future__ import annotations

import argparse
import cmath
import json
import math
import os
import random
import statistics
import sys

from .corpus import CmuSample, ScaledManhattan, cmu_columns, load_cmu
from .input_paths import playout, quantize, remote, spread
from .input_paths_eval import _test_windows, _two_sided, aware_detection, burst_share
from .kloak import cmu_events, cmu_from_events
from .kloak_eval import _by_subject
from .metrics import eer_exact
from .mimicry_eval import _accept, manhattan_forgery, threshold_at_eer
from .public_eval import cmu_split

SEED = 20261106
FAR = {"frame_ms": 16.0, "latency_ms": 150.0, "jitter_ms": 40.0}
GRIDS_MS = (1.0, 8.0)
USB_JITTER_MS = 0.05
DETECT_WINDOWS = (1, 5)
N_FORGED = 200


def _intervals(rows: list[CmuSample], columns: list[str]) -> list[float]:
    out = []
    for r in rows:
        ts = [t for t, _, _ in cmu_events(r, columns).events]
        out += [b - a for a, b in zip(ts, ts[1:], strict=False)]
    return out


def repeated_gap_share(rows: list[CmuSample], columns: list[str], tol_ms: float = 0.05) -> float:
    """Share of consecutive event gaps equal to the previous one within
    `tol_ms`: a spread packet lays its events on one even step."""
    gaps = _intervals(rows, columns)
    pairs = list(zip(gaps, gaps[1:], strict=False))
    return sum(abs(a - b) < tol_ms for a, b in pairs) / len(pairs)


def grid_alignment(rows: list[CmuSample], columns: list[str], period_ms: float) -> float:
    """Length of the mean phase vector of the event intervals on a grid of
    `period_ms`: near 1 when every interval is a multiple of it, near 0 when
    the residues are spread out."""
    gaps = _intervals(rows, columns)
    z = sum(cmath.exp(2j * math.pi * g / period_ms) for g in gaps) / len(gaps)
    return abs(z)


def _path(samples: list[CmuSample], columns: list[str], fn) -> tuple[list[CmuSample], list[int]]:
    out, extras = [], []
    for s in samples:
        ev, extra = fn(cmu_events(s, columns).events)
        out.append(cmu_from_events(s.subject, ev, columns))
        extras.append(extra)
    return out, extras


def _blind(clean: list[CmuSample], other: list[CmuSample], columns: list[str], stats) -> dict:
    out = {}
    for k in DETECT_WINDOWS:
        cw, ow = _test_windows(clean, k), _test_windows(other, k)
        out[f"k{k}"] = {name: round(_two_sided(eer_exact([f(w, columns) for w in cw],
                                                         [f(w, columns) for w in ow])), 4)
                        for name, f in stats.items()}
    return out


def impostor_acceptance(clean: list[CmuSample], seen: list[CmuSample]) -> float:
    """Mean share of other people's repetitions, as `seen` delivers them,
    accepted at each subject's EER threshold set on clean data."""
    split = cmu_split(clean)
    by_seen = _by_subject(seen)
    per = []
    for subj, (train, gen, imp) in split.items():
        m = ScaledManhattan.train(train)
        t = threshold_at_eer([m.score(x) for x in gen], [m.score(x) for x in imp])
        others = [x for o, rows in by_seen.items() if o != subj for x in rows[:5]]
        per.append(_accept([m.score(x) for x in others], t))
    return round(statistics.fmean(per), 4)


def careful_remote(clean: list[CmuSample], columns: list[str]) -> dict:
    rng = random.Random(f"{SEED}-remote")
    paths = {
        "raw": lambda ev: remote(ev, rng, **FAR),
        "spread": lambda ev: spread(remote(ev, rng, **FAR)[0], FAR["frame_ms"]),
        "playout_250ms": lambda ev: playout(ev, rng, 250.0, **FAR),
    }
    stats = {"bursts": burst_share, "repeated_gaps": repeated_gap_share}
    out: dict = {"path": FAR, "local_impostor_acceptance": impostor_acceptance(clean, clean)}
    for name, fn in paths.items():
        seen, extras = _path(clean, columns, fn)
        out[name] = {
            "blind_detection": _blind(clean, seen, columns, stats),
            "my_template_notices": aware_detection(clean, seen),
            "impostor_acceptance": impostor_acceptance(clean, seen),
        }
        if name == "playout_250ms":
            n_events = sum(len(cmu_events(s, columns).events) for s in clean)
            out[name]["late_event_share"] = round(sum(extras) / n_events, 4)
        print(f"remote {name} done", file=sys.stderr)
    return out


def _on_grid(samples: list[CmuSample], columns: list[str], period_ms: float,
             rng: random.Random) -> list[CmuSample]:
    def fn(ev):
        return quantize(ev, period_ms, rng.uniform(0, period_ms), USB_JITTER_MS, rng)
    return _path(samples, columns, fn)[0]


def _grid_stats():
    return {f"grid_{g:g}ms": (lambda rows, cols, g=g: grid_alignment(rows, cols, g))
            for g in GRIDS_MS}


def rig(clean: list[CmuSample], columns: list[str]) -> dict:
    out: dict = {}
    for kb in GRIDS_MS:
        rng = random.Random(f"{SEED}-kb-{kb}")
        mine = _on_grid(clean, columns, kb, rng)
        by = _by_subject(mine)
        res: dict = {}
        for name, rig_ms in (("perfect", None), *((f"rig_{g:g}ms", g) for g in GRIDS_MS)):
            accepted, forged_all, real_all = [], [], []
            for subj, (train, gen, imp) in cmu_split(mine).items():
                frng = random.Random(f"{SEED}-forge-{kb}-{name}-{subj}")
                m = ScaledManhattan.train(train)
                t = threshold_at_eer([m.score(x) for x in gen], [m.score(x) for x in imp])
                forged = [manhattan_forgery(m, columns, frng, False) for _ in range(N_FORGED)]
                if rig_ms is not None:
                    forged = _on_grid(forged, columns, rig_ms, frng)
                accepted.append(_accept([m.score(x) for x in forged], t))
                forged_all += [CmuSample(subj, x.features) for x in forged]
                real_all += by[subj][200:]
            entry = {"forgery_acceptance": round(statistics.fmean(accepted), 4)}
            # The grid test: my keyboard's later repetitions against the
            # forgeries, windows of k, per grid. Both sets are 200 per subject.
            entry["grid_detection"] = {}
            for k in DETECT_WINDOWS:
                rw = [real_all[i:i + k] for i in range(0, len(real_all) - k + 1, k)]
                fw = [forged_all[i:i + k] for i in range(0, len(forged_all) - k + 1, k)]
                entry["grid_detection"][f"k{k}"] = {
                    g: round(_two_sided(eer_exact([f(w, columns) for w in rw],
                                                  [f(w, columns) for w in fw])), 4)
                    for g, f in _grid_stats().items()}
            entry["grid_alignment_median"] = {
                g: round(statistics.median(f([x], columns) for x in forged_all[::20]), 3)
                for g, f in _grid_stats().items()}
            res[name] = entry
        res["my_keyboard_alignment_median"] = {
            g: round(statistics.median(f([x], columns) for x in mine[::20]), 3)
            for g, f in _grid_stats().items()}
        out[f"keyboard_{kb:g}ms"] = res
        print(f"keyboard {kb:g} ms done", file=sys.stderr)
    return out


def run(path: str) -> dict:
    clean = load_cmu(path)
    columns = cmu_columns(path)
    return {"corpus": "CMU DSL-StrongPasswordData", "seed": SEED,
            "careful_remote": careful_remote(clean, columns),
            "rig": rig(clean, columns)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.delivery_eval")
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
