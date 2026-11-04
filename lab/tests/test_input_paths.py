"""Re-timing buffers, remote hops and forgeries, on synthetic rows. No real data."""

import random

from fidus_lab.corpus import ScaledManhattan, cmu_columns, load_cmu
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.input_paths import apply, cadence, foreign, lag_ms, remote
from fidus_lab.input_paths_eval import burst_share, short_hold_share
from fidus_lab.kloak import cmu_events
from fidus_lab.mimicry_eval import (
    _features,
    expert_forgery,
    manhattan_forgery,
    threshold_at_eer,
)
from fidus_lab.public_eval import _rep_segment
from tests.test_public_corpora import _cmu_csv


def _events(t_downs, hold=50.0):
    ev = [(t, i, True) for i, t in enumerate(t_downs)]
    ev += [(t + hold, i, False) for i, t in enumerate(t_downs)]
    return sorted(ev, key=lambda e: (e[0], not e[2], e[1]))


def test_cadence_never_releases_a_key_before_it_is_typed():
    ev = _events([0, 50, 100, 700, 750])
    out, leaks = cadence(ev, 200.0, 80.0)
    downs = {i: t for t, i, d in out if d}
    assert downs == {0: 0, 1: 200, 2: 400, 3: 700, 4: 900}
    # Only key 3 came after its slot: its gap leaks.
    assert leaks == 1
    assert all(x >= 0 for x in lag_ms(ev, out))
    ups = {i: t for t, i, d in out if not d}
    assert all(ups[i] - downs[i] == 80.0 for i in downs)


def test_foreign_copies_the_donor_where_the_typist_is_faster():
    ev = _events([0, 10, 20])
    donor = _events([0, 150, 260], hold=70.0)
    out, leaks = foreign(ev, donor)
    downs = {i: t for t, i, d in out if d}
    assert downs == {0: 0, 1: 150, 2: 260} and leaks == 0


def test_remote_batches_events_and_keeps_their_order():
    ev = _events([0, 3, 40, 90], hold=5.0)
    out, packets = remote(ev, random.Random(1), frame_ms=16.0, latency_ms=0.0, jitter_ms=0.0)
    times = [t for t, _, _ in out]
    assert times == sorted(times)
    assert [(i, d) for _, i, d in out] == [(i, d) for _, i, d in ev]
    # Down 0, down 1, up 0, up 1 share the first frame and land together.
    assert packets == 3
    assert times[3] - times[0] < 1.0


def test_detector_statistics_on_clean_and_remote(tmp_path):
    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    rows = load_cmu(path)[:6]
    assert burst_share(rows, cols) == 0.0
    # The synthetic typists are slow, so a long frame is needed to batch keys.
    hopped = [apply(r, cols, lambda e: remote(e, random.Random(2), frame_ms=200.0))[0]
              for r in rows]
    assert burst_share(hopped, cols) > 0.0
    assert 0.0 <= short_hold_share(hopped, cols) <= 1.0


def test_threshold_matches_the_eer_crossing():
    # At 4.0, one genuine score of four is rejected and one impostor score of
    # four is accepted: the crossing.
    assert threshold_at_eer([1.0, 2.0, 3.0, 4.0], [3.5, 5.0, 6.0, 7.0]) == 4.0


def test_forgeries_have_the_corpus_shape(tmp_path):
    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    rows = load_cmu(path)[:12]
    m = ScaledManhattan.train(rows)
    exact = manhattan_forgery(m, cols, random.Random(0), exact=True)
    # Only UD can differ: it is rebuilt as DD - H, and the synthetic rows round
    # their UD column on its own (the real corpus does not).
    assert m.score(exact) < 0.05
    noisy = manhattan_forgery(m, cols, random.Random(0), exact=False)
    assert len(noisy.features) == len(cols) and m.score(noisy) > 0
    tpl = KeystrokeTemplate.fit([_rep_segment(r, cols, False) for r in rows])
    f = expert_forgery(tpl, cols, random.Random(0))
    assert all(v > 0 for c, v in zip(cols, f.features, strict=True) if not c.startswith("UD."))
    # A forgery rebuilds into key events like any repetition.
    assert len(cmu_events(f, cols).events) == 2 * 11
    assert _features("x", [0.1] * 11, [0.2] * 10, cols).features[2] == 0.2 - 0.1


def test_deflate_removes_kloak_variance_from_holds_and_latencies(tmp_path):
    from fidus_lab.mimicry_eval import deflate

    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    m = ScaledManhattan.train(load_cmu(path)[:12])
    d = deflate(m, cols, 100)
    assert d.mean == m.mean
    for c, a, b in zip(cols, m.mad, d.mad, strict=True):
        if c.startswith("UD."):
            assert a == b
        else:
            assert 0.2 * a - 1e-12 <= b <= a
