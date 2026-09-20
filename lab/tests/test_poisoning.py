from fidus_lab.divergence import template_stability
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.poisoning import AnchorWatch, admits, bounded_update
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Typist

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
IMP = dict(hold_mu=12.2, hold_sigma=0.45, gap_mu=12.4, gap_sigma=0.5)


def template(params, n, seed0):
    segs = [next(segment_trace(Typist(seed=seed0 + s, **params).type_segment(40)))
            for s in range(n)]
    return KeystrokeTemplate.fit(segs)


def test_admission_gate_rejects_non_genuine_windows():
    assert admits(-8.0)       # clearly genuine
    assert not admits(0.0)    # neutral
    assert not admits(5.0)    # impostor-like


def test_bounded_update_moves_only_a_little():
    genuine = template(GEN, 8, seed0=0)
    impostor = template(IMP, 8, seed0=100)
    before = template_stability(genuine, impostor)
    updated = bounded_update(genuine, impostor, max_step=0.05)
    after = template_stability(genuine, updated)
    # One bounded step moves the template far less than all the way.
    assert after < 0.2 * before


def test_anchor_watch_flags_cumulative_drift():
    anchor = template(GEN, 8, seed0=0)
    watch = AnchorWatch(anchor=anchor, drift_alert_threshold=0.15)
    # Repeated bounded updates towards an impostor eventually trip the anchor.
    impostor = template(IMP, 8, seed0=100)
    current = anchor
    tripped_at = None
    for i in range(1, 200):
        current = bounded_update(current, impostor, max_step=0.05)
        if watch.drifted(current):
            tripped_at = i
            break
    assert tripped_at is not None, "drift never detected"
