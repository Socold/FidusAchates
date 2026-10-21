import time

from fidus_lab.learning import (
    Enrolled,
    learning_curve,
    replay,
    simulate_impostor,
    split_sessions,
)
from fidus_lab.segment import Segment
from fidus_lab.synth import HabitualUser, Typist

OWNER_KEYS = dict(hold_mu=11.4, hold_sigma=0.2, gap_mu=11.8, gap_sigma=0.25)
GUEST_KEYS = dict(hold_mu=11.9, hold_sigma=0.2, gap_mu=12.3, gap_sigma=0.25)


def person(keys, habits, n, seed, t0=0):
    """n segments of ~20 s: some typing, some pointing, a few shortcuts."""
    typ = Typist(seed=seed, **keys)
    hab = HabitualUser(seed=seed, **habits)
    segs = []
    for i in range(n):
        start = t0 + i * 30_000_000
        recs = typ.type_segment(40, start_us=start)
        recs += hab.gestures(4, start_us=recs[-1].time_us + 100_000)
        recs += hab.shortcut_presses(2, start_us=recs[-1].time_us + 100_000)
        segs.append(Segment(start_us=recs[0].time_us, end_us=recs[-1].time_us, records=recs))
    return segs


def test_simulated_impostor_differs_but_keeps_shape():
    segs = person(OWNER_KEYS, {}, 3, seed=1)
    fake = simulate_impostor(segs, seed=4)
    assert len(fake) == len(segs)
    assert [s.n_events for s in fake] == [s.n_events for s in segs]
    assert any(a.duration_us != b.duration_us for a, b in zip(fake, segs, strict=True))


def test_split_sessions_caps_size():
    segs = person(OWNER_KEYS, {}, 25, seed=2)
    sessions = split_sessions(segs, max_segments=10)
    assert [len(s) for s in sessions] == [10, 10, 5]


def test_owner_is_recognised_and_guest_is_caught():
    enrol = person(OWNER_KEYS, {}, 30, seed=3)
    eng = Enrolled.fit(enrol)
    own = replay(eng.engine(), person(OWNER_KEYS, {}, 10, seed=4))
    other = replay(eng.engine(), person(GUEST_KEYS, dict(departure=4), 10, seed=5))
    assert own.recognised_after_s is not None and own.alarms == 0
    assert other.first_alarm_after_s is not None


def test_curve_with_guests_reports_real_kind_and_improves():
    owner = person(OWNER_KEYS, {}, 80, seed=6)
    guests = [person(GUEST_KEYS, dict(departure=4), 8, seed=10 + i, t0=10**12)
              for i in range(3)]
    t = time.time()
    curve = learning_curve(owner, guests, budgets_min=(1, 3, 10, 20))
    assert time.time() - t < 60
    assert curve.impostor_kind == "guest" and curve.population_reference
    pts = curve.points
    assert len(pts) >= 3
    assert pts[-1].enrol_minutes > pts[0].enrol_minutes
    assert pts[-1].detected_share == 1.0
    assert pts[-1].false_alarms_per_hour == 0.0
    assert curve.ready_at_minutes is not None
    d = curve.as_dict()
    assert d["ready_at_minutes"] == curve.ready_at_minutes


def test_curve_without_guests_says_simulated():
    owner = person(OWNER_KEYS, {}, 40, seed=7)
    curve = learning_curve(owner, None, budgets_min=(2, 5))
    assert curve.impostor_kind == "simulated"
    assert "simulated" in curve.note


def test_too_little_data_is_said_not_guessed():
    curve = learning_curve(person(OWNER_KEYS, {}, 3, seed=8))
    assert curve.points == [] and curve.note


def test_a_different_typist_is_caught_despite_my_own_pointer():
    """Regression: pointer velocity has one observation per motion event, and
    summed as if independent it outweighed every keystroke signal, so a
    different typist using the pointer like me went unseen for minutes or
    for good. Pooled evidence (evidence.pooled) bounds it."""
    owner = person(OWNER_KEYS, {}, 60, seed=6)
    eng = Enrolled.fit(owner)
    caught = [replay(eng.engine(), person(GUEST_KEYS, {}, 10, seed=s)).first_alarm_after_s
              for s in range(20, 26)]
    assert all(c is not None and c < 60 for c in caught)
    mine = [replay(eng.engine(), person(OWNER_KEYS, {}, 10, seed=s + 100)).alarms
            for s in range(20, 26)]
    assert sum(mine) == 0
