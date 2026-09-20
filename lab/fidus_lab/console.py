"""Local administration console (FR-50 to FR-58, SR-9).

A standard-library HTTP server bound to 127.0.0.1 that streams the analysis of
a trace over Server-Sent Events and drives the GNOME overlay.

A local web server is reachable by any page in the browser, so (SR-9): it
validates Host and Origin (anti-DNS-rebinding), sends no cross-origin headers,
and keeps the session in an HttpOnly, SameSite=Strict cookie, never in the URL.
The only thing that ever travels in a URL is a one-time bootstrap link, consumed
on first use, so a leak into browser history is harmless.

The pure pieces (SSE framing, the host check, the state snapshot) are unit
tested; a smoke test binds an ephemeral port and fetches a page.
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def segment_snapshot(r: SegmentReport) -> dict:
    return {
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
    _subscribers: list["_Queue"] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def publish(self, report: SegmentReport) -> None:
        snap = segment_snapshot(report)
        with self._lock:
            self.segments.append(snap)
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

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "segments": list(self.segments),
                "max_p_impostor": self.max_p_impostor,
                "outcomes": dict(self.outcomes),
                "profile_count": self.profile_count,
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


def render_page() -> str:
    return _PAGE


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
                body = render_page().encode()
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

    return Handler


class Bootstrap:
    """A one-time login token. Valid until consumed exactly once."""

    def __init__(self) -> None:
        self._token: str | None = secrets.token_urlsafe(24)
        self._lock = threading.Lock()

    @property
    def token(self) -> str | None:
        return self._token

    def consume(self, presented: str) -> bool:
        with self._lock:
            if self._token is None or not presented:
                return False
            ok = secrets.compare_digest(presented, self._token)
            if ok:
                self._token = None
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


def start(host: str = "127.0.0.1", port: int = 0) -> Console:
    """Start the console on the loopback. Port 0 picks a free port."""
    bootstrap = Bootstrap()
    session = secrets.token_urlsafe(32)
    state = ConsoleState()
    server = ThreadingHTTPServer((host, port), make_handler(bootstrap, session, state))
    return Console(state=state, server=server, bootstrap=bootstrap, session=session)


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>FidusAchates console</title>
<style>
 :root{color-scheme:dark}
 body{font:14px/1.5 system-ui,sans-serif;margin:0;background:#111;color:#eee}
 header{padding:12px 20px;background:#1a1a1a;border-bottom:1px solid #333}
 h1{font-size:16px;margin:0}
 main{padding:20px;display:grid;gap:20px;grid-template-columns:1fr 2fr}
 .card{background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:16px}
 .gauge{font-size:40px;font-weight:bold}
 .bad{color:#e33}.ok{color:#3c3}
 table{width:100%;border-collapse:collapse;font-size:13px}
 td,th{padding:4px 8px;border-bottom:1px solid #262626;text-align:left}
 .tag-automation_unsanctioned{color:#e90}
 .tag-automation_sanctioned{color:#6ad}
 .tag-human{color:#9c9}
 .out-alert{color:#e33;font-weight:bold}.out-tag{color:#e90}.out-none{color:#7a7}
</style></head><body>
<header><h1>FidusAchates &mdash; local console</h1></header>
<main>
 <section class="card">
  <div>Identity confidence (max)</div>
  <div id="gauge" class="gauge ok">9%</div>
  <div style="margin-top:12px">Distinct profiles: <b id="profiles">0</b></div>
  <div id="outcomes" style="margin-top:8px;color:#aaa"></div>
 </section>
 <section class="card">
  <table><thead><tr><th>#</th><th>events</th><th>actor</th><th>P(impostor)</th><th>outcome</th></tr></thead>
  <tbody id="rows"></tbody></table>
 </section>
</main>
<script>
 const gauge = document.getElementById('gauge');
 const rows = document.getElementById('rows');
 const outcomes = document.getElementById('outcomes');
 let maxp = 0.09;
 function setGauge(p){maxp=Math.max(maxp,p);const pct=Math.round(maxp*100);
   gauge.textContent=pct+'%';gauge.className='gauge '+(pct>50?'bad':'ok');}
 function addRow(s){const tr=document.createElement('tr');
   tr.innerHTML=`<td>${s.index}</td><td>${s.events}</td>`+
     `<td class="tag-${s.actor}">${s.actor}</td>`+
     `<td>${(s.p_impostor*100).toFixed(0)}%</td>`+
     `<td class="out-${s.outcome}">${s.outcome}</td>`;
   rows.prepend(tr);setGauge(s.p_impostor);}
 const es = new EventSource('/events');
 es.addEventListener('hello',e=>{const st=JSON.parse(e.data);
   (st.segments||[]).forEach(addRow);
   document.getElementById('profiles').textContent=st.profile_count||0;});
 es.addEventListener('segment',e=>addRow(JSON.parse(e.data)));
 es.addEventListener('profiles',e=>{
   document.getElementById('profiles').textContent=JSON.parse(e.data).count;});
</script></body></html>"""
