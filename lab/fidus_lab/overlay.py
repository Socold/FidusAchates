"""Drive the GNOME red-square overlay over D-Bus.

The overlay itself lives in the GNOME Shell extension; this is the client the
console and the live daemon use. It degrades to a no-op when D-Bus or the
extension is absent (a headless run, a machine without the extension), so
nothing here needs the shell to be tested.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

BUS = "org.fidusachates.Overlay"
PATH = "/org/fidusachates/Overlay"


class OverlayClient:
    """Abstract overlay. `set_confidence` and `clear` are the whole surface."""

    def set_confidence(self, percent: int, channel: str = "Identity") -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


@dataclass
class NullOverlay(OverlayClient):
    """Records calls, drives nothing. The default, and what tests use."""

    calls: list[tuple[str, int, str]] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def set_confidence(self, percent: int, channel: str = "Identity") -> None:
        self.calls.append(("set", int(percent), channel))

    def clear(self) -> None:
        self.calls.append(("clear", 0, ""))


class GdbusOverlay(OverlayClient):
    """Calls the extension via the `gdbus` CLI. Silent if it is unavailable."""

    def __init__(self) -> None:
        self._gdbus = shutil.which("gdbus")

    def available(self) -> bool:
        return self._gdbus is not None

    def _call(self, method: str, *args: str) -> None:
        if not self._gdbus:
            return
        cmd = [self._gdbus, "call", "--session", "-d", BUS, "-o", PATH,
               "-m", f"{BUS}.{method}", *args]
        try:
            subprocess.run(cmd, capture_output=True, timeout=2, check=False)
        except (subprocess.SubprocessError, OSError):
            pass  # the overlay is best-effort; never break the pipeline

    def set_confidence(self, percent: int, channel: str = "Identity") -> None:
        self._call("SetConfidence", str(int(percent)), channel)

    def clear(self) -> None:
        self._call("Clear")


def best_overlay() -> OverlayClient:
    """A gdbus-backed overlay if gdbus exists, else a null one."""
    g = GdbusOverlay()
    return g if g.available() else NullOverlay()
