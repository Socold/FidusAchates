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
from dataclasses import dataclass
from enum import Enum

from .registry import SanctionRegistry
from .segment import Segment


class ActorLabel(str, Enum):
    HUMAN = "human"
    AUTOMATION_SANCTIONED = "automation_sanctioned"
    AUTOMATION_UNSANCTIONED = "automation_unsanctioned"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class AttributionParams:
    # Below this many events a segment is UNCERTAIN: too little to judge.
    min_events: int = 8
    # A segment is automation if this fraction or more of its events are virtual.
    virtual_fraction: float = 0.5
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
) -> Attribution:
    """Label one segment. Never raises an alarm; that is the policy's job."""
    if segment.n_events < params.min_events:
        return Attribution(ActorLabel.UNCERTAIN, "too few events to judge")

    by_provenance = segment.virtual_fraction >= params.virtual_fraction
    by_timing = _looks_metronomic(segment, params)

    if not (by_provenance or by_timing):
        return Attribution(ActorLabel.HUMAN, "hardware input, human-like timing")

    # It is automation. Sanctioned if any contributing virtual device, or the
    # segment's time, matches the registry. For a metronomic hardware segment
    # (no virtual device), fall back to the segment start time.
    devices = segment.virtual_devices() or segment.devices
    sanctioned = any(registry.is_sanctioned(d, segment.start_us) for d in devices)

    cue = "virtual device" if by_provenance else "metronomic timing"
    if sanctioned:
        return Attribution(
            ActorLabel.AUTOMATION_SANCTIONED, f"automation ({cue}), sanctioned"
        )
    return Attribution(
        ActorLabel.AUTOMATION_UNSANCTIONED, f"automation ({cue}), not sanctioned"
    )
