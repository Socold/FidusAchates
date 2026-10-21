"""Global templates versus per-usage templates, on synthetic typists.

    PYTHONPATH=lab python3 research/results/2026-10-21-usage-aware/run.py

I type differently when I write and when I play. The global model learns
both as modes and scores a window against the best-matching one; the
usage-aware model scores a window against the template of the usage it was
typed in. Same enrolment data, same seeds, only the category differs.
"""

from __future__ import annotations

import json
import statistics
import sys
from dataclasses import replace

from fidus_lab.context import CATEGORIES
from fidus_lab.learning import Enrolled
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Typist

OFFICE = CATEGORIES.index("office")
GAME = CATEGORIES.index("game")
WRITING = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
PLAYING = dict(hold_mu=12.2, hold_sigma=0.3, gap_mu=12.3, gap_sigma=0.35)
# Someone between my two usages, and someone whose holds are longer than mine
# when I play but whose gaps are shorter than mine when I write. Measured
# down-to-down latency is hold plus gap, so the latter lands close to my
# playing rhythm on that signal: a cross impostor, not a distant one.
BETWEEN = dict(hold_mu=11.8, hold_sigma=0.3, gap_mu=11.9, gap_sigma=0.35)
CROSS = dict(hold_mu=12.6, hold_sigma=0.4, gap_mu=11.0, gap_sigma=0.45)
SESSIONS = 30
SEGMENTS = 15


def typed(params, n, seed, category, keys=40):
    segs, t = [], 0
    for i in range(n):
        recs = Typist(seed=seed + i, **params).type_segment(keys, start_us=t)
        for s in segment_trace(recs):
            s.category = category
            segs.append(s)
        t = recs[-1].time_us + 10_000_000
    return segs


def blind(segs):
    return [replace(s, category=None) for s in segs]


def first_alarm(enrolled, segs):
    eng = enrolled.engine()
    for i, s in enumerate(segs, start=1):
        if eng.step(s).alarmed:
            return i
    return None


def scenario(enrolled, make, usage_aware):
    delays = []
    for k in range(SESSIONS):
        segs = make(10_000 + 100 * k)
        delays.append(first_alarm(enrolled, segs if usage_aware else blind(segs)))
    hit = [d for d in delays if d is not None]
    return {"alarmed_fraction": round(len(hit) / SESSIONS, 3),
            "median_delay_segments": statistics.median(hit) if hit else None}


def main() -> int:
    # In games I mostly play, and sometimes type in the chat as I write.
    enrol = (typed(WRITING, 40, seed=100, category=OFFICE)
             + typed(PLAYING, 40, seed=300, category=GAME)
             + typed(WRITING, 20, seed=500, category=GAME))
    models = {"global": Enrolled.fit(blind(enrol)), "usage_aware": Enrolled.fit(enrol)}
    cases = {
        "me_writing": lambda s: typed(WRITING, SEGMENTS, s, OFFICE),
        "me_playing": lambda s: typed(PLAYING, SEGMENTS, s, GAME),
        "impostor_with_my_playing_rhythm_writing": lambda s: typed(PLAYING, SEGMENTS, s, OFFICE),
        "me_chatting_in_a_game": lambda s: typed(WRITING, SEGMENTS, s, GAME),
        "impostor_between_my_usages_writing": lambda s: typed(BETWEEN, SEGMENTS, s, OFFICE),
        "impostor_cross_writing": lambda s: typed(CROSS, SEGMENTS, s, OFFICE),
    }
    out = {"note": "synthetic typists; alarmed_fraction is a false alarm rate for 'me_*' "
                   "and a detection rate otherwise",
           "sessions": SESSIONS, "segments_per_session": SEGMENTS,
           "modes_in_global_model": len(models["global"].modes),
           "usage_modes": {CATEGORIES[c]: len(m) for c, m
                           in sorted(models["usage_aware"].context_keystroke.items())}}
    for name, make in cases.items():
        out[name] = {m: scenario(models[m], make, m == "usage_aware") for m in models}
    json.dump(out, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
