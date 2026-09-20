"""The sanctioned-actor registry (FR-39, ADR-0011).

Lets the user declare automation they expect: an AI coding assistant, an MCP
tool, a scripted task of their own. Declared automation is labelled
``automation_sanctioned`` and never, on its own, alarmed.

It stores as little as possible: device indices known to be sanctioned virtual
devices, and time-boxed "agent sessions" the user opens when handing control to
an assistant. Never what the actor did.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSession:
    """A window during which the user delegated control to an agent."""

    start_us: int
    end_us: int
    note: str = ""  # a human label like "copilot" or "mcp:files"; never content

    def covers(self, time_us: int) -> bool:
        return self.start_us <= time_us <= self.end_us


@dataclass
class SanctionRegistry:
    # Virtual-device indices the user has marked as sanctioned automation
    # (for example a remapper, or an assistant's injection device).
    sanctioned_devices: set[int] = field(default_factory=set)
    sessions: list[AgentSession] = field(default_factory=list)

    def sanction_device(self, device: int) -> None:
        self.sanctioned_devices.add(device)

    def open_session(self, start_us: int, end_us: int, note: str = "") -> AgentSession:
        s = AgentSession(start_us, end_us, note)
        self.sessions.append(s)
        return s

    def is_sanctioned(self, device: int, time_us: int) -> bool:
        """True if this device, at this time, is sanctioned automation."""
        if device in self.sanctioned_devices:
            return True
        return any(s.covers(time_us) for s in self.sessions)
