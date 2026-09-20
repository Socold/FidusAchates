from fidus_lab.explain import Contribution, describe, explain, waterfall


def test_waterfall_is_sorted_and_complete():
    contribs = {"A01_hold_log_mean": 2.0, "A03_dd_log_mean": -5.0, "A08_speed": 1.0}
    w = waterfall(contribs)
    assert [c.signal for c in w] == ["A03_dd_log_mean", "A01_hold_log_mean", "A08_speed"]
    # Nothing dropped: the waterfall sums to the total.
    assert abs(sum(c.decibans for c in w) - sum(contribs.values())) < 1e-9


def test_describe_reads_the_sign():
    assert "against the legitimate user" in describe(Contribution("A03_dd_log_mean", 7.2))
    assert "for the legitimate user" in describe(Contribution("A01_hold_log_mean", -3.0))


def test_explanation_splits_for_and_against():
    contribs = {"A03_dd_log_mean": 6.0, "A01_hold_log_mean": -2.0, "E03_dd_cv": 4.0}
    e = explain(contribs, channel="Identity")
    assert e.channel == "Identity"
    assert abs(e.total_db - 8.0) < 1e-9
    assert len(e.top_against) == 2   # dd and cv
    assert len(e.top_for) == 1       # hold
    text = e.as_text()
    assert "key-to-key rhythm" in text and "+8.0 dB" in text


def test_top_n_caps_each_side():
    contribs = {f"A0{i}_dd_log_mean": float(i) for i in range(1, 9)}
    e = explain(contribs, top_n=3)
    assert len(e.top_against) == 3
