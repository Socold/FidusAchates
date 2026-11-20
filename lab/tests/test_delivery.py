"""Smoothed remote delivery, polling grids, and their evaluation, on
synthetic rows. No real data."""

import random

from fidus_lab.corpus import cmu_columns, load_cmu
from fidus_lab.delivery_eval import grid_alignment, repeated_gap_share, run
from fidus_lab.input_paths import playout, quantize, remote, spread
from fidus_lab.kloak import cmu_events, cmu_from_events
from tests.test_input_paths import _events
from tests.test_public_corpora import _cmu_csv


def _gaps(ev):
    ts = [t for t, _, _ in ev]
    return [b - a for a, b in zip(ts, ts[1:], strict=False)]


def test_spread_lays_a_packet_evenly_over_one_frame():
    burst = [(100.0, 0, True), (100.02, 1, True), (100.04, 0, False), (100.06, 1, False)]
    out, runs = spread(burst, frame_ms=16.0)
    assert runs == 1
    assert [round(g, 6) for g in _gaps(out)] == [4.0, 4.0, 4.0]
    assert all(a[0] >= b[0] for a, b in zip(out, burst, strict=True))


def test_spread_leaves_separate_events_alone():
    ev = _events([0, 200, 400])
    out, runs = spread(ev)
    assert runs == 0 and sorted(out) == sorted(ev)


def test_playout_restores_the_timing_when_the_buffer_is_deep():
    ev = _events([0, 137, 251, 420], hold=63.0)
    out, late = playout(ev, random.Random(0), buffer_ms=2000.0, tick_ms=1.0)
    assert late == 0
    assert all(abs((b - a) - 2000.0) <= 1.0
               for (a, _, _), (b, _, _) in zip(sorted(ev), sorted(out), strict=True))


def test_playout_counts_what_arrives_after_the_buffer():
    ev = _events([0, 137, 251, 420])
    _, late = playout(ev, random.Random(0), buffer_ms=1.0, latency_ms=150.0, jitter_ms=40.0)
    assert late == len(ev)


def test_quantize_puts_every_event_on_the_poll_grid():
    ev = _events([0.3, 101.7, 250.2], hold=55.5)
    out, moved = quantize(ev, 8.0, phase_ms=2.0)
    assert moved == len(ev)
    assert all((t - 2.0) % 8.0 == 0 for t, _, _ in out)
    assert all(t >= s for (t, _, _), (s, _, _) in zip(out, ev, strict=True))


def test_grid_and_repeated_gap_statistics(tmp_path):
    path = _cmu_csv(tmp_path, subjects=1, reps=5)
    cols = cmu_columns(path)
    rows = load_cmu(path)
    on8 = [cmu_from_events(r.subject, quantize(cmu_events(r, cols).events, 8.0)[0], cols)
           for r in rows]
    assert grid_alignment(on8, cols, 8.0) > 0.99
    assert grid_alignment(rows, cols, 8.0) < 0.6
    rng = random.Random(1)
    far = [cmu_from_events(r.subject, spread(remote(cmu_events(r, cols).events, rng,
                                                    latency_ms=150.0, jitter_ms=40.0)[0])[0],
                           cols) for r in rows]
    assert repeated_gap_share(far, cols) > repeated_gap_share(rows, cols)


def test_run_reports_both_studies(tmp_path):
    res = run(_cmu_csv(tmp_path, subjects=2, reps=400))
    assert set(res["careful_remote"]) >= {"raw", "spread", "playout_250ms"}
    rig = res["rig"]["keyboard_1ms"]
    assert set(rig) >= {"perfect", "rig_1ms", "rig_8ms"}
    # A 125 Hz rig in front of a 1000 Hz keyboard shows on the 8 ms grid.
    assert rig["rig_8ms"]["grid_detection"]["k5"]["grid_8ms"] < 0.05
