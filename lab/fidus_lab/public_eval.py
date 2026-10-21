"""Protocols for the public corpora: CMU keystroke and Balabit mouse.

`python -m fidus_lab.public_eval --cmu <csv> --balabit <dir> --out <dir>`
runs everything and writes `metrics.json`. Nothing here is tuned on the test
data: every parameter is the engine's default or the published protocol's.

CMU follows Killourhy and Maxion (2009): per subject, train on the first 200
repetitions, test on the remaining 200 as genuine and on the first 5
repetitions of every other subject as impostors; the EER is computed per
subject and averaged.

Balabit: per user, the genuine template is fitted on that user's training
sessions; the labelled test sessions of the user (public_labels.csv) are
segmented and scored by the Identity engine with only the pointer expert
enrolled. Impostor data never enters training unless the population reference
is asked for, which uses the other users' training sessions and is optimistic
because the imitated attackers are drawn from that same pool.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import dataclass, field
from typing import Callable

from .corpus import (
    CmuSample,
    ScaledManhattan,
    balabit_sessions,
    cmu_class_features,
    cmu_columns,
    cmu_pair_features,
    cmu_records,
    load_balabit_labels,
    load_balabit_session,
    load_cmu,
)
from .engine import IdentityEngine
from .experts import KeystrokeExpert, KeystrokeTemplate, PointerTemplate
from .metrics import eer_exact
from .segment import Segment, segment_trace
from .trace import EventKind, KeyClass


@dataclass
class EerSummary:
    mean: float
    std: float
    per_unit: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"mean": round(self.mean, 4), "std": round(self.std, 4),
                "per_unit": {k: round(v, 4) for k, v in self.per_unit.items()}}


def _summary(per: dict[str, float]) -> EerSummary:
    vals = [v for v in per.values() if v == v]  # drop NaN (no data)
    if not vals:
        return EerSummary(float("nan"), float("nan"), per)
    return EerSummary(statistics.fmean(vals), statistics.pstdev(vals), per)


# --- CMU ------------------------------------------------------------------------


def cmu_split(
    samples: list[CmuSample], n_train: int = 200, n_impostor: int = 5,
) -> dict[str, tuple[list[CmuSample], list[CmuSample], list[CmuSample]]]:
    """{subject: (train, genuine test, impostor test)}, rows in file order."""
    by: dict[str, list[CmuSample]] = {}
    for s in samples:
        by.setdefault(s.subject, []).append(s)
    out = {}
    for subj, rows in by.items():
        impostors = [s for o, r in by.items() if o != subj for s in r[:n_impostor]]
        out[subj] = (rows[:n_train], rows[n_train:], impostors)
    return out


def cmu_manhattan(
    samples: list[CmuSample],
    transform: Callable[[CmuSample], list[float]] | None = None,
    **split_kw,
) -> EerSummary:
    """Scaled-Manhattan EER, optionally on transformed feature vectors."""
    def tx(s: CmuSample) -> CmuSample:
        return s if transform is None else CmuSample(s.subject, transform(s))

    per = {}
    for subj, (train, gen, imp) in cmu_split(samples, **split_kw).items():
        model = ScaledManhattan.train([tx(s) for s in train])
        per[subj] = eer_exact([model.score(tx(s)) for s in gen],
                              [model.score(tx(s)) for s in imp])
    return _summary(per)


def _rep_segment(s: CmuSample, columns: list[str], pair_digraphs: bool) -> Segment:
    recs = cmu_records(s, columns, pair_digraphs=pair_digraphs)
    return Segment(start_us=recs[0].time_us, end_us=recs[-1].time_us, records=recs)


def cmu_keystroke_expert(
    samples: list[CmuSample], columns: list[str], pair_digraphs: bool = False,
    **split_kw,
) -> EerSummary:
    """The keystroke expert itself, one repetition per segment, wide fallback
    reference (no impostor data in training, as in the protocol). The score is
    the segment's total evidence, as the default fusion sums it."""
    expert = KeystrokeExpert()
    empty = KeystrokeTemplate()
    per = {}
    for subj, (train, gen, imp) in cmu_split(samples, **split_kw).items():
        tpl = KeystrokeTemplate.fit([_rep_segment(s, columns, pair_digraphs) for s in train])

        def score(s: CmuSample, tpl: KeystrokeTemplate = tpl) -> float:
            ev, _ = expert.evidence(_rep_segment(s, columns, pair_digraphs), tpl, empty)
            return sum(ev.values())

        per[subj] = eer_exact([score(s) for s in gen], [score(s) for s in imp])
    return _summary(per)


def cmu_same_class_rollover(samples: list[CmuSample], columns: list[str]) -> float:
    """Share of repetitions in which a key goes down before the previous key of
    the same key class is released. The hold matcher of the keystroke expert
    pairs downs and ups by class, so such overlaps corrupt hold times."""
    hit = 0
    for s in samples:
        recs = cmu_records(s, columns)
        held: dict[KeyClass | None, bool] = {}
        bad = False
        for r in recs:
            kc = r.event.key_class
            if r.event.kind == EventKind.KEY_DOWN:
                if held.get(kc):
                    bad = True
                held[kc] = True
            else:
                held[kc] = False
        hit += bad
    return hit / len(samples) if samples else 0.0


def run_cmu(path: str) -> dict:
    samples = load_cmu(path)
    columns = cmu_columns(path)
    n_subjects = len({s.subject for s in samples})
    full = cmu_manhattan(samples)
    pairs = cmu_manhattan(samples, lambda s: cmu_pair_features(s, columns))
    classes = cmu_manhattan(samples, lambda s: cmu_class_features(s, columns))
    expert_cls = cmu_keystroke_expert(samples, columns, pair_digraphs=False)
    expert_pair = cmu_keystroke_expert(samples, columns, pair_digraphs=True)
    return {
        "protocol": "Killourhy-Maxion: first 200 reps train, last 200 genuine, "
                    "first 5 reps of each other subject impostor; exact EER per subject",
        "n_subjects": n_subjects,
        "n_rows": len(samples),
        "published_eer_scaled_manhattan": 0.096,
        "scaled_manhattan_all_31_features": full.as_dict(),
        "scaled_manhattan_true_pairs_20_features": pairs.as_dict(),
        "scaled_manhattan_classes": {
            **classes.as_dict(),
            "n_features": len(cmu_class_features(samples[0], columns)),
        },
        "keystroke_expert_digraph_classes": expert_cls.as_dict(),
        "keystroke_expert_true_digraphs": expert_pair.as_dict(),
        "share_of_reps_with_same_class_rollover": round(
            cmu_same_class_rollover(samples, columns), 4),
    }


# --- Balabit -------------------------------------------------------------------


def session_segments(records: list, **seg_kw) -> list[Segment]:
    return list(segment_trace(records, **seg_kw))


def score_session(engine: IdentityEngine, segments: list[Segment]) -> list[float]:
    """Evidence of each segment that passes the engine's quality gate; the
    gated ones carry no vote and are left out rather than scored as zero."""
    out = []
    for seg in segments:
        d = engine.step(seg)
        if d.quality >= engine.min_quality:
            out.append(d.evidence_db)
    return out


def windows(scores: list[float], k: int) -> list[float]:
    """Total evidence over non-overlapping runs of k consecutive segments; a
    tail shorter than k is dropped."""
    return [sum(scores[i:i + k]) for i in range(0, len(scores) - k + 1, k)]


def balabit_user_eers(
    genuine: list[list[float]], impostor: list[list[float]], ks: tuple[int, ...],
) -> dict[str, float]:
    """EERs for one user from per-session segment evidence lists: per window
    of k segments for each k, and per session (mean evidence)."""
    out = {}
    for k in ks:
        g = [w for s in genuine for w in windows(s, k)]
        i = [w for s in impostor for w in windows(s, k)]
        out[f"k{k}"] = eer_exact(g, i)
    g = [statistics.fmean(s) for s in genuine if s]
    i = [statistics.fmean(s) for s in impostor if s]
    out["session"] = eer_exact(g, i)
    return out


def run_balabit(
    root: str, split_axes: bool = False, population: bool = False,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict:
    labels = load_balabit_labels(os.path.join(root, "public_labels.csv"))
    train = balabit_sessions(root, "training")
    test = balabit_sessions(root, "test")
    train_segs = {
        u: [seg for p in paths
            for seg in session_segments(load_balabit_session(p, split_axes=split_axes))]
        for u, paths in train.items()
    }
    templates = {u: PointerTemplate.fit(segs) for u, segs in train_segs.items()}

    per_user: dict[str, dict[str, float]] = {}
    counts: dict[str, dict[str, int]] = {}
    for user, paths in test.items():
        ref = None
        if population:
            others = [s for o, segs in train_segs.items() if o != user for s in segs]
            ref = PointerTemplate.fit(others)
        gen, imp = [], []
        for p in paths:
            name = os.path.basename(p)
            if name not in labels:
                continue
            eng = IdentityEngine(genuine=KeystrokeTemplate(), pointer=templates[user],
                                 pointer_reference=ref)
            scores = score_session(
                eng, session_segments(load_balabit_session(p, split_axes=split_axes)))
            (imp if labels[name] else gen).append(scores)
        per_user[user] = balabit_user_eers(gen, imp, ks)
        counts[user] = {
            "genuine_sessions": len(gen), "impostor_sessions": len(imp),
            "genuine_segments": sum(len(s) for s in gen),
            "impostor_segments": sum(len(s) for s in imp),
        }

    levels = [f"k{k}" for k in ks] + ["session"]
    return {
        "reference": "population (other users' training)" if population else "wide fallback",
        "motion": "split axes (as the live recorder)" if split_axes else "one record per event",
        "eer": {lv: _summary({u: per_user[u][lv] for u in per_user}).as_dict()
                for lv in levels},
        "counts": counts,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.public_eval")
    ap.add_argument("--cmu", help="DSL-StrongPasswordData.csv")
    ap.add_argument("--balabit", help="Mouse-Dynamics-Challenge directory")
    ap.add_argument("--out", help="directory for metrics.json")
    args = ap.parse_args(argv)
    result: dict = {}
    if args.cmu:
        result["cmu"] = run_cmu(args.cmu)
    if args.balabit:
        result["balabit"] = {
            "wide_combined": run_balabit(args.balabit),
            "wide_split_axes": run_balabit(args.balabit, split_axes=True),
            "population_combined": run_balabit(args.balabit, population=True),
        }
    text = json.dumps(result, indent=2)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "metrics.json"), "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
