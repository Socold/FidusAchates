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
