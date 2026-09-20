from fidus_lab.divergence import gaussian_js, template_stability
from fidus_lab.enrolment import Phase, assess
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Typist

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)


def sessions(params, n, keys=40, seed0=0):
    out = []
    for s in range(n):
        recs = Typist(seed=seed0 + s, **params).type_segment(keys)
        out.append(list(segment_trace(recs)))
    return out


def template(params, n, seed0):
    segs = [seg for sess in sessions(params, n, seed0=seed0) for seg in sess]
    return KeystrokeTemplate.fit(segs)


def test_js_is_zero_for_identical_and_grows_with_separation():
    assert gaussian_js(0.0, 1.0, 0.0, 1.0) < 1e-6
    near = gaussian_js(0.0, 1.0, 0.3, 1.0)
    far = gaussian_js(0.0, 1.0, 3.0, 1.0)
    assert 0 < near < far <= 1.0


def test_same_user_templates_are_more_stable_than_cross_user():
    a = template(GEN, 8, seed0=0)
    b = template(GEN, 8, seed0=100)  # same params, different draws
    IMP = dict(hold_mu=12.0, hold_sigma=0.4, gap_mu=12.2, gap_sigma=0.4)
    c = template(IMP, 8, seed0=200)
    assert template_stability(a, b) < template_stability(a, c)


def test_criteria_not_ready_until_all_met():
    enrol = sessions(GEN, 8, seed0=0)
    # Volume ok, but stability history empty and performance not ok yet.
    conv = assess(enrol, stability_history=[], performance_ok=False,
                  n_keystrokes=3000, n_days=6, n_devices=1)
    assert conv.volume == 1.0
    assert conv.stability == 0.0
    assert not conv.ready
    assert conv.phase() == Phase.ENROLMENT


def test_criteria_ready_when_all_met():
    enrol = sessions(GEN, 8, seed0=0)
    conv = assess(enrol, stability_history=[0.01, 0.01, 0.01], performance_ok=True,
                  n_keystrokes=3000, n_days=6, n_devices=1)
    assert conv.ready
    assert conv.phase() == Phase.OPERATIONAL


def test_bootstrap_phase_on_low_volume():
    conv = assess([], stability_history=[], performance_ok=False,
                  n_keystrokes=100, n_days=1, n_devices=1)
    assert conv.phase() == Phase.BOOTSTRAP


def test_tracker_derives_counts_from_the_data():
    """Review finding: assess() trusted caller-supplied counts. The tracker
    computes keystrokes, sessions and devices from the segments it is fed."""
    from fidus_lab.enrolment import EnrolmentTracker
    tr = EnrolmentTracker()
    t = 0
    for s in range(10):
        recs = Typist(seed=s, **GEN).type_segment(40, start_us=t)
        for seg in segment_trace(recs):
            tr.feed(seg)
        # Separate every other batch by more than the session gap.
        t = recs[-1].time_us + (tr.session_gap_us + 1 if s % 2 else 5_000_000)
    assert tr.n_keystrokes == 400
    assert tr.n_sessions >= 5
    assert tr.devices == {0}
    assert len(tr.snapshots) >= 2
    conv = tr.convergence(performance_ok=False)
    # Volume is data-derived and partial with defaults (needs 2000 keystrokes).
    assert 0 < conv.volume < 1.0
