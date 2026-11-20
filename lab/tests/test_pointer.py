"""The pointer expert: the engine must not be blind when nobody types, and the
explanation must have more than one bar."""

from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import KeystrokeTemplate, PointerTemplate
from fidus_lab.explain import waterfall
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Mouser, Typist

GEN_T = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
# Fast, precise mouser vs slow, hesitant one.
GEN_M = dict(vel_mu=0.3, vel_sigma=0.3, pause_mu=11.5, pause_sigma=0.3, click_mu=11.3, click_sigma=0.25)
IMP_M = dict(vel_mu=-0.4, vel_sigma=0.4, pause_mu=12.3, pause_sigma=0.4, click_mu=11.9, click_sigma=0.35)


def mouse_segs(params, n, seed0=0):
    out = []
    for s in range(n):
        recs = Mouser(seed=seed0 + s, **params).move_and_click(6)
        out.extend(segment_trace(recs))
    return out


def test_pointer_template_fits_all_four_signals():
    tpl = PointerTemplate.fit(mouse_segs(GEN_M, 6, seed0=0))
    assert {"B01_velocity", "B09_pause_before_click", "B10_click_duration"} <= set(tpl.models)


def test_engine_sees_a_pointer_only_impostor():
    """No typing at all in the evaluated segments: only the pointer expert can
    speak. Before it existed, the engine was blind here."""
    kb = KeystrokeTemplate.fit(list(segment_trace(Typist(seed=1, **GEN_T).type_segment(40))))
    ptr = PointerTemplate.fit(mouse_segs(GEN_M, 8, seed0=100))
    eng = IdentityEngine(genuine=kb, reference=None, pointer=ptr, pointer_reference=None)
    genuine_ev = [eng.step(s).evidence_db for s in mouse_segs(GEN_M, 5, seed0=500)]
    eng2 = IdentityEngine(genuine=kb, reference=None, pointer=ptr, pointer_reference=None)
    impostor_ev = [eng2.step(s).evidence_db for s in mouse_segs(IMP_M, 5, seed0=700)]
    assert sum(impostor_ev) / len(impostor_ev) > sum(genuine_ev) / len(genuine_ev)
    assert any(d != 0.0 for d in impostor_ev), "pointer-only segments produced no evidence"


def test_explanation_has_several_bars():
    """The waterfall used to have one bar (a single scalar per expert). With
    per-signal evidence it separates hold, digraph classes and pointer."""
    kb = KeystrokeTemplate.fit(list(segment_trace(Typist(seed=1, **GEN_T).type_segment(60))))
    ptr = PointerTemplate.fit(mouse_segs(GEN_M, 8, seed0=100))
    eng = IdentityEngine(genuine=kb, reference=None, pointer=ptr, pointer_reference=None)
    # A mixed segment: typing then mousing.
    recs = Typist(seed=9, **GEN_T).type_segment(40) + \
        Mouser(seed=9, **GEN_M).move_and_click(4, start_us=6_000_000)
    seg = next(segment_trace(sorted(recs, key=lambda r: r.time_us), gap_us=10_000_000))
    d = eng.step(seg)
    bars = waterfall(d.contributions)
    names = {b.signal for b in bars}
    assert len(bars) >= 3
    assert any(n.startswith("A0") for n in names) and any(n.startswith("B") for n in names)
    # Exactness: the bars sum to the fused evidence (bias is zero by default).
    assert abs(sum(b.decibans for b in bars) - d.evidence_db) < 1e-9


def test_without_a_population_the_pointer_vouches_only_up_to_the_cap():
    """The wide fallback cannot tell me from another hand on the same mouse,
    so it may accuse in full but vouch only up to the cap, per signal."""
    from fidus_lab.experts import PointerExpert
    ptr = PointerTemplate.fit(mouse_segs(GEN_M, 8, seed0=100))
    seg = mouse_segs(GEN_M, 1, seed0=900)[0]
    capped, _ = PointerExpert().evidence(seg, ptr, PointerTemplate())
    free, _ = PointerExpert(fallback_vouch_cap_db=None).evidence(seg, ptr, PointerTemplate())
    assert min(free.values()) < -1.0, "the genuine segment should vouch strongly uncapped"
    assert all(v >= -1.0 for v in capped.values())
    imp = mouse_segs(IMP_M, 1, seed0=901)[0]
    acc_c, _ = PointerExpert().evidence(imp, ptr, PointerTemplate())
    acc_f, _ = PointerExpert(fallback_vouch_cap_db=None).evidence(imp, ptr, PointerTemplate())
    assert {k: v for k, v in acc_c.items() if v > 0} == {k: v for k, v in acc_f.items() if v > 0}


def test_with_a_population_the_cap_does_not_apply():
    from fidus_lab.experts import PointerExpert
    ptr = PointerTemplate.fit(mouse_segs(GEN_M, 8, seed0=100))
    pop = PointerTemplate.fit(mouse_segs(IMP_M, 8, seed0=300))
    seg = mouse_segs(GEN_M, 1, seed0=900)[0]
    capped, _ = PointerExpert().evidence(seg, ptr, pop)
    free, _ = PointerExpert(fallback_vouch_cap_db=None).evidence(seg, ptr, pop)
    assert capped == free


def test_vouch_bench_reports_each_cap():
    from fidus_lab.learning import Enrolled, split_sessions
    from fidus_lab.vouch_eval import cap_row
    own = mouse_segs(GEN_M, 30, seed0=1000)
    enrolled = Enrolled.fit(own[:20])
    held = split_sessions(own[20:], max_segments=5)
    guest = split_sessions(mouse_segs(IMP_M, 10, seed0=2000), max_segments=5)
    rows = [cap_row(enrolled, held, [guest], [], c) for c in (None, 0.0)]
    assert [r["cap_db"] for r in rows] == [None, 0.0]
    # Capping vouching can only add alarms on the guest, never remove them.
    assert rows[1]["guests"][0]["alarms"] >= rows[0]["guests"][0]["alarms"]
