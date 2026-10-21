"""Split a reduced trace into activity segments.

A segment is a run of activity with no idle gap longer than ``gap_us``, capped
at ``max_us`` so a long continuous session is still cut into windows. Everything
downstream (attribution, and later the CUSUM windows) works on segments, not raw
records, so this is where replay turns a stream into units of judgment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

from .context import ContextEvent
from .trace import EventKind, Record

# Defaults in microseconds: a 2 s gap starts a new segment, a segment spans at
# most 60 s. Both are tuning parameters, revisited with real traces.
DEFAULT_GAP_US = 2_000_000
DEFAULT_MAX_US = 60_000_000


@dataclass
class Segment:
    start_us: int
    end_us: int
    records: list[Record] = field(default_factory=list)
    # Focus changes that happened during the segment (attached by the daemon).
    context: list[ContextEvent] = field(default_factory=list)
    # The application category in focus when the segment ended, None when
    # unknown: what kind of usage the segment is judged in.
    category: int | None = None

    @property
    def duration_us(self) -> int:
        return self.end_us - self.start_us

    @property
    def n_events(self) -> int:
        return len(self.records)

    @property
    def n_virtual(self) -> int:
        return sum(1 for r in self.records if r.virtual)

    @property
    def virtual_fraction(self) -> float:
        return self.n_virtual / self.n_events if self.records else 0.0

    @property
    def devices(self) -> set[int]:
        return {r.device for r in self.records}

    def virtual_devices(self) -> set[int]:
        """Device indices that produced at least one virtual event here."""
        return {r.device for r in self.records if r.virtual}

    def virtual_key_downs(self) -> int:
        """Key-down events from virtual devices. Provenance is judged per
        modality: a burst of injected keystrokes stays visible even when a
        hardware mouse floods the same segment with motion events."""
        return sum(
            1 for r in self.records
            if r.virtual and r.event.kind == EventKind.KEY_DOWN
        )

    def virtual_key_devices(self) -> set[int]:
        return {
            r.device for r in self.records
            if r.virtual and r.event.kind == EventKind.KEY_DOWN
        }

    def key_down_intervals_us(self) -> list[int]:
        """Inter-key-down intervals, the basis of timing-regularity cues."""
        times = [r.time_us for r in self.records if r.event.kind == EventKind.KEY_DOWN]
        return [b - a for a, b in zip(times, times[1:], strict=False)]


def segment_trace(
    records: Iterable[Record],
    gap_us: int = DEFAULT_GAP_US,
    max_us: int = DEFAULT_MAX_US,
) -> Iterator[Segment]:
    """Yield segments from a time-ordered record stream."""
    current: Segment | None = None
    for r in records:
        if current is None:
            current = Segment(start_us=r.time_us, end_us=r.time_us, records=[r])
            continue
        idle = r.time_us - current.end_us
        too_long = r.time_us - current.start_us > max_us
        if idle > gap_us or too_long:
            yield current
            current = Segment(start_us=r.time_us, end_us=r.time_us, records=[r])
        else:
            current.records.append(r)
            current.end_us = r.time_us
    if current is not None:
        yield current


class LiveSegmenter:
    """The streaming form of `segment_trace`, for the live path: records come
    in one by one from the recorder's pipe, and a segment must also close when
    the user simply stops (no next record arrives to reveal the gap), which
    `tick` handles from the clock."""

    def __init__(self, gap_us: int = DEFAULT_GAP_US, max_us: int = DEFAULT_MAX_US) -> None:
        self.gap_us = gap_us
        self.max_us = max_us
        self._current: Segment | None = None

    def feed(self, r: Record) -> Segment | None:
        """Add a record; return the segment it closed, if any."""
        cur = self._current
        if cur is None:
            self._current = Segment(start_us=r.time_us, end_us=r.time_us, records=[r])
            return None
        if r.time_us - cur.end_us > self.gap_us or r.time_us - cur.start_us > self.max_us:
            self._current = Segment(start_us=r.time_us, end_us=r.time_us, records=[r])
            return cur
        cur.records.append(r)
        cur.end_us = r.time_us
        return None

    def tick(self, now_us: int) -> Segment | None:
        """Close the open segment once the idle gap has passed."""
        cur = self._current
        if cur is not None and now_us - cur.end_us > self.gap_us:
            self._current = None
            return cur
        return None
