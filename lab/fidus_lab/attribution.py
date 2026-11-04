"""Actor attribution (ADR-0011): a label per segment, never a verdict.

This is the first pass of the Attribution channel. It answers "human or
automation, and if automation, sanctioned or not?" and nothing else. Whether
automation is a problem is decided by the malice policy, not here.

Version 1 uses provenance (virtual vs hardware devices) as the primary cue,
plus one timing cue (under-dispersion: a metronome regularity no human has).
The richer family-E signals come with the signal study (work package 4); this
module is written so adding them changes the score, not the shape.
"""

from __future__ import annotations

import statistics
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from .registry import SanctionRegistry
from .segment import Segment
from .trace import EventKind


class ActorLabel(str, Enum):
    HUMAN = "human"
    AUTOMATION_SANCTIONED = "automation_sanctioned"
    AUTOMATION_UNSANCTIONED = "automation_unsanctioned"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class AttributionParams:
    # Below this many events a segment is UNCERTAIN: too little to judge.
    min_events: int = 8
    # A segment is automation if this fraction or more of its events are virtual
    # (the whole-segment cue), OR if at least `min_virtual_key_downs`
    # keystrokes came from a virtual device (the per-modality cue, which a
    # hardware mouse cannot dilute).
    virtual_fraction: float = 0.5
    min_virtual_key_downs: int = 5
    # Or if key-down intervals are this regular (coefficient of variation below
    # the threshold): a human's typing is never that even.
    max_cv_for_machine: float = 0.05
    min_intervals_for_cv: int = 6


@dataclass(frozen=True)
class Attribution:
    label: ActorLabel
    # Why, in a few words, for the console and the logs.
    reason: str


def _looks_metronomic(segment: Segment, params: AttributionParams) -> bool:
    intervals = segment.key_down_intervals_us()
    if len(intervals) < params.min_intervals_for_cv:
        return False
    mean = statistics.fmean(intervals)
    if mean <= 0:
        return False
    cv = statistics.pstdev(intervals) / mean
    return cv < params.max_cv_for_machine


def attribute(
    segment: Segment,
    registry: SanctionRegistry,
    params: AttributionParams = AttributionParams(),
    input_path: str | None = None,
) -> Attribution:
    """Label one segment. Never raises an alarm; that is the policy's job.
    `input_path` names a cue kept across segments that something sits between
    my hands and the recorder, today "remote session timing"
    (`RemoteTimingWatch`, E11). The input is then not my hand's own,
    sanctioned or not, so it is labelled like automation."""
    if segment.n_events < params.min_events:
        return Attribution(ActorLabel.UNCERTAIN, "too few events to judge")

    by_provenance = (
        segment.virtual_fraction >= params.virtual_fraction
        or segment.virtual_key_downs() >= params.min_virtual_key_downs
    )
    by_timing = _looks_metronomic(segment, params)

    if not (by_provenance or by_timing or input_path):
        return Attribution(ActorLabel.HUMAN, "hardware input, human-like timing")

    # It is automation. Sanctioned if any contributing virtual device, or the
    # segment's time, matches the registry. For a metronomic hardware segment
    # (no virtual device), fall back to the segment start time.
    devices = (
        segment.virtual_key_devices() or segment.virtual_devices() or segment.devices
    )
    sanctioned = any(registry.is_sanctioned(d, segment.start_us) for d in devices)

    cue = ("virtual device" if by_provenance
           else "metronomic timing" if by_timing else input_path)
    if sanctioned:
        return Attribution(
            ActorLabel.AUTOMATION_SANCTIONED, f"automation ({cue}), sanctioned"
        )
    return Attribution(
        ActorLabel.AUTOMATION_UNSANCTIONED, f"automation ({cue}), not sanctioned"
    )


@dataclass
class PhantomWatch:
    """E20, phantom activity: the shell keeps reporting focus changes while no
    input at all reaches the recorder. Something is driving the session
    without going through the devices I read: a tool that grabs the keyboard
    and re-injects through the compositor (kloak, research/articles/
    2026-11-04-kloak.md), a remote-desktop session, a portal-driven agent.

    Focus can change with no input (a dialog opening, a command launching a
    browser), so one change proves nothing; `min_changes` within `window_us`
    while the recorder has been silent for the whole window does. Input
    counts before the secret-input filter: keys withheld at the lock screen
    were still typed on my keyboard. Called from two threads, hence the lock.
    """

    window_us: int = 120_000_000
    min_changes: int = 4
    started_us: int = 0
    active: bool = False
    _last_input_us: int | None = None
    _changes: deque = field(default_factory=deque)
    _mutex: threading.Lock = field(default_factory=threading.Lock)

    def input(self, t_us: int) -> bool:
        """Any recorded event. Returns True if this ends a phantom episode."""
        with self._mutex:
            self._last_input_us = t_us
            self._changes.clear()
            ended, self.active = self.active, False
            return ended

    def focus(self, t_us: int) -> bool:
        """A focus change reported by the shell. Returns True if this starts
        a phantom episode."""
        with self._mutex:
            self._changes.append(t_us)
            while self._changes and self._changes[0] < t_us - self.window_us:
                self._changes.popleft()
            last = self._last_input_us if self._last_input_us is not None else self.started_us
            quiet = t_us - last >= self.window_us
            hit = quiet and len(self._changes) >= self.min_changes
            started = hit and not self.active
            self.active = self.active or hit
            return started

    def describe(self) -> str:
        return (f"{self.min_changes} or more focus changes in "
                f"{self.window_us // 60_000_000} min with no input reaching the recorder")


def near_simultaneous_share(segment: Segment, gap_us: int = 1000) -> tuple[float, int]:
    """Share of consecutive key events (downs and ups) less than `gap_us`
    apart, and the number of pairs. A keyboard puts two events in the same
    report now and then (2.3 % of pairs on my own traces); a remote hop over a
    jittery path lands whole packets at once."""
    ts = [r.time_us for r in segment.records
          if r.event.kind in (EventKind.KEY_DOWN, EventKind.KEY_UP)]
    pairs = len(ts) - 1
    if pairs <= 0:
        return 0.0, 0
    return sum((b - a) < gap_us for a, b in zip(ts, ts[1:], strict=False)) / pairs, pairs


@dataclass
class RemoteTimingWatch:
    """E11, remote session timing, over the last `n` segments with at least
    `min_pairs` key-event pairs. Calibrated on 12 days of my own traces (the
    rolling mean never went above 0.058) and on a simulated remote-desktop hop
    (research/results/2026-11-04-input-paths): at 0.08 a 150 ms path is
    flagged in 80 % of windows, a 40 ms path in 4 %, a LAN never. The signal
    is blind to a short path, and to remote input that never reaches evdev
    (Wayland remote desktop: E20, E21)."""

    n: int = 8
    min_pairs: int = 19
    threshold: float = 0.08
    _shares: deque = field(default_factory=deque)

    def feed(self, segment: Segment) -> bool:
        share, pairs = near_simultaneous_share(segment)
        if pairs >= self.min_pairs:
            self._shares.append(share)
            while len(self._shares) > self.n:
                self._shares.popleft()
        return self.flagged

    @property
    def flagged(self) -> bool:
        return (len(self._shares) == self.n
                and sum(self._shares) / self.n > self.threshold)
