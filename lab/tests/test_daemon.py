import datetime as dt
import json
import os
import threading
import urllib.error
import urllib.request

import pytest

from fidus_lab.console import publish_link, start
from fidus_lab.daemon import panel_state
from fidus_lab.segment import Segment
from fidus_lab.storage import Store, monotonic_runs
from fidus_lab.synth import Typist
from fidus_lab.trace import Event, EventKind, Record

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
DAY = dt.date(2026, 10, 1)


def test_panel_state_never_alerts_while_learning():
    assert panel_state(False, 0.34, 0.99) == ("learning", 34)
    assert panel_state(True, 1.0, 0.72) == ("alert", 72)
    assert panel_state(True, 1.0, 0.2) == ("recognized", 0)
    assert panel_state(True, 1.0, None) == ("recognized", 0)


def test_store_round_trips_days_and_splits_reboots(tmp_path):
    st = Store(tmp_path)
    a = Typist(seed=1, **GEN).type_segment(30, start_us=50_000_000)
    b = Typist(seed=2, **GEN).type_segment(30, start_us=1_000)  # after a reboot
    st.write(a, today=DAY)
    st.write(b, today=DAY)
    st.write(Typist(seed=3, **GEN).type_segment(30, start_us=9_000_000),
             today=DAY + dt.timedelta(days=1))
    st.flush()
    assert st.days() == ["2026-10-01", "2026-10-02"]
    segs, days = st.load_owner()
    assert len(segs) == 3 and days == [0, 0, 1]
    assert oct(os.stat(tmp_path / "traces" / "2026-10-01.fidustr").st_mode)[-3:] == "600"


def test_monotonic_runs_split_where_time_goes_back():
    recs = [Record(t, 0, False, Event(EventKind.WHEEL, dy=1)) for t in (5, 6, 1, 2)]
    assert [len(r) for r in monotonic_runs(recs)] == [2, 2]


def test_excluded_windows_never_come_back(tmp_path):
    st = Store(tmp_path)
    recs = Typist(seed=1, **GEN).type_segment(30)
    st.write(recs, today=dt.date.today())
    st.flush()
    segs, _ = st.load_owner()
    st.exclude(segs[0])
    assert st.load_owner()[0] == []


def test_guests_are_separate_and_pruned_with_retention(tmp_path):
    st = Store(tmp_path, retention_days=30)
    with pytest.raises(ValueError):
        st.new_guest("No consent", consent=False, today=DAY)
    g = st.new_guest("Alice <script>", consent=True, today=DAY)
    g.write(Typist(seed=5, **GEN).type_segment(30))
    g.close()
    assert st.guests()[0]["label"] == "Alice script"
    assert st.guests()[0]["consent"] is True and st.guests()[0]["consent_at"]
    assert len(st.load_guest_sessions()) == 1
    assert st.load_owner()[0] == []
    st.write(Typist(seed=6, **GEN).type_segment(5), today=DAY)
    st.flush()
    removed = st.prune(today=DAY + dt.timedelta(days=31))
    assert removed and st.guests() == [] and st.days() == []
    assert not st.delete_guest("../../etc/passwd")


def _login(console):
    """Follow the one-time link with a cookie jar, as a browser would."""
    import http.cookiejar

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(console.url).read()
    return opener


def test_link_is_rearmed_and_published_0600(tmp_path):
    c = start(rearm=True)
    threading.Thread(target=c.serve_forever, daemon=True).start()
    try:
        path = publish_link(c, tmp_path / "console-link")
        first = path.read_text().strip()
        assert oct(os.stat(path).st_mode)[-3:] == "600"
        _login(c)
        second = path.read_text().strip()
        assert second != first and second == c.url
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(first)          # a used link never works twice
    finally:
        c.shutdown()


def test_actions_need_session_and_origin():
    c = start(rearm=True)
    seen = {}
    c.state.actions["guest_start"] = lambda body: seen.update(body) or {"guest": "x"}
    threading.Thread(target=c.serve_forever, daemon=True).start()
    host, port = c.server.server_address[:2]
    base = f"http://{host}:{port}"
    try:
        opener = _login(c)

        def post(origin, data=b'{"label":"Bob"}', op=opener):
            req = urllib.request.Request(base + "/api/action/guest_start", data=data,
                                         method="POST")
            if origin:
                req.add_header("Origin", origin)
            return op.open(req)

        assert json.loads(post(base).read()) == {"guest": "x"}
        assert seen == {"label": "Bob"}
        for bad in (None, "http://evil.example"):
            with pytest.raises(urllib.error.HTTPError):
                post(bad)
        with pytest.raises(urllib.error.HTTPError):
            post(base, op=urllib.request.build_opener())   # no cookie
        with pytest.raises(urllib.error.HTTPError):
            post(base, data=b"[1]")
    finally:
        c.shutdown()


def test_state_snapshot_carries_live_fields():
    c = start()
    c.state.set_status({"phase": "enrolment", "progress": 0.4})
    c.state.set_learning({"points": [], "ready_at_minutes": None})
    snap = c.state.snapshot()
    assert snap["status"]["phase"] == "enrolment"
    assert snap["learning"]["ready_at_minutes"] is None
    c.server.server_close()


def test_segment_type_has_context_by_default():
    assert Segment(0, 0).context == []
