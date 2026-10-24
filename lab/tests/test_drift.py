import datetime as dt
import os

from fidus_lab.drift import ModelSnapshots, categorical_js, model_drift
from fidus_lab.history import History
from fidus_lab.learning import Enrolled
from fidus_lab.segment import segment_trace
from fidus_lab.stats import Categorical
from fidus_lab.synth import Typist

ME = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
OTHER = dict(hold_mu=11.9, hold_sigma=0.25, gap_mu=12.1, gap_sigma=0.3)
DAY = dt.date(2026, 10, 24)


def _enrolled(gen: dict, seed: int = 0) -> Enrolled:
    recs = []
    for i in range(6):
        recs += Typist(seed=seed + i, **gen).type_segment(60, start_us=i * 60_000_000)
    return Enrolled.fit(list(segment_trace(recs)))


def test_categorical_js_is_zero_for_the_same_and_grows_apart():
    a = Categorical(counts=(50, 10, 0))
    assert categorical_js(a, a) == 0.0
    assert categorical_js(a, Categorical(counts=(0, 10, 50))) > 0.3


def test_someone_else_drifts_much_more_than_me_again():
    me = _enrolled(ME)
    again = model_drift(_enrolled(ME, seed=50), me)
    other = model_drift(_enrolled(OTHER, seed=50), me)
    assert model_drift(me, me)["overall"] == 0.0
    assert other["keystroke"] > 3 * again["keystroke"]
    assert other["overall"] > again["overall"]


def test_snapshots_one_per_day_and_lagged_references(tmp_path):
    snaps = ModelSnapshots(tmp_path)
    me = _enrolled(ME)
    for back in (30, 8, 1):
        assert snaps.save_daily(me, {}, today=DAY - dt.timedelta(days=back))
    assert not snaps.save_daily(me, {}, today=DAY - dt.timedelta(days=1))
    snaps.save_daily(me, {}, today=DAY)  # today's own: never a reference
    refs = snaps.references(today=DAY)
    assert {k: v[0] for k, v in refs.items()} == {
        "1d": "2026-10-23", "7d": "2026-10-16", "oldest": "2026-09-24"}
    d = snaps.drift(me, today=DAY)
    assert d["7d"]["overall"] == 0.0 and d["oldest"]["day"] == "2026-09-24"
    assert oct(os.stat(tmp_path / "models" / "2026-10-23.json").st_mode)[-3:] == "600"
    assert [p.name for p in snaps.prune(today=DAY + dt.timedelta(days=1))] == ["2026-09-24.json"]


def test_no_reference_before_a_first_day_is_kept(tmp_path):
    snaps = ModelSnapshots(tmp_path)
    snaps.save_daily(_enrolled(ME), {}, today=DAY)
    assert snaps.drift(_enrolled(ME), today=DAY) == {}


def test_the_fit_line_carries_the_drift(tmp_path):
    line = History(tmp_path).fit({"phase": "enrolment", "ready": False,
                                  "drift": {"1d": {"overall": 0.01, "day": "2026-10-23"}}})
    assert line["drift"]["1d"]["overall"] == 0.01


def test_the_daemon_keeps_a_snapshot_of_its_fresh_fits(tmp_path):
    from types import SimpleNamespace

    from fidus_lab.daemon import Daemon

    d = SimpleNamespace(model_path=tmp_path / "model.json", snapshots=ModelSnapshots(tmp_path))
    Daemon._fresh_or_saved(d, _enrolled(ME), {"progress": 0.5, "ready": False})
    assert len(list((tmp_path / "models").glob("*.json"))) == 1
