"""Counting users, and revising the count: the original 'how many people' ask.

Cases: two genuinely different people stay two profiles; the same person seen as
several regimes collapses to one; and a person on two devices, alternating
within sessions, is one profile with two modes (temporal interleaving).
"""

from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.profiles import ProfileSet, temporal_interleaving
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Typist

ALICE = dict(hold_mu=11.35, hold_sigma=0.24, gap_mu=11.45, gap_sigma=0.28)
BOB = dict(hold_mu=12.10, hold_sigma=0.40, gap_mu=12.30, gap_sigma=0.45)


def template(params, seed, n=6, keys=40):
    segs = [next(segment_trace(Typist(seed=seed + s, **params).type_segment(keys)))
            for s in range(n)]
    return KeystrokeTemplate.fit(segs)


def test_interleaving_metric():
    assert temporal_interleaving({1, 2, 3}, {1, 2, 3}) == 1.0
    assert temporal_interleaving({1, 2}, {3, 4}) == 0.0
    assert 0 < temporal_interleaving({1, 2, 3}, {3, 4, 5}) < 1.0


def test_two_distinct_people_stay_two_profiles():
    ps = ProfileSet()
    # Distinct people, disjoint sessions.
    for s in range(4):
        ps.add_regime(template(ALICE, seed=100 + s * 10), session_id=s)
    for s in range(4, 8):
        ps.add_regime(template(BOB, seed=500 + s * 10), session_id=s)
    ps.revise()
    assert ps.count == 2, f"expected 2 people, got {ps.count}"


def test_same_person_many_regimes_collapse_to_one():
    ps = ProfileSet()
    # Same params, different draws, disjoint sessions: should still merge on
    # template closeness alone.
    for s in range(6):
        ps.add_regime(template(ALICE, seed=1000 + s * 50), session_id=s)
    ps.revise()
    assert ps.count == 1, f"expected 1 person, got {ps.count}"


def test_same_person_two_devices_is_one_profile_two_modes():
    ps = ProfileSet()
    # Two distinct regimes (different timing) but ALTERNATING within the same
    # sessions -> interleaved -> one person, two modes.
    internal = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.30)
    external = dict(hold_mu=11.75, hold_sigma=0.30, gap_mu=11.85, gap_sigma=0.34)
    for s in range(6):
        ps.add_regime(template(internal, seed=2000 + s * 10), session_id=s)
        ps.add_regime(template(external, seed=6000 + s * 10), session_id=s)
    ps.revise()
    assert ps.count == 1, f"interleaved regimes should be one profile, got {ps.count}"
    assert len(ps.profiles[0].modes) >= 2
    assert any(e.kind == "merge" for e in ps.history)


def test_revision_history_is_recorded_with_reasons():
    ps = ProfileSet()
    for s in range(4):
        ps.add_regime(template(ALICE, seed=3000 + s * 30), session_id=s)
    ps.revise()
    assert ps.count == 1
    assert ps.history and "JS distance" in ps.history[0].detail
