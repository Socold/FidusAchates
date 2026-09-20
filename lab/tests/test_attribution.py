"""Attribution and the malice policy: the heart of ADR-0011.

The cases that matter: a developer's AI assistant or a user's MCP tool, declared
in the registry, is labelled sanctioned and never alarmed; the same automation
undeclared is tagged, not alarmed; and only identity divergence or a sensitive
action turns a tag into an alert.
"""

from fidus_lab import (
    ActorLabel,
    Outcome,
    Record,
    SanctionRegistry,
    Sensitivity,
    attribute,
    decide,
    segment_trace,
)
from fidus_lab.trace import Event, EventKind


def key(t, device=0, virtual=False):
    return Record(t, device, virtual, Event(kind=EventKind.KEY_DOWN))


def human_typing(n=20, start=0, device=0):
    # Irregular human intervals: 90-180 ms.
    out, t = [], start
    for i in range(n):
        out.append(key(t, device=device))
        t += 90_000 + (i * 37 % 90) * 1000
    return out


def robotic_typing(n=20, start=0, device=9, virtual=True, step=50_000):
    return [key(start + i * step, device=device, virtual=virtual) for i in range(n)]


def one_segment(records):
    segs = list(segment_trace(records))
    assert len(segs) == 1
    return segs[0]


def test_human_hardware_is_labelled_human():
    seg = one_segment(human_typing())
    a = attribute(seg, SanctionRegistry())
    assert a.label == ActorLabel.HUMAN


def test_too_few_events_is_uncertain():
    seg = one_segment(human_typing(n=3))
    assert attribute(seg, SanctionRegistry()).label == ActorLabel.UNCERTAIN


def test_virtual_device_automation_undeclared_is_unsanctioned_but_only_tagged():
    seg = one_segment(robotic_typing())
    a = attribute(seg, SanctionRegistry())
    assert a.label == ActorLabel.AUTOMATION_UNSANCTIONED
    # The core of ADR-0011: automation alone is a tag, not an alert.
    assert decide(a.label, identity_diverged=False, sensitivity=Sensitivity.LOW) == Outcome.TAG


def test_sanctioned_agent_session_makes_it_sanctioned_and_quiet():
    # A developer opens an agent session, then the assistant drives input.
    reg = SanctionRegistry()
    reg.open_session(start_us=0, end_us=10_000_000, note="ai-assistant")
    seg = one_segment(robotic_typing(start=1_000_000))
    a = attribute(seg, reg)
    assert a.label == ActorLabel.AUTOMATION_SANCTIONED
    assert decide(a.label, identity_diverged=False, sensitivity=Sensitivity.LOW) == Outcome.TAG
    # Never an overlay, whatever the (stubbed low) sensitivity.
    assert decide(a.label, identity_diverged=False, sensitivity=Sensitivity.HIGH) != Outcome.ALERT


def test_sanctioned_device_pattern():
    reg = SanctionRegistry()
    reg.sanction_device(9)  # e.g. the assistant's known injection device
    seg = one_segment(robotic_typing(device=9))
    assert attribute(seg, reg).label == ActorLabel.AUTOMATION_SANCTIONED


def test_metronomic_hardware_is_automation_even_without_virtual_flag():
    # A BadUSB is real hardware, so provenance says nothing; timing does.
    seg = one_segment(robotic_typing(virtual=False, device=0, step=40_000))
    assert attribute(seg, SanctionRegistry()).label == ActorLabel.AUTOMATION_UNSANCTIONED


def test_unsanctioned_automation_with_sensitive_action_alerts():
    seg = one_segment(robotic_typing())
    label = attribute(seg, SanctionRegistry()).label
    assert label == ActorLabel.AUTOMATION_UNSANCTIONED
    # Only when the action is sensitive does the tag become an alert.
    assert decide(label, identity_diverged=False, sensitivity=Sensitivity.HIGH) == Outcome.ALERT


def test_identity_divergence_always_alerts():
    # Even a human, if it is a different person.
    assert decide(ActorLabel.HUMAN, identity_diverged=True, sensitivity=Sensitivity.LOW) == Outcome.ALERT
    assert decide(ActorLabel.AUTOMATION_SANCTIONED, identity_diverged=True, sensitivity=Sensitivity.LOW) == Outcome.ALERT
