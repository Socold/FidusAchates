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


class GioOverlay(OverlayClient):
    """Calls the extension through PyGObject's Gio D-Bus proxy: no subprocess
    per call, which the gdbus CLI client needed. Silent if the extension is
    not on the bus."""

    def __init__(self) -> None:
        import gi  # imported here: optional dependency

        gi.require_version("Gio", "2.0")
        gi.require_version("GLib", "2.0")
        from gi.repository import Gio

        self._gio = Gio
        self._proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
            BUS, PATH, BUS, None,
        )

    def _call(self, method: str, variant) -> None:
        try:
            self._proxy.call_sync(method, variant, self._gio.DBusCallFlags.NONE, 500, None)
        except Exception:  # noqa: BLE001  best-effort: the overlay never breaks the pipeline
            pass

    def set_confidence(self, percent: int, channel: str = "Identity") -> None:
        from gi.repository import GLib

        self._call("SetConfidence", GLib.Variant("(us)", (int(percent), channel)))

    def clear(self) -> None:
        self._call("Clear", None)


@dataclass
class ChangeOnly(OverlayClient):
    """Forward a call to the inner client only when the state changes, so a
    steady stream of segments does not hammer the bus (NFR budgets)."""

    inner: OverlayClient
    _last: tuple | None = None

    def set_confidence(self, percent: int, channel: str = "Identity") -> None:
        state = ("set", int(percent), channel)
        if state != self._last:
            self.inner.set_confidence(percent, channel)
            self._last = state

    def clear(self) -> None:
        if self._last != ("clear",):
            self.inner.clear()
            self._last = ("clear",)


def best_overlay() -> OverlayClient:
    """Gio proxy if PyGObject is present, else the gdbus CLI, else null; always
    wrapped so only state changes reach the bus."""
    try:
        return ChangeOnly(GioOverlay())
    except Exception:  # noqa: BLE001  no PyGObject or no session bus
        pass
    g = GdbusOverlay()
    return ChangeOnly(g if g.available() else NullOverlay())
