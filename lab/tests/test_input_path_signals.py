"""E20 phantom activity, E11 remote timing and the re-timing measure, on
synthetic segments. The thresholds themselves are measured in docs/09-STUDY-INPUT-PATH.md."""

import random

from fidus_lab.attribution import (
    ActorLabel,
    PhantomWatch,
    RemoteTimingWatch,
    attribute,
    near_simultaneous_share,
)
from fidus_lab.daemon import panel_state
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.experts.keystroke import hold_dispersion_ratio
from fidus_lab.kloak import obfuscate_times
from fidus_lab.registry import SanctionRegistry
from fidus_lab.segment import Segment, segment_trace
from fidus_lab.synth import Typist
from fidus_lab.trace import Record

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
S = 1_000_000


def _seg(records):
    return Segment(start_us=records[0].time_us, end_us=records[-1].time_us, records=records)


def _typed(seed, n=60, start_us=0):
    return _seg(Typist(seed=seed, **GEN).type_segment(n, start_us=start_us))


def _retimed(seg, max_delay_ms, seed=0):
    out, _ = obfuscate_times([r.time_us / 1000 for r in seg.records], max_delay_ms,
                             random.Random(seed))
    return _seg([Record(t * 1000, r.device, r.virtual, r.event)
                 for t, r in zip(out, seg.records, strict=True)])


def test_phantom_needs_several_focus_changes_and_a_silent_recorder():
    w = PhantomWatch(window_us=120 * S, min_changes=4, started_us=0)
    w.input(10 * S)
    # Focus changes while I type: nothing.
    assert not any(w.focus(t * S) for t in (20, 30, 40, 50))
    # Silence, then focus keeps changing: the fourth change in the window starts it.
    assert [w.focus(t * S) for t in (200, 210, 220, 230)] == [False, False, False, True]
    assert w.active and not w.focus(240 * S)
    # Input reaching the recorder again ends it.
    assert w.input(250 * S) and not w.active


def test_phantom_counts_from_start_when_nothing_was_ever_recorded():
    w = PhantomWatch(window_us=120 * S, min_changes=4, started_us=0)
    assert not any(w.focus(t * S) for t in (10, 20, 30, 40))  # too early to say
    # Two minutes of silence since start, and four changes already in the window.
    assert w.focus(130 * S) and w.active


def test_phantom_alerts_the_bar_at_any_phase():
    assert panel_state(False, 0.2, None, phantom=True) == ("alert", 100)
    assert panel_state(False, 0.2, None) == ("learning", 20)


def test_remote_timing_is_judged_over_several_segments():
    w = RemoteTimingWatch(n=3, min_pairs=19, threshold=0.08)
    clean = _typed(1)
    share, pairs = near_simultaneous_share(clean)
    assert share == 0.0 and pairs >= 19
    # Packets landing at once: every other event within the same millisecond.
    recs = []
    for i, r in enumerate(clean.records):
        t = clean.records[i - 1].time_us + 50 if i % 2 else r.time_us
        recs.append(Record(t, r.device, r.virtual, r.event))
    bursty = _seg(sorted(recs, key=lambda r: r.time_us))
    assert near_simultaneous_share(bursty)[0] > 0.3
    assert not w.feed(bursty) and not w.feed(bursty)
    assert w.feed(bursty)
    assert not w.feed(clean) or w.flagged  # the mean decides, not one segment
    w2 = RemoteTimingWatch(n=3)
    assert not any(w2.feed(_typed(s)) for s in range(5))


def test_re_timed_holds_are_more_scattered_than_my_template():
    tpl = KeystrokeTemplate.fit([_typed(s, 80, s * 100 * S) for s in range(8)])
    probe = _typed(42, 80)
    mine, n = hold_dispersion_ratio(probe, tpl)
    jittered, n2 = hold_dispersion_ratio(_retimed(probe, 100), tpl)
    assert n >= 15 and n2 >= 15
    # Clear on a tight synthetic typist; on my own free text the two overlap,
    # which is why this ratio is measured (retiming_check), not used to label.
    assert jittered > 1.5 * mine
    assert hold_dispersion_ratio(_seg(probe.records[:3]), tpl) == (0.0, 0)


def test_retiming_check_rolls_a_mean_over_consecutive_segments():
    from fidus_lab.retiming_check import quantile, rolling

    assert rolling([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]) == [3.0, 4.0]
    assert quantile([3.0, 1.0, 2.0], 1.0) == 3.0


def test_an_input_path_cue_labels_the_segment_like_automation():
    seg = list(segment_trace(Typist(seed=3, **GEN).type_segment(40)))[0]
    reg = SanctionRegistry()
    assert attribute(seg, reg).label == ActorLabel.HUMAN
    a = attribute(seg, reg, input_path="re-timed input")
    assert a.label == ActorLabel.AUTOMATION_UNSANCTIONED and "re-timed input" in a.reason
