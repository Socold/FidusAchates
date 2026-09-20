"""Break the circularity: validate the engine on data that violates its model.

Every earlier validation used log-normal typists, the model the engine
assumes. Here the genuine user is a HostileTypist (bimodal holds, bursty gaps,
corrections, heavy tails). Two questions, answered honestly:

1. Does the engine still reject a distinct impostor when the genuine data is
   off-model?  (It should: the impostor is still far away.)
2. Does it stay quiet on the genuine user despite the model mismatch?  This
   is where a naive log-normal fit can misfire on bimodal data. We measure the
   false alarm rate and require it to stay within budget on this data, and we
   record the number rather than assume it.
"""

from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.segment import segment_trace
from fidus_lab.synth import HostileTypist, Typist

SMOOTH_IMPOSTOR = dict(hold_mu=12.4, hold_sigma=0.3, gap_mu=12.6, gap_sigma=0.35)


def hostile_segs(n, seed0=0, keys=40):
    out = []
    for s in range(n):
        recs = HostileTypist(seed=seed0 + s).type_segment(keys)
        out.extend(segment_trace(recs, gap_us=60_000_000))  # keep one segment
    return out


def smooth_segs(params, n, seed0=0, keys=40):
    out = []
    for s in range(n):
        out.extend(segment_trace(Typist(seed=seed0 + s, **params).type_segment(keys)))
    return out


def test_off_model_genuine_user_still_rejects_a_distinct_impostor():
    tpl = KeystrokeTemplate.fit(hostile_segs(10, seed0=100))
    eng = IdentityEngine(genuine=tpl, reference=None)
    fired = any(eng.step(s).alarmed for s in smooth_segs(SMOOTH_IMPOSTOR, 12, seed0=700))
    assert fired, "a clearly different impostor was not detected on off-model enrolment"


def test_off_model_genuine_user_false_alarm_rate_is_measured_and_bounded():
    """A log-normal fit on bimodal, bursty data is a real mismatch. We do not
    assume it is harmless: we measure the false alarm rate over many sessions
    and bound it. If this bound ever has to be loosened, that is a finding
    about the model, and it must be recorded as one."""
    tpl = KeystrokeTemplate.fit(hostile_segs(10, seed0=100))
    sessions = 30
    alarms = 0
    for s in range(sessions):
        eng = IdentityEngine(genuine=tpl, reference=None)
        for seg in hostile_segs(6, seed0=2000 + s * 10):
            if eng.step(seg).alarmed:
                alarms += 1
                break
    rate = alarms / sessions
    # Budget: at most one session in five may raise a false alarm on data
    # this hostile to the model. Recorded, not hidden.
    assert rate <= 0.20, f"false alarm rate on off-model genuine data: {rate:.2f}"
