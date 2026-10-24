import datetime as dt
import json
import os

from fidus_lab import saved_model
from fidus_lab.learning import Enrolled
from fidus_lab.segment import segment_trace
from fidus_lab.storage import Store
from fidus_lab.synth import Typist

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)


def _enrolled() -> Enrolled:
    recs = []
    for i in range(6):
        recs += Typist(seed=i, **GEN).type_segment(60, start_us=i * 60_000_000)
    return Enrolled.fit(list(segment_trace(recs)))


def test_the_model_round_trips_and_scores_the_same(tmp_path):
    e = _enrolled()
    path = tmp_path / "model.json"
    saved_model.save(path, e, {"progress": 0.6, "ready": False})
    back, status = saved_model.load(path)
    assert back == e and status["progress"] == 0.6
    assert oct(os.stat(path).st_mode)[-3:] == "600"
    probe = list(segment_trace(Typist(seed=99, **GEN).type_segment(60)))[0]
    assert e.engine().step(probe).evidence_db == back.engine().step(probe).evidence_db


def test_an_unreadable_or_foreign_file_is_ignored(tmp_path):
    path = tmp_path / "model.json"
    assert saved_model.load(path) is None
    path.write_text("{not json")
    assert saved_model.load(path) is None
    path.write_text(json.dumps({"format": 999, "status": {}, "model": {}}))
    assert saved_model.load(path) is None


def test_the_saved_model_stands_in_only_when_clearly_better():
    saved = {"progress": 0.8, "ready": False}
    assert saved_model.prefer_saved(None, saved)
    assert saved_model.prefer_saved({"progress": 0.2, "ready": False}, saved)
    assert not saved_model.prefer_saved({"progress": 0.75, "ready": False}, saved)
    assert saved_model.prefer_saved({"progress": 0.99, "ready": False},
                                    {"progress": 1.0, "ready": True})
    assert not saved_model.prefer_saved({"progress": 1.0, "ready": True},
                                        {"progress": 1.0, "ready": True})


def test_flagged_windows_follow_the_retention(tmp_path):
    st = Store(tmp_path, retention_days=30)
    seg = list(segment_trace(Typist(seed=1, **GEN).type_segment(30)))[0]
    st.exclude(seg, today=dt.date(2026, 9, 1))
    st.exclude(seg, today=dt.date(2026, 10, 20))
    removed = st.prune(today=dt.date(2026, 10, 24))
    assert tmp_path / "excluded.jsonl" in removed
    assert list(st._excluded()) == ["2026-10-20"]
    assert st.prune(today=dt.date(2026, 10, 24)) == []


def test_daemon_saves_the_fresh_fit_and_falls_back_after_an_absence(tmp_path):
    from types import SimpleNamespace

    from fidus_lab.daemon import Daemon

    d = SimpleNamespace(model_path=tmp_path / "model.json")
    e = _enrolled()
    ready = {"progress": 1.0, "ready": True, "fitted_at": "2026-10-24 12:00", "guests": 0,
             "population_reference": False, "curve_kind": "simulated"}
    assert Daemon._fresh_or_saved(d, e, ready) == (e, ready)
    # A month later every day is gone: no fresh fit, the saved one stands in.
    empty = ready | {"progress": 0.0, "ready": False, "fitted_at": "2026-11-30 09:00", "guests": 1}
    back, status = Daemon._fresh_or_saved(d, None, empty)
    assert back == e and status["ready"] and status["restored_from"] == "2026-10-24 12:00"
    assert status["guests"] == 1
