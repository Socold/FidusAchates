import json
import threading
import urllib.request

from fidus_lab.console import (
    ConsoleState,
    host_is_local,
    render_page,
    segment_snapshot,
    sse,
    start,
)
from fidus_lab.analyze import analyze_segments
from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.registry import SanctionRegistry
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Typist

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)


def a_report():
    recs = Typist(seed=1, **GEN).type_segment(40)
    segs = list(segment_trace(recs))
    tpl = KeystrokeTemplate.fit(segs)
    eng = IdentityEngine(genuine=tpl, reference=tpl)
    return analyze_segments(segs, eng, SanctionRegistry()).segments[0]


def test_sse_framing():
    out = sse("segment", {"a": 1}).decode()
    assert out.startswith("event: segment\n")
    assert 'data: {"a":1}\n\n' in out


def test_host_check_blocks_rebinding():
    assert host_is_local("127.0.0.1:8080")
    assert host_is_local("localhost")
    assert not host_is_local("evil.example.com")
    assert not host_is_local(None)


def test_segment_snapshot_is_content_free():
    snap = segment_snapshot(a_report())
    assert set(snap) >= {"index", "actor", "p_impostor", "outcome"}
    # No key, no character, no title anywhere in the snapshot.
    blob = json.dumps(snap).lower()
    for forbidden in ("keycode", "title", "window", "char"):
        assert forbidden not in blob


def test_state_publishes_to_subscribers():
    st = ConsoleState()
    q = st.subscribe()
    st.publish(a_report())
    item = q.get(timeout=1)
    assert item and b"event: segment" in item


def test_page_carries_no_secret():
    page = render_page()
    assert "EventSource('/events')" in page
    assert "token" not in page.lower()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _get(url, headers=None):
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers=headers or {})
    try:
        r = opener.open(req, timeout=3)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), b""


def test_session_is_a_cookie_and_bootstrap_is_one_time():
    console = start()
    t = threading.Thread(target=console.serve_forever, daemon=True)
    t.start()
    try:
        host, port = console.server.server_address[:2]
        base = f"http://{host}:{port}"

        # No session: forbidden.
        code, _, _ = _get(f"{base}/")
        assert code == 403

        # The one-time link sets the cookie and redirects, without the
        # session ever appearing in a URL.
        code, headers, _ = _get(console.url)
        assert code == 302
        set_cookie = headers.get("Set-Cookie", "")
        assert "fidus_session=" in set_cookie
        assert "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie
        assert headers.get("Location") == "/"
        cookie = set_cookie.split(";")[0]

        # Same link again: consumed, refused.
        code, _, _ = _get(console.url)
        assert code == 403

        # With the cookie: the page and the API work.
        code, _, body = _get(f"{base}/", {"Cookie": cookie})
        assert code == 200 and b"FidusAchates" in body
        code, _, body = _get(f"{base}/api/state", {"Cookie": cookie})
        assert code == 200 and b"segments" in body

        # A foreign Host header (DNS rebinding) is refused even with the cookie.
        code, _, _ = _get(f"{base}/api/state",
                          {"Cookie": cookie, "Host": "evil.example.com"})
        assert code == 403
    finally:
        console.shutdown()
