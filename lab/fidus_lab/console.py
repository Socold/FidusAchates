"""Local administration console (FR-50 to FR-58, SR-9).

A standard-library HTTP server bound to 127.0.0.1 that streams the analysis of
a trace (or of the live daemon) over Server-Sent Events: the decisions as they
come, the enrolment status, and the learning curves.

A local web server is reachable by any page in the browser, so (SR-9): it
validates Host and Origin (anti-DNS-rebinding), sends no cross-origin headers,
and keeps the session in an HttpOnly, SameSite=Strict cookie, never in the URL.
The only thing that ever travels in a URL is a one-time bootstrap link, consumed
on first use, so a leak into browser history is harmless. The daemon re-arms a
fresh link after each use and leaves it in a 0600 file in the runtime directory,
where the shell indicator reads it. State-changing requests are POSTs that must
carry a loopback Origin as well as the session cookie.

The pure pieces (SSE framing, the host check, the state snapshot) are unit
tested; a smoke test binds an ephemeral port and fetches a page.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from .analyze import SegmentReport

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
COOKIE_NAME = "fidus_session"


def sse(event: str, data: dict) -> bytes:
    """Format one Server-Sent Event."""
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


def host_is_local(host_header: str | None) -> bool:
    """True if the Host header names the loopback (SR-9, anti-rebinding)."""
    if not host_header:
        return False
    host = host_header.rsplit(":", 1)[0].strip("[]")
    return host in ALLOWED_HOSTS


def segment_snapshot(r: SegmentReport, extra: dict | None = None) -> dict:
    return (extra or {}) | {
        "index": r.index,
        "events": r.n_events,
        "actor": r.attribution.label.value,
        "actor_reason": r.attribution.reason,
        "p_impostor": round(r.identity_p_impostor, 3),
        "alarmed": r.identity_alarmed,
        "outcome": r.outcome.value,
        "explanation": r.explanation.as_text(),
    }


@dataclass
class ConsoleState:
    """What the console shows, updated as segments are analysed."""

    segments: list[dict] = field(default_factory=list)
    max_p_impostor: float = 0.0
    outcomes: dict[str, int] = field(default_factory=dict)
    profile_count: int = 0
    # Live daemon only: enrolment status, learning curve, guest sessions.
    status: dict = field(default_factory=dict)
    learning: dict | None = None
    guests: list = field(default_factory=list)
    # The daemon's history over the retention period, and the hour in progress.
    history: list = field(default_factory=list)
    live_hour: dict | None = None
    # Actions the console may trigger, registered by the daemon.
    actions: dict[str, Callable[[dict], dict]] = field(default_factory=dict)
    max_segments: int = 600
    _subscribers: list["_Queue"] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def publish(self, report: SegmentReport, extra: dict | None = None) -> None:
        snap = segment_snapshot(report, extra)
        with self._lock:
            self.segments.append(snap)
            del self.segments[:-self.max_segments]
            self.max_p_impostor = max(self.max_p_impostor, snap["p_impostor"])
            self.outcomes[snap["outcome"]] = self.outcomes.get(snap["outcome"], 0) + 1
            subs = list(self._subscribers)
        for q in subs:
            q.put(sse("segment", snap))

    def set_profiles(self, n: int) -> None:
        with self._lock:
            self.profile_count = n
            subs = list(self._subscribers)
        for q in subs:
            q.put(sse("profiles", {"count": n}))

    def _broadcast(self, event: str, data: dict) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            q.put(sse(event, data))

    def set_status(self, status: dict) -> None:
        with self._lock:
            self.status = dict(status)
        self._broadcast("status", status)

    def set_learning(self, learning: dict | None) -> None:
        with self._lock:
            self.learning = learning
        self._broadcast("learning", learning or {})

    def set_guests(self, guests: list) -> None:
        with self._lock:
            self.guests = list(guests)
        self._broadcast("guests", {"guests": guests})

    def set_history(self, lines: list) -> None:
        with self._lock:
            self.history = list(lines)
        self._broadcast("history", {"lines": lines})

    def add_history(self, line: dict) -> None:
        with self._lock:
            self.history.append(line)
        self._broadcast("history_line", line)

    def set_live_hour(self, line: dict | None) -> None:
        with self._lock:
            self.live_hour = line
        self._broadcast("live_hour", line or {})

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "segments": list(self.segments),
                "max_p_impostor": self.max_p_impostor,
                "outcomes": dict(self.outcomes),
                "profile_count": self.profile_count,
                "status": dict(self.status),
                "learning": self.learning,
                "guests": list(self.guests),
                "history": list(self.history),
                "live_hour": self.live_hour,
            }

    def subscribe(self) -> "_Queue":
        q = _Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "_Queue") -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


class _Queue:
    def __init__(self) -> None:
        self._items: list[bytes] = []
        self._cv = threading.Condition()

    def put(self, item: bytes) -> None:
        with self._cv:
            self._items.append(item)
            self._cv.notify()

    def get(self, timeout: float) -> bytes | None:
        with self._cv:
            if not self._items:
                self._cv.wait(timeout)
            return self._items.pop(0) if self._items else None


def render_page(initial: dict | None = None) -> str:
    """The page, with the current state inlined so it paints at once instead
    of waiting for the event stream. `</` is escaped so no value can close the
    script element."""
    blob = json.dumps(initial or {}).replace("</", "<\\/")
    return _PAGE.replace("/*INITIAL*/{}", blob)


def make_handler(bootstrap: "Bootstrap", session: str, state: ConsoleState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):  # quiet
            pass

        def _reject(self, code: int, msg: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(msg.encode())

        def _local_and_same_origin(self) -> bool:
            if not host_is_local(self.headers.get("Host")):
                return False
            origin = self.headers.get("Origin")
            if origin and not host_is_local(urlparse(origin).hostname):
                return False
            return True

        def _has_session(self) -> bool:
            cookie = self.headers.get("Cookie", "")
            for part in cookie.split(";"):
                k, _, v = part.strip().partition("=")
                if k == COOKIE_NAME and secrets.compare_digest(v, session):
                    return True
            return False

        def do_GET(self):
            url = urlparse(self.path)
            route = url.path
            if not self._local_and_same_origin():
                return self._reject(403, "forbidden")

            # One-time bootstrap: consumes the link, sets the cookie, redirects.
            if route == "/login":
                t = parse_qs(url.query).get("t", [""])[0]
                if not bootstrap.consume(t):
                    return self._reject(403, "invalid or already used link")
                self.send_response(302)
                self.send_header(
                    "Set-Cookie",
                    f"{COOKIE_NAME}={session}; HttpOnly; SameSite=Strict; Path=/",
                )
                self.send_header("Location", "/")
                self.end_headers()
                return

            if not self._has_session():
                return self._reject(403, "no session")

            if route == "/":
                body = render_page(state.snapshot()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)
            elif route == "/api/state":
                body = json.dumps(state.snapshot()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif route == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q = state.subscribe()
                try:
                    self.wfile.write(sse("hello", state.snapshot()))
                    self.wfile.flush()
                    while True:
                        item = q.get(timeout=15)
                        self.wfile.write(item if item else b": keepalive\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    state.unsubscribe(q)
            else:
                self._reject(404, "not found")

        def do_POST(self):
            # A state change needs all three: loopback Host, a loopback Origin
            # (a browser always sends one on a POST, so a missing one is not a
            # browser we trust), and the session cookie.
            if not self._local_and_same_origin() or not self.headers.get("Origin"):
                return self._reject(403, "forbidden")
            if not self._has_session():
                return self._reject(403, "no session")
            route = urlparse(self.path).path
            name = route.removeprefix("/api/action/")
            action = state.actions.get(name) if route.startswith("/api/action/") else None
            if action is None:
                return self._reject(404, "not found")
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 4096)
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("body must be an object")
                result = action(body)
            except (ValueError, KeyError) as e:
                return self._reject(400, str(e))
            out = json.dumps(result or {}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

    return Handler


class Bootstrap:
    """A one-time login token. Valid until consumed exactly once. With
    `rearm`, a fresh token replaces it on use and `on_new` is told, so the
    indicator always has a link to open and no link ever works twice."""

    def __init__(self, rearm: bool = False,
                 on_new: Callable[[str], None] | None = None) -> None:
        self._token: str | None = secrets.token_urlsafe(24)
        self._lock = threading.Lock()
        self._rearm = rearm
        self.on_new = on_new

    @property
    def token(self) -> str | None:
        return self._token

    def consume(self, presented: str) -> bool:
        with self._lock:
            if self._token is None or not presented:
                return False
            ok = secrets.compare_digest(presented, self._token)
            if ok:
                self._token = secrets.token_urlsafe(24) if self._rearm else None
                if self._token and self.on_new:
                    self.on_new(self._token)
            return ok


@dataclass
class Console:
    state: ConsoleState
    server: ThreadingHTTPServer
    bootstrap: Bootstrap
    session: str

    @property
    def url(self) -> str:
        """The one-time login link. Open it once; it then stops working."""
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}/login?t={self.bootstrap.token}"

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()


def start(host: str = "127.0.0.1", port: int = 0, rearm: bool = False) -> Console:
    """Start the console on the loopback. Port 0 picks a free port."""
    bootstrap = Bootstrap(rearm=rearm)
    session = secrets.token_urlsafe(32)
    state = ConsoleState()
    server = ThreadingHTTPServer((host, port), make_handler(bootstrap, session, state))
    return Console(state=state, server=server, bootstrap=bootstrap, session=session)


def link_file() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / "fidusachates" / "console-link"


def publish_link(console: Console, path: Path | None = None) -> Path:
    """Write the current one-time link where the shell indicator reads it,
    readable by me only, and keep it current as links are used."""
    path = path or link_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def write(_token: str | None = None) -> None:
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(console.url + "\n")
        os.replace(tmp, path)

    console.bootstrap.on_new = write
    write()
    return path


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FidusAchates console</title>
<style>
 :root{color-scheme:dark;
  --surface-0:#111110;--surface-1:#1a1a19;--border:#2e2e2c;
  --text-primary:#f0efec;--text-secondary:#c3c2b7;--text-muted:#8d8c83;
  --grid:#2a2a28;--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;
  --good:#3fb950;--critical:#e5534b;--warning:#d29922;--neutral:#8d8c83}
 *{box-sizing:border-box}
 body{font:14px/1.5 system-ui,sans-serif;margin:0;background:var(--surface-0);color:var(--text-primary)}
 header{padding:12px 20px;background:var(--surface-1);border-bottom:1px solid var(--border);
  display:flex;gap:20px;align-items:center;flex-wrap:wrap}
 h1{font-size:16px;margin:0}
 h2{font-size:14px;margin:0 0 4px}
 nav button{background:none;border:0;color:var(--text-secondary);font:inherit;padding:6px 10px;
  border-radius:6px;cursor:pointer}
 nav button.on{background:var(--border);color:var(--text-primary)}
 main{padding:20px;max-width:1200px;margin:0 auto}
 .grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
 .card{background:var(--surface-1);border:1px solid var(--border);border-radius:8px;padding:16px;min-width:0}
 .sub{color:var(--text-muted);font-size:12px;margin:0 0 8px}
 .hero{font-size:32px;font-weight:600;margin:4px 0}
 .pill{display:inline-flex;gap:6px;align-items:center;padding:2px 10px;border-radius:999px;
  border:1px solid var(--border);font-size:12px;color:var(--text-secondary)}
 .dot{width:8px;height:8px;border-radius:50%;display:inline-block}
 .bar{height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin:4px 0 10px}
 .bar > i{display:block;height:100%;background:var(--series-1);border-radius:3px}
 table{width:100%;border-collapse:collapse;font-size:13px}
 td,th{padding:4px 8px;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}
 th{color:var(--text-muted);font-weight:500}
 .scroll{overflow-x:auto}
 .note{color:var(--warning);font-size:13px}
 .muted{color:var(--text-muted)}
 svg text{fill:var(--text-muted);font-size:11px}
 .tip{position:fixed;pointer-events:none;background:#000d;border:1px solid var(--border);
  padding:6px 8px;border-radius:6px;font-size:12px;display:none;z-index:9;white-space:pre}
 .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--text-secondary);margin-top:6px}
 .legend span{display:inline-flex;align-items:center;gap:6px}
 .legend i{width:14px;height:2px;display:inline-block}
 button.act{background:var(--series-1);color:#fff;border:0;border-radius:6px;padding:6px 12px;
  font:inherit;cursor:pointer}
 button.act.stop{background:var(--critical)}
 button.link{background:none;border:0;color:var(--text-muted);cursor:pointer;font:inherit;text-decoration:underline}
 input{background:var(--surface-0);border:1px solid var(--border);color:var(--text-primary);
  border-radius:6px;padding:6px 8px;font:inherit}
 .hidden{display:none}
 td.reasons{white-space:normal;min-width:280px}
 .out-alert{color:var(--critical);font-weight:600}.out-tag{color:var(--warning)}
</style></head><body>
<header><h1>FidusAchates</h1>
 <nav><button data-tab="now" class="on">Now</button><button data-tab="timeline">Timeline</button>
 <button data-tab="learning">Learning</button><button data-tab="guests">Guests</button></nav>
 <span id="state-pill" class="pill"><i class="dot" style="background:var(--neutral)"></i>waiting</span>
</header>
<main>
<section id="tab-now">
 <div id="guest-banner" class="card hidden" style="border-color:var(--warning);margin-bottom:16px">
  Guest session running: <b id="guest-name"></b>. This activity is recorded as someone else and never
  enrols. <button class="act stop" onclick="act('guest_stop')">Stop guest session</button></div>
 <div class="grid">
  <div class="card"><h2>Status</h2><p class="sub" id="phase-line">waiting for the first fit</p>
   <div class="hero" id="hero-state">-</div>
   <div id="criteria"></div></div>
  <div class="card"><h2>Someone else? This session</h2>
   <p class="sub">Probability that the person at the keyboard is not me, per window, over active time</p>
   <div id="ch-p"></div></div>
  <div class="card"><h2>Recognition, this session</h2>
   <p class="sub">Evidence summed since the session started; below -20 dB counts as recognised</p>
   <div id="ch-e"></div></div>
 </div>
 <div class="card" style="margin-top:16px"><h2>Recent windows</h2>
  <div class="scroll"><table><thead><tr><th>time</th><th>events</th><th>actor</th>
  <th>P(someone else)</th><th>evidence</th><th>outcome</th><th>main reasons</th></tr></thead>
  <tbody id="rows"></tbody></table></div></div>
</section>
<section id="tab-timeline" class="hidden">
 <div style="margin-bottom:12px"><span class="muted">Range </span><nav style="display:inline">
  <button class="range" data-range="1">24 h</button><button class="range" data-range="7">7 days</button>
  <button class="range on" data-range="30">30 days</button></nav>
  <span class="muted" id="tl-note"></span></div>
 <div class="grid">
  <div class="card"><h2>Learning</h2>
   <p class="sub">Overall progress and each enrolment criterion, after every refit</p><div id="tl-learn"></div></div>
  <div class="card"><h2>Is it me? Hour by hour</h2>
   <p class="sub">Mean recognition confidence, and the highest probability of someone else, per hour of activity</p>
   <div id="tl-conf"></div></div>
  <div class="card"><h2>Alarms</h2>
   <p class="sub">Windows the engine alarmed on, per day (on me, these are false alarms)</p><div id="tl-alarms"></div></div>
  <div class="card"><h2>Drift of my model</h2>
   <p class="sub">How far the current model is from itself a day ago, a week ago, and the oldest day kept
   (Jensen-Shannon, 0 = same). Measured only, no alert yet: my own drift sets the future threshold</p>
   <div id="tl-drift"></div></div>
  <div class="card"><h2>Keystrokes enrolled</h2>
   <p class="sub">Keystrokes in the templates at each refit, within the retention period</p><div id="tl-keys"></div></div>
  <div class="card"><h2>Measured performance</h2>
   <p class="sub">From each learning curve: false alarms per hour on me, and the share of someone else caught</p>
   <div id="tl-perf"></div></div>
  <div class="card"><h2>Time to recognise me</h2>
   <p class="sub">From each learning curve: median seconds of my activity before -20 dB</p><div id="tl-ttr"></div></div>
 </div>
</section>
<section id="tab-learning" class="hidden">
 <div class="grid">
  <div class="card"><h2>When does it know me?</h2><div class="hero" id="ready-hero">-</div>
   <p class="sub" id="ready-sub"></p><p class="note" id="curve-note"></p>
   <button class="act" onclick="act('recompute')">Recompute now</button>
   <span class="muted" id="curve-time"></span></div>
  <div class="card"><h2>Enrolment criteria</h2>
   <p class="sub">Progress of each criterion against the active time enrolled (log scale)</p>
   <div id="ch-crit"></div></div>
 </div>
 <div class="grid" style="margin-top:16px">
  <div class="card"><h2>Someone else caught</h2>
   <p class="sub">Share of the other person's sessions detected, by minutes of my activity enrolled</p>
   <div id="ch-det"></div></div>
  <div class="card"><h2>Time to catch someone else</h2>
   <p class="sub">Median seconds of their activity before the alarm</p><div id="ch-ttd"></div></div>
  <div class="card"><h2>Time to recognise me</h2>
   <p class="sub">Median seconds of my activity before -20 dB, in a fresh session</p><div id="ch-ttr"></div></div>
  <div class="card"><h2>False alarms on me</h2>
   <p class="sub">Alarms per hour of my own held-out activity</p><div id="ch-fa"></div></div>
 </div>
 <div class="card" style="margin-top:16px"><h2>Table</h2><div class="scroll"><table>
  <thead><tr><th>enrolled (min)</th><th>tested on me (min)</th><th>recognised</th><th>time to recognise</th>
  <th>false alarms / h</th><th>impostors</th><th>caught</th><th>time to catch</th><th>ready</th></tr></thead>
  <tbody id="curve-rows"></tbody></table></div></div>
</section>
<section id="tab-guests" class="hidden">
 <div class="grid">
  <div class="card"><h2>Record someone else</h2>
   <p class="sub">Hand the computer to someone for 10 to 15 minutes of ordinary use. Their activity is kept
   apart, never enrols as me, and becomes the impostor population: it gives the real detection numbers and
   a reference that sharpens the model. Ask them first: it is behavioural data about them. Their session is
   deleted after the retention period like mine; a statistical summary pooled with the other guests, which
   names no one, is kept so detection keeps working, until they ask, or I delete it.</p>
   <input id="guest-label" placeholder="label, e.g. a first name" maxlength="40">
   <label style="display:block;margin:8px 0"><input type="checkbox" id="guest-consent">
    They have agreed, knowing what is recorded, why, for how long (30 days for their session, until deleted
    for the pooled summary), and that they can have both deleted.</label>
   <button class="act" onclick="startGuest()">Start guest session</button>
   <button class="act stop" onclick="act('guest_stop')">Stop</button></div>
  <div class="card"><h2>Recorded guests</h2><table><thead><tr><th>label</th><th>day</th><th>size</th><th></th></tr></thead>
   <tbody id="guest-rows"></tbody></table>
   <h2 style="margin-top:16px">Pooled guest reference</h2><p class="sub" id="pop-line"></p>
   <button class="link" id="pop-forget" onclick="if (confirm('Forget the pooled guest reference?')) act('population_forget')">forget it</button></div>
 </div>
</section>
</main>
<div class="tip" id="tip"></div>
<script>
const $ = id => document.getElementById(id);
const S = {segments: [], status: {}, learning: null, guests: [], history: [], live_hour: null};
const TABS = ['now', 'timeline', 'learning', 'guests'];
let rangeDays = 30;
function showTab(name) {
  document.querySelectorAll('nav button[data-tab]').forEach(x => x.classList.toggle('on', x.dataset.tab === name));
  for (const t of TABS) $('tab-' + t).classList.toggle('hidden', t !== name);
  render();
}
document.querySelectorAll('nav button[data-tab]').forEach(b => b.onclick = () => {
  history.replaceState(null, '', '#' + b.dataset.tab); showTab(b.dataset.tab); });
document.querySelectorAll('button.range').forEach(b => b.onclick = () => {
  rangeDays = +b.dataset.range;
  document.querySelectorAll('button.range').forEach(x => x.classList.toggle('on', x === b)); render(); });
async function act(name, body) {
  await fetch('/api/action/' + name, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {})});
}
function startGuest() {
  if (!$('guest-consent').checked) { alert('Their agreement comes first.'); return; }
  act('guest_start', {label: $('guest-label').value, consent: true});
  $('guest-consent').checked = false;
}
function td(text, cls) { const c = document.createElement('td'); c.textContent = text;
  if (cls) c.className = cls; return c; }
const fmtS = s => s == null ? '-' : s < 90 ? Math.round(s) + ' s' : (s / 60).toFixed(1) + ' min';
const fmtMin = m => m == null ? '-' : m < 90 ? (+m).toFixed(m < 10 ? 1 : 0) + ' min' : (m / 60).toFixed(1) + ' h';
const pct = v => v == null ? '-' : Math.round(v * 100) + ' %';

// One line chart: one axis, thin lines, markers with a hover tooltip, optional
// dashed reference lines and a vertical marker.
function chart(el, o) {
  const W = el.clientWidth || 340, H = 170, L = 44, R = 10, T = 10, B = 26;
  const pts = o.series.flatMap(s => s.ys.map((y, i) => [o.xs[i], y])).filter(p => p[1] != null);
  if (!pts.length) { el.innerHTML = '<p class="muted">No data yet.</p>'; return; }
  const fx = o.logX ? Math.log10 : (v => v);
  const xs = o.xs.map(fx), x0 = Math.min(...xs), x1 = Math.max(...xs) === x0 ? x0 + 1 : Math.max(...xs);
  let y0 = o.yMin ?? 0, y1 = o.yMax ?? Math.max(...pts.map(p => p[1]), ...(o.refs || []).map(r => r.y));
  if (y1 === y0) y1 = y0 + 1;
  const X = v => L + (fx(v) - x0) / (x1 - x0) * (W - L - R);
  const Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  let g = '';
  for (let i = 0; i <= 4; i++) { const v = y0 + (y1 - y0) * i / 4;
    g += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--grid)"/>` +
         `<text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end">${o.yFmt(v)}</text>`; }
  const ticks = o.logX ? [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000].filter(t => fx(t) >= x0 && fx(t) <= x1)
                       : [0, 1, 2, 3, 4].map(i => (x0 + (x1 - x0) * i / 4));
  for (const t of ticks) g += `<text x="${X(t)}" y="${H - 6}" text-anchor="middle">${o.xFmt(t)}</text>`;
  for (const r of (o.refs || [])) g += `<line x1="${L}" x2="${W - R}" y1="${Y(r.y)}" y2="${Y(r.y)}" ` +
    `stroke="var(--text-muted)" stroke-dasharray="4 4"/><text x="${W - R}" y="${Y(r.y) - 4}" text-anchor="end">${r.label}</text>`;
  if (o.vline != null) g += `<line x1="${X(o.vline)}" x2="${X(o.vline)}" y1="${T}" y2="${H - B}" ` +
    `stroke="var(--good)" stroke-dasharray="3 3"/><text x="${X(o.vline) + 4}" y="${T + 10}">ready</text>`;
  let marks = '';
  o.series.forEach((s, si) => {
    let d = '', on = false, prev = null;
    s.ys.forEach((y, i) => { if (y == null) { on = false; return; }
      if (o.gap && prev != null && o.xs[i] - prev > o.gap) on = false;
      d += (on ? 'L' : 'M') + X(o.xs[i]).toFixed(1) + ' ' + Y(y).toFixed(1); on = true; prev = o.xs[i]; });
    g += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2"/>`;
    s.ys.forEach((y, i) => { if (y == null) return;
      const tip = `${s.name}: ${o.yFmt(y)}\\n${o.xLabel}: ${o.xFmt(o.xs[i])}`;
      marks += `<circle cx="${X(o.xs[i])}" cy="${Y(y)}" r="${o.xs.length > 60 ? 2 : 4}" fill="${s.color}" ` +
        `stroke="var(--surface-1)" stroke-width="2"/><circle cx="${X(o.xs[i])}" cy="${Y(y)}" r="10" ` +
        `fill="transparent" data-tip="${tip.replace(/"/g, '')}"/>`; });
  });
  el.innerHTML = `<svg width="100%" viewBox="0 0 ${W} ${H}" role="img" aria-label="${o.aria}">${g}${marks}</svg>` +
    (o.series.length > 1 ? '<div class="legend">' + o.series.map(s =>
      `<span><i style="background:${s.color}"></i>${s.name}</span>`).join('') + '</div>' : '');
}
document.addEventListener('mousemove', e => {
  const t = e.target.dataset && e.target.dataset.tip, tip = $('tip');
  if (!t) { tip.style.display = 'none'; return; }
  tip.textContent = t; tip.style.display = 'block';
  tip.style.left = (e.clientX + 12) + 'px'; tip.style.top = (e.clientY + 12) + 'px';
});

const STATE_TEXT = {learning: 'Learning', recognized: 'Recognised', alert: 'Someone else?'};
function renderStatus() {
  const st = S.status || {}, last = S.segments[S.segments.length - 1];
  const p = last ? last.p_impostor : null;
  let state = st.ready ? (p != null && p > 0.5 ? 'alert' : 'recognized') : 'learning';
  if (!st.phase || st.phase === 'starting') state = 'waiting';
  const color = {learning: 'var(--neutral)', recognized: 'var(--good)', alert: 'var(--critical)'}[state] || 'var(--neutral)';
  const label = state === 'learning' ? `Learning ${Math.round((st.progress || 0) * 100)} %` :
                state === 'alert' ? `Someone else? ${Math.round(p * 100)} %` : (STATE_TEXT[state] || 'waiting');
  $('state-pill').innerHTML = `<i class="dot" style="background:${color}"></i>`;
  $('state-pill').append(label);
  $('hero-state').textContent = label;
  $('phase-line').textContent = st.phase ? `phase ${st.phase}, ${st.days || 0} day(s), ` +
    `${(st.owner_keystrokes || 0).toLocaleString()} keystrokes, model fitted ${st.fitted_at || '-'}` +
    (st.population_reference ? ', guest population in use' : '') +
    (st.restored_from ? ', restored model: the stored days no longer support a fresh one' : '')
    : 'waiting for the first fit';
  const c = st.criteria || {}, names = {volume: 'C1 volume', stability: 'C2 stability',
    coverage: 'C4 days covered', performance: 'C3 measured performance'};
  $('criteria').innerHTML = '';
  for (const k of Object.keys(names)) {
    const row = document.createElement('div');
    row.innerHTML = `<div class="muted" style="font-size:12px">${names[k]}: ${Math.round((c[k] || 0) * 100)} %</div>` +
      `<div class="bar"><i style="width:${Math.round((c[k] || 0) * 100)}%"></i></div>`;
    $('criteria').append(row);
  }
  const g = st.guest;
  $('guest-banner').classList.toggle('hidden', !g);
  if (g) $('guest-name').textContent = g.label;
}
function renderNow() {
  const segs = S.segments.slice(-300);
  const xs = segs.map(s => s.t ?? s.index);
  chart($('ch-p'), {xs, series: [{name: 'P(someone else)', ys: segs.map(s => s.p_impostor), color: 'var(--series-1)'}],
    yMin: 0, yMax: 1, yFmt: v => Math.round(v * 100) + '%', xFmt: v => fmtS(v), xLabel: 'active time',
    refs: [{y: 0.5, label: 'alert above 50 %'}], aria: 'probability of someone else over the session'});
  const ev = segs.map(s => s.session_db == null ? null : Math.max(-60, Math.min(60, s.session_db)));
  chart($('ch-e'), {xs, series: [{name: 'summed evidence', ys: ev, color: 'var(--series-3)'}],
    yMin: -60, yMax: 60, yFmt: v => Math.round(v) + ' dB', xFmt: v => fmtS(v), xLabel: 'active time',
    refs: [{y: -20, label: 'recognised'}], aria: 'summed evidence over the session'});
  const rows = $('rows'); rows.innerHTML = '';
  for (const s of S.segments.slice(-40).reverse()) {
    const tr = document.createElement('tr');
    tr.append(td(s.at || s.index), td(s.events), td(s.actor + (s.guest ? ' (guest)' : '')),
      td(pct(s.p_impostor)), td(s.evidence_db == null ? '-' : s.evidence_db + ' dB'),
      td(s.outcome, 'out-' + s.outcome));
    const reasons = (s.explanation || '').split('\\n').slice(1).filter(l => l.includes('- ')).slice(0, 2)
      .map(l => l.replace(/^\\s*- /, '')).join('; ');
    const acted = s.sensitivity && s.sensitivity !== 'low'
      ? s.sensitivity + ' sensitivity (' + (s.actions || []).join(', ') + ')' : '';
    tr.append(td([acted, reasons].filter(Boolean).join('; '), 'muted reasons'));
    rows.append(tr);
  }
}
const HOUR = 3600e3, DAY = 24 * HOUR;
const two = n => String(n).padStart(2, '0');
const fmtWhen = v => { const d = new Date(v);
  return `${two(d.getDate())}/${two(d.getMonth() + 1)} ${two(d.getHours())}:${two(d.getMinutes())}`; };
const fmtDay = v => { const d = new Date(v); return `${two(d.getDate())}/${two(d.getMonth() + 1)}`; };
function renderTimeline() {
  const from = Date.now() - rangeDays * DAY;
  const lines = S.history.concat(S.live_hour && S.live_hour.w ? [S.live_hour] : [])
    .map(l => ({...l, x: new Date(l.w).getTime()})).filter(l => l.x >= from);
  const of = k => lines.filter(l => l.k === k);
  const fits = of('fit'), hours = of('hour'), curves = of('curve');
  const first = S.history.length ? fmtWhen(new Date(S.history[0].w).getTime()) : null;
  $('tl-note').textContent = first ? ` history kept since ${first}` : ' no history yet: it fills after the first refit';
  const xf = rangeDays > 1 ? fmtDay : fmtWhen;
  const base = xs => ({xs, xFmt: xf, xLabel: 'when', gap: rangeDays > 1 ? 6 * HOUR : 2 * HOUR});
  const fx = fits.map(l => l.x), c = l => l.criteria || {};
  chart($('tl-learn'), {...base(fx), yMin: 0, yMax: 1, yFmt: v => Math.round(v * 100) + '%', aria: 'learning over time',
    series: [{name: 'overall', ys: fits.map(l => l.progress), color: 'var(--text-primary)'},
             {name: 'C1 volume', ys: fits.map(l => c(l).volume), color: 'var(--series-1)'},
             {name: 'C2 stability', ys: fits.map(l => c(l).stability), color: 'var(--series-2)'},
             {name: 'C4 days', ys: fits.map(l => c(l).coverage), color: 'var(--series-3)'},
             {name: 'C3 performance', ys: fits.map(l => c(l).performance), color: 'var(--warning)'}]});
  chart($('tl-conf'), {...base(hours.map(l => l.x)), yMin: 0, yMax: 1, yFmt: v => Math.round(v * 100) + '%',
    aria: 'recognition per hour', refs: [{y: 0.5, label: 'alert above 50 %'}],
    series: [{name: 'confidence it is me', ys: hours.map(l => l.conf), color: 'var(--series-3)'},
             {name: 'highest P(someone else)', ys: hours.map(l => l.p_max), color: 'var(--series-2)'}]});
  const perDay = {};
  for (const l of hours) { const d = new Date(l.x); d.setHours(12, 0, 0, 0);
    perDay[d.getTime()] = (perDay[d.getTime()] || 0) + (l.alarms || 0); }
  const days = Object.keys(perDay).map(Number).sort((a, b) => a - b);
  chart($('tl-alarms'), {xs: days, xFmt: fmtDay, xLabel: 'day', yFmt: v => Math.round(v), aria: 'alarms per day',
    series: [{name: 'alarms', ys: days.map(d => perDay[d]), color: 'var(--critical)'}]});
  const dr = (l, k) => l.drift && l.drift[k] ? l.drift[k].overall : null;
  chart($('tl-drift'), {...base(fx), yMin: 0, yFmt: v => v.toFixed(3), aria: 'model drift over time',
    series: [{name: 'vs 1 day before', ys: fits.map(l => dr(l, '1d')), color: 'var(--series-1)'},
             {name: 'vs 7 days before', ys: fits.map(l => dr(l, '7d')), color: 'var(--series-2)'},
             {name: 'vs oldest kept', ys: fits.map(l => dr(l, 'oldest')), color: 'var(--series-3)'}]});
  chart($('tl-keys'), {...base(fx), yFmt: v => Math.round(v).toLocaleString(), aria: 'keystrokes enrolled',
    series: [{name: 'keystrokes', ys: fits.map(l => l.keystrokes), color: 'var(--series-1)'}]});
  const cx = curves.map(l => l.x);
  chart($('tl-perf'), {...base(cx), yMin: 0, yFmt: v => v.toFixed(1), aria: 'measured performance',
    refs: [{y: 0.2, label: 'false alarm target'}],
    series: [{name: 'false alarms / h', ys: curves.map(l => l.false_alarms_per_hour), color: 'var(--series-2)'},
             {name: 'share caught', ys: curves.map(l => l.detected_share), color: 'var(--series-1)'}]});
  chart($('tl-ttr'), {...base(cx), yFmt: v => fmtS(v), aria: 'time to recognise over time',
    series: [{name: 'time to recognise', ys: curves.map(l => l.time_to_recognise_s), color: 'var(--series-3)'}]});
}
function renderLearning() {
  const L = S.learning || {}, pts = L.points || [];
  const ready = L.ready_at_minutes;
  $('ready-hero').textContent = ready != null ? `after ${fmtMin(ready)} of use` :
    pts.length ? 'not yet' : 'not enough data yet';
  $('ready-sub').textContent = `${fmtMin(L.owner_minutes || 0)} of my active use collected. Ready means at least ` +
    `90 % of the other person's sessions caught and at most 0.2 false alarm per hour on me.`;
  $('curve-note').textContent = L.note || (L.impostor_kind === 'guest' ?
    `Impostors: ${pts.length ? pts[0].impostor_sessions : 0} real guest session(s)` +
    (L.population_reference ? ', tested one out against the others.' : '.') : '');
  $('curve-time').textContent = L.computed_at ? ' last computed ' + L.computed_at : '';
  const xs = pts.map(p => Math.max(p.enrol_minutes, 0.1));
  const base = {xs, logX: true, xFmt: v => fmtMin(v), xLabel: 'enrolled', vline: ready};
  chart($('ch-crit'), {...base, yMin: 0, yMax: 1, yFmt: v => Math.round(v * 100) + '%', aria: 'enrolment criteria',
    series: [{name: 'C1 volume', ys: pts.map(p => p.volume), color: 'var(--series-1)'},
             {name: 'C2 stability', ys: pts.map(p => p.stability), color: 'var(--series-2)'},
             {name: 'C4 days', ys: pts.map(p => p.coverage), color: 'var(--series-3)'}]});
  chart($('ch-det'), {...base, yMin: 0, yMax: 1, yFmt: v => Math.round(v * 100) + '%', aria: 'share caught',
    refs: [{y: 0.9, label: 'target'}], series: [{name: 'caught', ys: pts.map(p => p.detected_share), color: 'var(--series-1)'}]});
  chart($('ch-ttd'), {...base, yFmt: v => fmtS(v), aria: 'time to catch',
    series: [{name: 'time to catch', ys: pts.map(p => p.median_time_to_detect_s), color: 'var(--series-1)'}]});
  chart($('ch-ttr'), {...base, yFmt: v => fmtS(v), aria: 'time to recognise',
    series: [{name: 'time to recognise', ys: pts.map(p => p.median_time_to_recognise_s), color: 'var(--series-1)'}]});
  chart($('ch-fa'), {...base, yFmt: v => v.toFixed(1), aria: 'false alarms per hour',
    refs: [{y: 0.2, label: 'target'}],
    series: [{name: 'false alarms / h', ys: pts.map(p => p.false_alarms_per_hour), color: 'var(--series-1)'}]});
  const rows = $('curve-rows'); rows.innerHTML = '';
  for (const p of pts) { const tr = document.createElement('tr');
    tr.append(td(p.enrol_minutes), td(p.genuine_minutes_tested), td(pct(p.recognised_share)),
      td(fmtS(p.median_time_to_recognise_s)),
      td(p.false_alarms_per_hour == null ? '-' : p.false_alarms_per_hour.toFixed(2)),
      td(`${p.impostor_sessions} ${p.impostor_kind}`), td(pct(p.detected_share)),
      td(fmtS(p.median_time_to_detect_s)), td(p.ready ? 'yes' : 'no'));
    rows.append(tr); }
}
function renderGuests() {
  const rows = $('guest-rows'); rows.innerHTML = '';
  for (const g of S.guests) { const tr = document.createElement('tr');
    const del = document.createElement('button'); del.className = 'link'; del.textContent = 'delete';
    del.onclick = () => { if (confirm('Delete this guest session?')) act('guest_delete', {id: g.id}); };
    const c = document.createElement('td'); c.append(del);
    tr.append(td(g.label), td(g.day), td(Math.round((g.bytes || 0) / 1024) + ' KB'), c);
    rows.append(tr); }
  if (!S.guests.length) rows.innerHTML = '<tr><td class="muted" colspan="4">none yet</td></tr>';
  const pop = (S.status || {}).population;
  $('pop-line').textContent = !pop ? 'None: without guests, someone else is judged against a wide default, ' +
    'which only catches very different typists.' : `From ${pop.sessions} guest session(s), fitted ${pop.fitted_at}` +
    (pop.kept ? ', kept after their sessions were deleted.' : '.');
  $('pop-forget').classList.toggle('hidden', !pop);
}
let pending = false;
function render() { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false;
  renderStatus();
  if (!$('tab-now').classList.contains('hidden')) renderNow();
  if (!$('tab-timeline').classList.contains('hidden')) renderTimeline();
  if (!$('tab-learning').classList.contains('hidden')) renderLearning();
  if (!$('tab-guests').classList.contains('hidden')) renderGuests(); }); }
Object.assign(S, /*INITIAL*/{}); S.status = S.status || {}; S.guests = S.guests || [];
S.segments = S.segments || []; S.history = S.history || []; render();
const es = new EventSource('/events');
es.addEventListener('hello', e => { Object.assign(S, JSON.parse(e.data)); S.status = S.status || {};
  S.guests = S.guests || []; render(); });
es.addEventListener('segment', e => { S.segments.push(JSON.parse(e.data));
  if (S.segments.length > 600) S.segments.shift(); render(); });
es.addEventListener('status', e => { S.status = JSON.parse(e.data); render(); });
es.addEventListener('learning', e => { S.learning = JSON.parse(e.data); render(); });
es.addEventListener('guests', e => { S.guests = JSON.parse(e.data).guests; render(); });
es.addEventListener('history', e => { S.history = JSON.parse(e.data).lines; render(); });
es.addEventListener('history_line', e => { const l = JSON.parse(e.data); S.history.push(l);
  if (l.k === 'hour') S.live_hour = null; render(); });
es.addEventListener('live_hour', e => { const l = JSON.parse(e.data); S.live_hour = l.w ? l : null; render(); });
window.addEventListener('resize', render);
// A link ending in #learning opens that tab (the fragment survives the login redirect).
if (TABS.includes(location.hash.slice(1))) showTab(location.hash.slice(1));
</script></body></html>"""
