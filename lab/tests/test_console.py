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


def test_page_embeds_the_token_not_a_secret_leak():
    page = render_page("TESTTOKEN")
    assert "TESTTOKEN" in page and "EventSource" in page


def test_server_serves_only_with_token():
    console = start()
    t = threading.Thread(target=console.serve_forever, daemon=True)
    t.start()
    try:
        host, port = console.server.server_address[:2]
        base = f"http://{host}:{port}"
        # With the token: 200.
        with urllib.request.urlopen(console.url, timeout=3) as r:
            assert r.status == 200
            assert b"FidusAchates" in r.read()
        # Without the token: 403.
        try:
            urllib.request.urlopen(f"{base}/", timeout=3)
            assert False, "expected 403 without token"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        console.shutdown()
