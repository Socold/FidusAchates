import io

import pytest

from fidus_lab.context import ContextTracker, attach
from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import HabitExpert, HabitTemplate, KeystrokeTemplate
from fidus_lab.experts.habits import (
    approach_direction,
    departure_direction,
    gestures,
    octant,
    overshoot_bin,
)
from fidus_lab.segment import Segment
from fidus_lab.synth import HabitualUser
from fidus_lab.trace import (
    MAGIC,
    Event,
    EventKind,
    KeyClass,
    Record,
    ShortcutClass,
    encode,
    read_stream,
)

OWNER = dict(departure=0, overshoot_p=0.1, law_a=11.0, law_b=0.35,
             shortcuts=((1, 0.5), (2, 0.4), (4, 0.1)), apps=(0, 1, 2))
OTHER = dict(departure=4, overshoot_p=0.6, law_a=11.5, law_b=0.25,
             shortcuts=((6, 0.4), (19, 0.4), (27, 0.2)), apps=(3, 4, 0))


def seg_of(records, context=()):
    s = Segment(start_us=records[0].time_us, end_us=records[-1].time_us,
                records=sorted(records, key=lambda r: r.time_us))
    s.context.extend(context)
    return s


def person_segments(params, n_segments, seed):
    u = HabitualUser(seed=seed, **params)
    segs = []
    tracker = ContextTracker()
    for i in range(n_segments):
        t0 = i * 100_000_000
        recs = u.gestures(12, start_us=t0) + u.shortcut_presses(10, start_us=t0 + 5_000)
        s = seg_of(recs)
        evs = [tracker.tick(t, c) for t, c in u.app_switches(6, start_us=t0 + 10_000)]
        attach([s], [e for e in evs if e is not None])
        segs.append(s)
    return segs


def test_octants():
    assert octant(10, 0) == 0
    assert octant(0, -10) == 2   # screen y grows down, so -dy is up
    assert octant(-10, 0) == 4
    assert octant(0, 10) == 6


def test_gesture_features_follow_the_generator():
    u = HabitualUser(seed=3, departure=4, departure_p=1.0, overshoot_p=1.0)
    gs = gestures(seg_of(u.gestures(10)))
    assert len(gs) == 10
    assert all(g.clicked for g in gs)
    assert {departure_direction(g) for g in gs} == {4}
    # Overshooting far enough means arriving from the far side: the approach
    # reverses once the way back is longer than the reading distance.
    # Rounding to whole device counts can tip a direction into a neighbour.
    near = {7, 0, 1, 3, 4, 5}
    assert {approach_direction(g) for g in gs} <= near
    assert 0 in {approach_direction(g) for g in gs}
    assert all(overshoot_bin(g) >= 1 for g in gs if overshoot_bin(g) is not None)
    straight = gestures(seg_of(HabitualUser(seed=3, departure=4, departure_p=1.0,
                                            overshoot_p=0.0).gestures(10)))
    assert {approach_direction(g) for g in straight} <= {3, 4, 5}
    assert {overshoot_bin(g) for g in straight} <= {0, None}


def test_owner_scores_genuine_and_other_scores_impostor():
    enrol = person_segments(OWNER, 20, seed=1)
    tpl = HabitTemplate.fit(enrol)
    assert {"A16_shortcut", "B25_departure", "C02_transition"} <= set(tpl.categorical)
    assert tpl.law is not None
    ex = HabitExpert()
    own = [sum(ex.evidence(s, tpl)[0].values()) for s in person_segments(OWNER, 6, seed=2)]
    other = [sum(ex.evidence(s, tpl)[0].values()) for s in person_segments(OTHER, 6, seed=3)]
    assert max(own) < 0 < min(other)


def test_population_reference_changes_the_evidence():
    enrol = person_segments(OWNER, 20, seed=1)
    tpl = HabitTemplate.fit(enrol)
    pop = HabitTemplate.fit(person_segments(OTHER, 20, seed=4))
    seg = person_segments(OWNER, 1, seed=5)[0]
    ex = HabitExpert()
    wide = sum(ex.evidence(seg, tpl)[0].values())
    with_pop = sum(ex.evidence(seg, tpl, pop)[0].values())
    assert with_pop != wide


def test_engine_uses_habits_and_rejects_self_reference():
    enrol = person_segments(OWNER, 20, seed=1)
    tpl = HabitTemplate.fit(enrol)
    eng = IdentityEngine(genuine=KeystrokeTemplate(), habits=tpl)
    d = eng.step(person_segments(OTHER, 1, seed=6)[0])
    assert any(k.startswith(("A16", "B25", "C02")) for k in d.contributions)
    with pytest.raises(ValueError):
        IdentityEngine(genuine=KeystrokeTemplate(), habits=tpl, habits_reference=tpl)


def test_context_tracker_ranks_the_opening_sequence():
    t = ContextTracker()
    evs = [t.tick(i, c) for i, c in enumerate(["browser", "browser", "terminal",
                                                "development", "office", "browser"])]
    evs = [e for e in evs if e is not None]
    assert [e.opening_rank for e in evs] == [0, 1, 2, None, None]
    assert evs[0].previous is None and evs[1].previous == 0
    t.new_session()
    assert t.tick(10, "media").opening_rank == 0


def test_shortcut_survives_encode_and_stream_read():
    recs = [
        Record(1, 0, False, Event(EventKind.KEY_DOWN, KeyClass.LETTER, 5,
                                  shortcut=ShortcutClass.UNDO)),
        Record(2, 0, False, Event(EventKind.KEY_UP, KeyClass.LETTER, 0)),
        Record(3, 1, True, Event(EventKind.MOTION, dx=-40000, dy=7)),
        Record(4, 1, False, Event(EventKind.BUTTON_DOWN, button=1)),
    ]
    blob = MAGIC + b"".join(encode(r) for r in recs)
    back = list(read_stream(io.BytesIO(blob)))
    assert back[0].event.shortcut == ShortcutClass.UNDO
    assert back[1].event.shortcut == ShortcutClass.NONE
    assert back[2].event.dx == -32768 and back[2].virtual
    assert back[3].event.button == 1


class _Trickle(io.RawIOBase):
    """A pipe that hands out a few bytes per read, mid-record."""

    def __init__(self, data: bytes) -> None:
        self._d = data

    def readable(self) -> bool:
        return True

    def read(self, n=-1):
        k = 3 if n is None or n < 0 else min(3, n)
        chunk, self._d = self._d[:k], self._d[k:]
        return chunk


def test_stream_reader_reassembles_short_reads():
    r = Record(9, 0, False, Event(EventKind.WHEEL, dx=0, dy=-1))
    back = list(read_stream(_Trickle(MAGIC + encode(r) * 3)))
    assert len(back) == 3 and back[0].event.dy == -1
