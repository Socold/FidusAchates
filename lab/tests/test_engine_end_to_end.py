"""The decision the whole project exists to make, on synthetic typists.

Enrol on a genuine user, then: the same user is not falsely alarmed, and a
different user (impostor) is detected within a bounded number of segments. No
real corpus needed to validate the machinery; corpus numbers are separate.
"""

from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Typist

# Genuine: fast, tight typist. Impostor: slower, looser. mu in log-microseconds
# (exp(11.4) ~= 90 ms hold, exp(11.9) ~= 147 ms).
GENUINE = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
IMPOSTOR = dict(hold_mu=11.9, hold_sigma=0.35, gap_mu=12.1, gap_sigma=0.4)


def segments_from(typist, n_segments, keys=40, seed_start=0):
    segs = []
    t = 0
    for i in range(n_segments):
        ty = Typist(seed=seed_start + i, **typist)
        recs = ty.type_segment(keys, start_us=t)
        segs.extend(segment_trace(recs))
        # Big gap so each call is its own segment.
        t = recs[-1].time_us + 10_000_000
    return segs


def build_engine():
    enrol = segments_from(GENUINE, n_segments=8, seed_start=100)
    genuine_tpl = KeystrokeTemplate.fit(enrol)
    # Impostor reference from a population distinct from the test impostor.
    ref = KeystrokeTemplate.fit(segments_from(IMPOSTOR, n_segments=8, seed_start=200))
    return IdentityEngine(genuine=genuine_tpl, reference=ref, cusum_h=25.0)


def test_genuine_user_is_not_alarmed():
    eng = build_engine()
    test_segs = segments_from(GENUINE, n_segments=20, seed_start=500)
    alarms = sum(1 for s in test_segs if eng.step(s).alarmed)
    assert alarms == 0, "genuine user falsely alarmed"


def test_impostor_is_detected_within_a_bound():
    eng = build_engine()
    impostor_segs = segments_from(IMPOSTOR, n_segments=20, seed_start=700)
    detected_at = None
    for i, s in enumerate(impostor_segs, start=1):
        if eng.step(s).alarmed:
            detected_at = i
            break
    assert detected_at is not None, "impostor never detected"
    assert detected_at <= 10, f"detection too slow: {detected_at} segments"


def test_evidence_points_the_right_way():
    # A genuine segment should give non-positive evidence on average.
    g = segments_from(GENUINE, 1, seed_start=900)[0]
    imp = segments_from(IMPOSTOR, 1, seed_start=901)[0]
    eng_g = build_engine().step(g).evidence_db
    eng_i = build_engine().step(imp).evidence_db
    assert eng_i > eng_g, "impostor evidence not higher than genuine"


def test_alarm_resets_the_statistic_so_it_does_not_stick():
    """Bug fixed: after an alarm the CUSUM must reset. Otherwise one alarm
    made every subsequent window 'alarmed' for the rest of the session."""
    eng = build_engine()
    impostor_segs = segments_from(IMPOSTOR, n_segments=6, seed_start=800)
    fired = [eng.step(s).alarmed for s in impostor_segs]
    assert any(fired), "impostor never detected"
    # After the first alarm the statistic restarts from zero: a genuine
    # segment right after must NOT report an alarm.
    genuine_seg = segments_from(GENUINE, 1, seed_start=950)[0]
    d = eng.step(genuine_seg)
    assert not d.alarmed
    assert d.cumulative < eng.cusum_h


def test_genuine_as_reference_is_refused():
    """Bug fixed: passing the genuine template as the impostor reference made
    every LLR exactly zero, an inert channel that looked like a working one."""
    import pytest
    tpl = KeystrokeTemplate.fit(segments_from(GENUINE, 4, seed_start=1))
    with pytest.raises(ValueError):
        IdentityEngine(genuine=tpl, reference=tpl)


def test_wide_fallback_still_separates_without_a_population():
    """With no impostor population, the wide fallback must still push an
    impostor's evidence above a genuine user's."""
    tpl = KeystrokeTemplate.fit(segments_from(GENUINE, 8, seed_start=100))
    g = segments_from(GENUINE, 1, seed_start=900)[0]
    i = segments_from(IMPOSTOR, 1, seed_start=901)[0]
    eg = IdentityEngine(genuine=tpl, reference=None).step(g).evidence_db
    ei = IdentityEngine(genuine=tpl, reference=None).step(i).evidence_db
    assert ei > eg
