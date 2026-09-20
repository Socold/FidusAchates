"""The malice policy (ADR-0011, decision engine 4.4/4.4b).

Attribution says who acts; this says whether to worry. It is deliberately the
only place that turns a label into an alarm, so the leap from "automated" to
"hostile" is explicit and inspectable.

Sensitivity is the future link to command-category signals (FR-47). Until that
work package lands it is a stub returning LOW, so unsanctioned automation is
tagged, not alarmed. Wiring the real signal replaces `stub_sensitivity`, nothing
else.
"""

from __future__ import annotations

from enum import Enum, IntEnum

from .attribution import ActorLabel
from .segment import Segment


class Sensitivity(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


class Outcome(str, Enum):
    NONE = "none"      # nothing to show
    TAG = "tag"        # shown and logged, no overlay
    ALERT = "alert"    # overlay / decision event


def stub_sensitivity(_segment: Segment) -> Sensitivity:
    """Placeholder until command-category correlation exists (WP 9)."""
    return Sensitivity.LOW


def decide(
    label: ActorLabel,
    identity_diverged: bool,
    sensitivity: Sensitivity,
) -> Outcome:
    """Combine attribution, identity and action sensitivity into an outcome.

    Rules (ADR-0011):
    - identity divergence always alerts, human or automated;
    - unsanctioned automation alerts only in a sensitive context;
    - unsanctioned automation otherwise is tagged;
    - sanctioned automation is tagged (shown), never alerted;
    - human, conforming, is nothing.
    """
    if identity_diverged:
        return Outcome.ALERT
    if label == ActorLabel.AUTOMATION_UNSANCTIONED:
        if sensitivity >= Sensitivity.HIGH:
            return Outcome.ALERT
        return Outcome.TAG
    if label == ActorLabel.AUTOMATION_SANCTIONED:
        return Outcome.TAG
    return Outcome.NONE
