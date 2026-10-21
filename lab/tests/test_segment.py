from fidus_lab import Record, segment_trace
from fidus_lab.trace import Event, EventKind


def rec(t, device=0, virtual=False):
    return Record(
        time_us=t,
        device=device,
        virtual=virtual,
        event=Event(kind=EventKind.KEY_DOWN),
    )


def test_idle_gap_splits_segments():
    records = [rec(0), rec(100_000), rec(200_000), rec(5_000_000), rec(5_100_000)]
    segs = list(segment_trace(records, gap_us=2_000_000))
    assert len(segs) == 2
    assert segs[0].n_events == 3
    assert segs[1].n_events == 2


def test_max_duration_caps_a_segment():
    # Continuous activity every 0.5 s for 70 s, cap at 60 s.
    records = [rec(t) for t in range(0, 70_000_000, 500_000)]
    segs = list(segment_trace(records, gap_us=2_000_000, max_us=60_000_000))
    assert len(segs) == 2


def test_virtual_fraction_and_devices():
    records = [rec(0, device=1), rec(10, device=9, virtual=True), rec(20, device=9, virtual=True)]
    seg = next(segment_trace(records))
    assert abs(seg.virtual_fraction - 2 / 3) < 1e-9
    assert seg.virtual_devices() == {9}


def test_live_segmenter_matches_offline_and_closes_on_idle():
    from fidus_lab.segment import LiveSegmenter
    from fidus_lab.trace import Event, EventKind, Record

    times = [0, 100, 200, 5_000_000, 5_000_100, 12_000_000]
    recs = [Record(t, 0, False, Event(EventKind.WHEEL, dy=1)) for t in times]
    live = LiveSegmenter()
    closed = [s for s in (live.feed(r) for r in recs) if s is not None]
    assert live.tick(12_000_100) is None          # still within the gap
    tail = live.tick(12_000_000 + 3_000_000)
    assert tail is not None
    closed.append(tail)
    offline = list(segment_trace(recs))
    assert [(s.start_us, s.end_us, s.n_events) for s in closed] == \
        [(s.start_us, s.end_us, s.n_events) for s in offline]
