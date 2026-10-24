import datetime as dt
import os

from fidus_lab.console import ConsoleState, render_page
from fidus_lab.history import FIT_EVERY_S, History

T0 = dt.datetime(2026, 10, 1, 9, 10)
STATUS = {"progress": 0.5, "phase": "enrolment", "ready": False, "owner_keystrokes": 4000,
          "days": 3, "guests": 0,
          "criteria": {"volume": 0.5, "stability": 1.0, "coverage": 0.6, "performance": 0.0}}


def test_fit_snapshots_are_throttled_unless_the_phase_changes(tmp_path):
    h = History(tmp_path)
    assert h.fit(STATUS, at=T0) is not None
    assert h.fit(STATUS, at=T0 + dt.timedelta(minutes=5)) is None
    later = T0 + dt.timedelta(seconds=FIT_EVERY_S)
    assert h.fit(STATUS, at=later)["progress"] == 0.5
    ready = STATUS | {"phase": "operational", "ready": True}
    assert h.fit(ready, at=later + dt.timedelta(minutes=1)) is not None
    assert [d["k"] for d in h.load()] == ["fit", "fit", "fit"]


def test_a_restart_does_not_repeat_the_last_snapshot(tmp_path):
    History(tmp_path).fit(STATUS, at=T0)
    h = History(tmp_path)
    h.load()
    assert h.fit(STATUS, at=T0 + dt.timedelta(minutes=1)) is None


def test_scores_are_summed_per_clock_hour(tmp_path):
    h = History(tmp_path)
    assert h.score(0.8, 0.1, False, at=T0) is None
    assert h.score(0.6, 0.3, True, at=T0 + dt.timedelta(minutes=40)) is None
    assert h.current()["n"] == 2
    closed = h.score(0.9, 0.05, False, at=T0 + dt.timedelta(hours=1))
    assert closed == {"k": "hour", "w": "2026-10-01T09:00:00", "n": 2, "conf": 0.7,
                      "p": 0.2, "p_max": 0.3, "alarms": 1}
    assert h.flush()["w"] == "2026-10-01T10:00:00"
    assert h.flush() is None
    assert [d["n"] for d in h.load()] == [2, 1]


def test_the_curve_survives_a_restart_and_leaves_its_headline(tmp_path):
    curve = {"owner_minutes": 120.0, "ready_at_minutes": None, "impostor_kind": "simulated",
             "points": [{"false_alarms_per_hour": 0.4, "median_time_to_recognise_s": 35.0,
                         "detected_share": 0.75}]}
    line = History(tmp_path).curve(curve, at=T0)
    assert line["false_alarms_per_hour"] == 0.4 and line["detected_share"] == 0.75
    h = History(tmp_path)
    assert h.load_learning() == curve
    assert h.load()[0]["k"] == "curve"
    assert oct(os.stat(tmp_path / "learning.json").st_mode)[-3:] == "600"
    assert oct(os.stat(tmp_path / "history" / "2026-10-01.jsonl").st_mode)[-3:] == "600"


def test_history_follows_the_retention_and_skips_torn_lines(tmp_path):
    h = History(tmp_path, retention_days=30)
    h.fit(STATUS, at=T0)
    h.fit(STATUS | {"ready": True}, at=T0 + dt.timedelta(days=31))
    with open(tmp_path / "history" / "2026-11-01.jsonl", "a") as fh:
        fh.write('{"k":"fit","w":"2026-11')
    assert len(h.load()) == 2
    removed = h.prune(today=dt.date(2026, 11, 1))
    assert [p.name for p in removed] == ["2026-10-01.jsonl"]
    assert len(h.load()) == 1


def test_console_carries_the_history_and_the_timeline_tab():
    st = ConsoleState()
    st.set_history([{"k": "fit", "w": "2026-10-01T09:10:00"}])
    st.add_history({"k": "hour", "w": "2026-10-01T09:00:00", "n": 1})
    st.set_live_hour({"k": "hour", "w": "2026-10-01T10:00:00", "n": 3})
    snap = st.snapshot()
    assert len(snap["history"]) == 2 and snap["live_hour"]["n"] == 3
    page = render_page(snap)
    assert 'id="tab-timeline"' in page and "2026-10-01T09:10:00" in page
