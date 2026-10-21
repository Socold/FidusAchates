"""The live daemon: recorder to engine to indicator, while I work.

    fidus-agent record --trace - | (this process)
        -> today's trace file (or the open guest session's)
        -> live segments -> Identity engine -> console + top-bar indicator

It also listens to the shell extension's `ActivityTick(category)` for the
application context, refits the templates from the stored days every half
hour, and recomputes the learning curves every few hours or on request.

The recorder stays the only process that reads /dev/input, confined and with
no network; this process never sees a key code, only the reduced stream. This
is the research build's live path: the production engine is the Rust port of
work package 7.

The indicator shows "learning" until the enrolment criteria are met, so a
model still learning never paints the bar red; the console shows every score
regardless.
"""

from __future__ import annotations

import argparse
import datetime as dt
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .analyze import SegmentReport
from .attribution import attribute
from .console import Console, publish_link, start
from .context import ContextEvent, ContextTracker
from .enrolment import CriteriaParams, EnrolmentTracker
from .explain import explain
from .learning import Enrolled, Population, learning_curve
from .overlay import best_overlay
from .policy import decide, stub_sensitivity
from .registry import SanctionRegistry
from .segment import LiveSegmenter, Segment
from .storage import GuestSession, Store, default_root
from .trace import Record, read_stream

# A break this long starts a new session: fresh CUSUM, new opening sequence.
NEW_SESSION_IDLE_US = 30 * 60 * 1_000_000
REFIT_EVERY_S = 30 * 60
# While still learning, refit often: the first scores should not wait half an
# hour, and early templates change fast.
REFIT_LEARNING_S = 5 * 60
CURVE_EVERY_S = 3 * 3600
HEARTBEAT_S = 30
# The bar turns red above this, and only once enrolment is complete.
ALERT_ABOVE = 0.5


def now_us() -> int:
    """CLOCK_MONOTONIC, the clock the recorder selects on every device."""
    return time.monotonic_ns() // 1000


def panel_state(ready: bool, progress: float, p_impostor: float | None) -> tuple[str, int]:
    """What the top bar shows: learning until enrolment is complete, then
    recognised, or the alert with its percentage."""
    if not ready:
        return "learning", int(round(progress * 100))
    if p_impostor is not None and p_impostor > ALERT_ABOVE:
        return "alert", int(round(p_impostor * 100))
    return "recognized", 0


@dataclass
class Model:
    enrolled: Enrolled
    population: Population | None
    fitted_at: float
    owner_segments: int


class Daemon:
    def __init__(self, store: Store, agent_cmd: list[str], console: Console,
                 params: CriteriaParams = CriteriaParams()) -> None:
        self.store = store
        self.agent_cmd = agent_cmd
        self.console = console
        self.params = params
        self.overlay = best_overlay()
        self.registry = SanctionRegistry()
        self.segmenter = LiveSegmenter()
        self.context = ContextTracker()
        self._pending_context: list[ContextEvent] = []
        self._records: queue.Queue = queue.Queue(maxsize=100_000)
        self._lock = threading.Lock()
        self._model: Model | None = None
        self._engine = None
        self._guest: GuestSession | None = None
        self._stop = threading.Event()
        self._refit_now = threading.Event()
        self._curve_now = threading.Event()
        self._last_record_us: int | None = None
        self._session_t = 0.0
        self._session_sum = 0.0
        self._last_p: float | None = None
        self._status: dict = {"phase": "starting", "progress": 0.0, "ready": False}
        self._index = 0
        self._register_actions()

    # --- console actions -------------------------------------------------------

    def _register_actions(self) -> None:
        a = self.console.state.actions
        a["guest_start"] = self._guest_start
        a["guest_stop"] = self._guest_stop
        a["guest_delete"] = self._guest_delete
        a["recompute"] = self._recompute

    def _guest_start(self, body: dict) -> dict:
        label = str(body.get("label") or "")
        with self._lock:
            if self._guest is None:
                self._guest = self.store.new_guest(label, consent=body.get("consent") is True)
                # Someone else from here on: the session starts fresh.
                self._new_session()
            gid = self._guest.id
        self._publish_status()
        return {"guest": gid}

    def _guest_stop(self, _body: dict) -> dict:
        with self._lock:
            g, self._guest = self._guest, None
            if g:
                g.close()
                self._new_session()
        self.console.state.set_guests(self.store.guests())
        self._publish_status()
        self._refit_now.set()
        return {"stopped": g.id if g else None}

    def _guest_delete(self, body: dict) -> dict:
        ok = self.store.delete_guest(str(body.get("id", "")))
        self.console.state.set_guests(self.store.guests())
        return {"deleted": ok}

    def _recompute(self, _body: dict) -> dict:
        self._refit_now.set()
        self._curve_now.set()
        return {"queued": True}

    # --- the live path ------------------------------------------------------------

    def _new_session(self) -> None:
        self.context.new_session()
        self._session_t = 0.0
        self._session_sum = 0.0
        if self._engine is not None:
            self._engine.reset()

    def _reader(self, proc: subprocess.Popen) -> None:
        try:
            for r in read_stream(proc.stdout):
                self._records.put(r)
        except ValueError as e:
            print(f"fidus-daemon: bad stream from the recorder: {e}", file=sys.stderr)
        self._records.put(None)

    def on_activity(self, category: str) -> None:
        """Called from the D-Bus thread on every focus change."""
        ev = self.context.tick(now_us(), category)
        if ev is None:
            return
        with self._lock:
            self._pending_context.append(ev)
            if self._guest:
                self._guest.write_context([ev])
            else:
                self.store.write_context([ev])

    def _write(self, r: Record) -> None:
        with self._lock:
            if self._guest:
                self._guest.write([r])
            else:
                self.store.write([r])

    def _close(self, seg: Segment) -> None:
        with self._lock:
            seg.context = [e for e in self._pending_context
                           if seg.start_us <= e.time_us <= seg.end_us]
            self._pending_context = [e for e in self._pending_context
                                     if e.time_us > seg.end_us]
            guest = self._guest.id if self._guest else None
            engine = self._engine
        if engine is None:
            return
        d = engine.step(seg)
        a = attribute(seg, self.registry)
        outcome = decide(a.label, identity_diverged=d.alarmed,
                         sensitivity=stub_sensitivity(seg))
        self._index += 1
        self._session_t += max(seg.duration_us, 0) / 1e6
        self._session_sum += d.evidence_db
        self._last_p = d.p_impostor
        report = SegmentReport(
            index=self._index, n_events=seg.n_events, segment=seg, attribution=a,
            identity_p_impostor=d.p_impostor, identity_alarmed=d.alarmed,
            outcome=outcome, explanation=explain(d.contributions, channel="Identity"),
        )
        if d.alarmed and guest is None:
            # Never learn from a window the engine flagged (threat M10).
            self.store.exclude(seg)
        self.console.state.publish(report, extra={
            "t": round(self._session_t, 1),
            "evidence_db": round(d.evidence_db, 1),
            "session_db": round(self._session_sum, 1),
            "guest": guest,
            "at": dt.datetime.now().strftime("%H:%M:%S"),
        })
        self._push_panel()

    def _push_panel(self, force: bool = False) -> None:
        st = self._status
        state, pct = panel_state(st.get("ready", False), st.get("progress", 0.0), self._last_p)
        self.overlay.set_status(state, pct, force=force)

    def _publish_status(self) -> None:
        with self._lock:
            st = dict(self._status)
            st["guest"] = ({"id": self._guest.id, "label": self._guest.label}
                           if self._guest else None)
        self.console.state.set_status(st)

    # --- background: refit and curves --------------------------------------------

    def _refit(self) -> None:
        segments, days = self.store.load_owner()
        guests = self.store.load_guest_sessions()
        tracker = EnrolmentTracker(params=self.params)
        for s in segments:
            tracker.feed(s)
        enrolled = Enrolled.fit(segments) if segments else None
        population = Population.fit([s for g in guests for s in g]) if guests else None
        curve = self.console.state.learning or {}
        performance_ok = bool(curve.get("ready_at_minutes"))
        conv = tracker.convergence(performance_ok=performance_ok,
                                   n_days=len(set(days)) if days else 0)
        progress = (conv.volume + conv.stability + conv.coverage + conv.performance) / 4
        with self._lock:
            if enrolled is not None:
                self._model = Model(enrolled, population, time.time(), len(segments))
                self._engine = enrolled.engine(population)
            self._status = {
                "curve_kind": curve.get("impostor_kind"),
                "phase": conv.phase().value,
                "ready": conv.ready,
                "progress": round(progress, 3),
                "criteria": {"volume": conv.volume, "stability": conv.stability,
                             "coverage": conv.coverage, "performance": conv.performance},
                "owner_segments": len(segments),
                "owner_keystrokes": tracker.n_keystrokes,
                "days": len(set(days)),
                "guests": len(guests),
                "population_reference": population is not None,
                "fitted_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        self._publish_status()
        self.console.state.set_guests(self.store.guests())
        self._push_panel()

    def _curve(self) -> None:
        segments, days = self.store.load_owner()
        guests = self.store.load_guest_sessions()
        curve = learning_curve(segments, guests, days=days, params=self.params)
        d = curve.as_dict()
        d["computed_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.console.state.set_learning(d)

    def _background(self) -> None:
        next_refit = 0.0
        next_curve = time.time() + 600  # let a few refits land first
        while not self._stop.is_set():
            t = time.time()
            try:
                if t >= next_refit or self._refit_now.is_set():
                    self._refit_now.clear()
                    self.store.prune()
                    self._refit()
                    ready = self._status.get("ready", False)
                    next_refit = t + (REFIT_EVERY_S if ready else REFIT_LEARNING_S)
                if t >= next_curve or self._curve_now.is_set():
                    self._curve_now.clear()
                    self._curve()
                    next_curve = t + CURVE_EVERY_S
                    self._refit()  # C3 may have just been met
            except Exception as e:  # noqa: BLE001  the live path must survive a bad fit
                print(f"fidus-daemon: background step failed: {e!r}", file=sys.stderr)
            self._stop.wait(5)

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_S):
            self._push_panel(force=True)

    # --- main --------------------------------------------------------------------

    def run(self) -> int:
        proc = subprocess.Popen(self.agent_cmd, stdout=subprocess.PIPE, bufsize=0)
        threading.Thread(target=self._reader, args=(proc,), daemon=True).start()
        threading.Thread(target=self._background, daemon=True).start()
        threading.Thread(target=self._heartbeat, daemon=True).start()
        start_activity_listener(self.on_activity)
        self._new_session()
        self.overlay.set_status("learning", 0)
        last_flush = time.time()
        try:
            while True:
                try:
                    r = self._records.get(timeout=0.5)
                except queue.Empty:
                    r = False
                if r is None:
                    print("fidus-daemon: the recorder stopped", file=sys.stderr)
                    return proc.wait() or 1
                if r:
                    if (self._last_record_us is not None
                            and r.time_us - self._last_record_us > NEW_SESSION_IDLE_US):
                        self._new_session()
                    self._last_record_us = r.time_us
                    self._write(r)
                    closed = self.segmenter.feed(r)
                else:
                    closed = self.segmenter.tick(now_us())
                if closed is not None:
                    self._close(closed)
                if time.time() - last_flush > 2:
                    with self._lock:
                        self.store.flush()
                        if self._guest:
                            self._guest.trace.flush()
                    last_flush = time.time()
        except KeyboardInterrupt:
            return 0
        finally:
            self._stop.set()
            proc.terminate()
            with self._lock:
                self.store.flush()
                if self._guest:
                    self._guest.close()
            self.overlay.set_status("off", 0, force=True)


def start_activity_listener(callback) -> bool:
    """Subscribe to the extension's ActivityTick on a GLib loop in its own
    thread. Without PyGObject or the extension, context simply stays empty."""
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
    except (ImportError, ValueError):
        return False

    def on_signal(_conn, _sender, _path, _iface, _signal, params):
        try:
            callback(params.unpack()[0])
        except Exception:  # noqa: BLE001  a bad tick must not kill the loop
            pass

    def loop() -> None:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.signal_subscribe(None, "org.fidusachates.Overlay", "ActivityTick",
                             "/org/fidusachates/Overlay", None,
                             Gio.DBusSignalFlags.NONE, on_signal)
        GLib.MainLoop().run()

    threading.Thread(target=loop, daemon=True).start()
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.daemon")
    ap.add_argument("--agent", default=str(Path.home() / ".local/bin/fidus-agent"),
                    help="the recorder binary (research-trace build)")
    ap.add_argument("--layout", default="qwerty", choices=("qwerty", "azerty"))
    ap.add_argument("--data", default=str(default_root()))
    ap.add_argument("--retention-days", type=int, default=30)
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args(argv)

    store = Store(Path(args.data), retention_days=args.retention_days)
    console = start(port=args.port, rearm=True)
    link = publish_link(console)
    threading.Thread(target=console.serve_forever, daemon=True).start()
    print(f"fidus-daemon: console link in {link}", file=sys.stderr)
    cmd = [args.agent, "record", "--trace", "-", "--layout", args.layout]
    return Daemon(store, cmd, console).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
