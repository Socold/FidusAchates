"""Does kloak hide a typist? Protocols on the CMU keystroke benchmark.

`python -m fidus_lab.kloak_eval --cmu <csv> --out <dir>` writes `metrics.json`.

Every protocol is the Killourhy and Maxion split of `public_eval` (first 200
repetitions of a subject to train, last 200 as genuine, first repetitions of
every other subject as impostors), run on copies of the corpus passed through
`fidus_lab.kloak` at several maximum delays. What changes is what the observer
holds:

- `profiled_clean`: a template built before kloak was switched on; every test
  repetition, genuine and impostor, goes through kloak.
- `aware`: the observer knows kloak is in the path and trains on obfuscated
  repetitions. Training on the subject's clean repetitions passed through the
  public algorithm gives the same thing, so this needs no capture under kloak.
- `aware` over k repetitions: the observer averages each feature over k
  consecutive repetitions before matching, as anyone holding a longer stretch
  of typing does. Training windows slide over the 200 training repetitions;
  genuine windows tile the 200 test ones; each impostor gives 5 windows from
  its first 5k repetitions. k = 1 is the published protocol.

Two readings: verification EER per subject (mean over the 51), and closed-set
identification, the share of genuine test windows whose nearest template is
their own subject's. The detector is the scaled-Manhattan baseline; the
keystroke expert of the engine is run at k = 1 to see what kloak costs my own
user. All draws are seeded; the run is deterministic.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys

from .corpus import CmuSample, ScaledManhattan, cmu_columns, load_cmu
from .experts import KeystrokeExpert, KeystrokeTemplate
from .kloak import cmu_events, obfuscate_corpus, obfuscate_times
from .metrics import eer_exact
from .public_eval import _rep_segment, _summary

DELAYS_MS = (0, 25, 50, 100, 200)
WINDOWS = (1, 5, 10, 20)
SEED = 20261104


def _by_subject(samples: list[CmuSample]) -> dict[str, list[CmuSample]]:
    by: dict[str, list[CmuSample]] = {}
    for s in samples:
        by.setdefault(s.subject, []).append(s)
    return by


def _mean(rows: list[CmuSample]) -> CmuSample:
    return CmuSample(rows[0].subject,
                     [statistics.fmean(c) for c in zip(*[r.features for r in rows], strict=True)])


def windowed(
    train_src: list[CmuSample], test_src: list[CmuSample], k: int,
    n_train: int = 200, n_impostor: int = 5,
) -> dict[str, tuple[list[CmuSample], list[CmuSample], list[CmuSample]]]:
    """{subject: (training windows, genuine windows, impostor windows)}. The
    two sources are the same corpus seen by the observer at training time and
    at test time (clean or obfuscated), row for row."""
    tr, te = _by_subject(train_src), _by_subject(test_src)
    out = {}
    for subj in tr:
        train = tr[subj][:n_train]
        gen = te[subj][n_train:]
        out[subj] = (
            [_mean(train[i:i + k]) for i in range(len(train) - k + 1)],
            [_mean(gen[i:i + k]) for i in range(0, len(gen) - k + 1, k)],
            [_mean(te[o][j * k:(j + 1) * k])
             for o in te if o != subj for j in range(n_impostor)],
        )
    return out


def verify_and_identify(splits: dict) -> dict:
    """Mean verification EER and closed-set rank-1 identification."""
    models = {s: ScaledManhattan.train(tr) for s, (tr, _, _) in splits.items()}
    per = {}
    hits = total = 0
    for subj, (_, gen, imp) in splits.items():
        m = models[subj]
        per[subj] = eer_exact([m.score(x) for x in gen], [m.score(x) for x in imp])
        for x in gen:
            best = min(models, key=lambda o, x=x: models[o].score(x))
            hits += best == subj
            total += 1
    eer = _summary(per)
    return {"eer_mean": round(eer.mean, 4), "eer_std": round(eer.std, 4),
            "identification": round(hits / total, 4), "n_genuine_windows": total}


def expert_eer(train_src: list[CmuSample], test_src: list[CmuSample],
               columns: list[str]) -> float:
    """The keystroke expert, one repetition per segment, wide fallback
    reference, as `public_eval.cmu_keystroke_expert`, trained and tested on
    the two given views of the corpus."""
    expert = KeystrokeExpert()
    empty = KeystrokeTemplate()
    per = {}
    for subj, (train, gen, imp) in windowed(train_src, test_src, 1).items():
        tpl = KeystrokeTemplate.fit([_rep_segment(s, columns, False) for s in train])

        def score(s: CmuSample, tpl: KeystrokeTemplate = tpl) -> float:
            ev, _ = expert.evidence(_rep_segment(s, columns, False), tpl, empty)
            return sum(ev.values())

        per[subj] = eer_exact([score(s) for s in gen], [score(s) for s in imp])
    return round(_summary(per).mean, 4)


def lag(samples: list[CmuSample], columns: list[str], max_delay_ms: int) -> dict:
    """Delay kloak adds to each event while these repetitions are typed."""
    rng = random.Random(SEED)
    delays = []
    for s in samples:
        times = [t for t, _, _ in cmu_events(s, columns).events]
        released, _ = obfuscate_times(times, max_delay_ms, rng)
        delays += [r - t for r, t in zip(released, times, strict=True)]
    delays.sort()
    return {"mean_ms": round(statistics.fmean(delays), 1),
            "p95_ms": round(delays[int(0.95 * (len(delays) - 1))], 1),
            "max_ms": round(delays[-1], 1)}


def noise(clean: list[CmuSample], obf: list[CmuSample], columns: list[str]) -> dict:
    """What kloak does to each family of columns over the whole corpus: the
    shift of the mean, the standard deviation of the per-repetition change,
    and the spread of the clean values for scale (all in ms)."""
    out = {}
    for fam in ("H.", "DD.", "UD."):
        idx = [i for i, c in enumerate(columns) if c.startswith(fam)]
        diffs = [(o.features[i] - c.features[i]) * 1000
                 for c, o in zip(clean, obf, strict=True) for i in idx]
        per_col_sd = [statistics.pstdev([c.features[i] * 1000 for c in clean]) for i in idx]
        out[fam.rstrip(".")] = {
            "mean_shift_ms": round(statistics.fmean(diffs), 2),
            "added_sd_ms": round(statistics.pstdev(diffs), 2),
            "clean_between_rep_sd_ms": round(statistics.fmean(per_col_sd), 2),
        }
    return out


def run(path: str, expert: bool = True) -> dict:
    clean = load_cmu(path)
    columns = cmu_columns(path)
    result: dict = {
        "corpus": "CMU DSL-StrongPasswordData, 51 subjects x 400 repetitions",
        "model": "kloak.c schedule: uniform integer delay in [max(prev_release - now, 0), D], "
                 "millisecond clock, order preserved",
        "seed": SEED,
        "delays": {},
    }
    for d in DELAYS_MS:
        obf = obfuscate_corpus(clean, columns, d, SEED + d)
        row: dict = {
            "profiled_clean": verify_and_identify(windowed(clean, obf, 1)),
            "aware": {f"k{k}": verify_and_identify(windowed(obf, obf, k)) for k in WINDOWS},
        }
        if d == 0:
            row["clean_reference"] = {f"k{k}": verify_and_identify(windowed(clean, clean, k))
                                      for k in WINDOWS}
        else:
            row["lag"] = lag(clean, columns, d)
            row["noise"] = noise(clean, obf, columns)
        if expert:
            row["keystroke_expert"] = {
                "profiled_clean": expert_eer(clean, obf, columns),
                "aware": expert_eer(obf, obf, columns),
            }
        result["delays"][f"{d}ms"] = row
        print(f"D={d} ms done", file=sys.stderr)
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.kloak_eval")
    ap.add_argument("--cmu", required=True, help="DSL-StrongPasswordData.csv")
    ap.add_argument("--out", help="directory for metrics.json")
    ap.add_argument("--no-expert", action="store_true", help="skip the keystroke expert")
    args = ap.parse_args(argv)
    result = run(args.cmu, expert=not args.no_expert)
    text = json.dumps(result, indent=2)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "metrics.json"), "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
