"""Enrolment life cycle and convergence criteria (decision engine section 5).

The end of enrolment is not a duration but four measured criteria, each a
progress in [0, 1]; enrolment ends only when all four reach 1. This module
assesses them and drives the phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .divergence import template_stability
from .experts import KeystrokeTemplate
from .segment import Segment


class Phase(str, Enum):
    BOOTSTRAP = "bootstrap"
    ENROLMENT = "enrolment"
    OPERATIONAL = "operational"


@dataclass(frozen=True)
class CriteriaParams:
    min_keystrokes: int = 2000
    min_sessions: int = 8
    min_days: int = 5
    stability_threshold: float = 0.02   # JS below this = stable
    stability_windows: int = 3
    min_devices: int = 1


@dataclass(frozen=True)
class Convergence:
    volume: float       # C1
    stability: float    # C2
    coverage: float     # C4
    # C3 (held-out performance) is measured by the bench, passed in as done.
    performance: float

    @property
    def ready(self) -> bool:
        return min(self.volume, self.stability, self.coverage, self.performance) >= 1.0

    def phase(self) -> Phase:
        if self.ready:
            return Phase.OPERATIONAL
        if self.volume >= 0.3:
            return Phase.ENROLMENT
        return Phase.BOOTSTRAP


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def assess(
    enrol_sessions: list[list[Segment]],
    stability_history: list[float],
    performance_ok: bool,
    n_keystrokes: int,
    n_days: int,
    n_devices: int,
    params: CriteriaParams = CriteriaParams(),
) -> Convergence:
    """Assess the four criteria from enrolment so far.

    stability_history: recent template-to-template JS values (see
    `rolling_stability`); performance_ok: whether C3 passed on held-out sessions.
    """
    n_sessions = len(enrol_sessions)
    volume = _clip01(min(
        n_keystrokes / params.min_keystrokes,
        n_sessions / params.min_sessions,
    ))
    recent = stability_history[-params.stability_windows:]
    stable = (
        len(recent) >= params.stability_windows
        and all(v < params.stability_threshold for v in recent)
    )
    stability = 1.0 if stable else 0.0
    coverage = _clip01(min(
        n_days / params.min_days,
        n_devices / params.min_devices,
    ))
    performance = 1.0 if performance_ok else 0.0
    return Convergence(volume=volume, stability=stability, coverage=coverage,
                       performance=performance)


def rolling_stability(templates: list[KeystrokeTemplate]) -> list[float]:
    """JS between each consecutive pair of template snapshots."""
    return [template_stability(a, b) for a, b in zip(templates, templates[1:])]


# ---------------------------------------------------------------------------
# A tracker that derives the criteria from the data it is fed, instead of
# trusting caller-supplied counts (review finding: `assess` alone was a
# calculator, not an enrolment).

from .trace import EventKind  # noqa: E402  (kept after the pure functions)

SESSION_GAP_US = 8 * 3600 * 1_000_000  # a break this long starts a new session


@dataclass
class EnrolmentTracker:
    """Feed segments in time order; it counts what the criteria need and keeps
    template snapshots for the stability criterion.

    The trace carries no wall-clock time, so "days" cannot be known from it.
    Sessions separated by at least `session_gap_us` stand in for distinct days;
    a caller with real calendar knowledge may override `n_days`.
    """

    params: CriteriaParams = CriteriaParams()
    session_gap_us: int = SESSION_GAP_US
    snapshot_every: int = 4  # segments between template snapshots

    segments: list[Segment] = None  # type: ignore[assignment]
    snapshots: list[KeystrokeTemplate] = None  # type: ignore[assignment]
    n_keystrokes: int = 0
    n_sessions: int = 0
    devices: set[int] = None  # type: ignore[assignment]
    _last_end_us: int | None = None

    def __post_init__(self) -> None:
        self.segments = []
        self.snapshots = []
        self.devices = set()

    def feed(self, seg: Segment) -> None:
        if self._last_end_us is None or seg.start_us - self._last_end_us >= self.session_gap_us:
            self.n_sessions += 1
        self._last_end_us = seg.end_us
        self.segments.append(seg)
        self.n_keystrokes += sum(
            1 for r in seg.records if r.event.kind == EventKind.KEY_DOWN
        )
        self.devices |= seg.devices
        if len(self.segments) % self.snapshot_every == 0:
            self.snapshots.append(KeystrokeTemplate.fit(self.segments))

    def convergence(self, performance_ok: bool, n_days: int | None = None) -> Convergence:
        return assess(
            enrol_sessions=[[]] * self.n_sessions,
            stability_history=rolling_stability(self.snapshots),
            performance_ok=performance_ok,
            n_keystrokes=self.n_keystrokes,
            n_days=self.n_sessions if n_days is None else n_days,
            n_devices=len(self.devices),
            params=self.params,
        )
