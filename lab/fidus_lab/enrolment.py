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
