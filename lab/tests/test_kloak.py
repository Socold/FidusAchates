"""The kloak model and its CMU protocols, on synthetic rows. No real data."""

import random

from fidus_lab.corpus import cmu_columns, load_cmu
from fidus_lab.kloak import (
    cmu_events,
    cmu_from_events,
    obfuscate_cmu,
    obfuscate_corpus,
    obfuscate_times,
)
from fidus_lab.kloak_eval import lag, noise, verify_and_identify, windowed
from tests.test_public_corpora import _cmu_csv


def test_delays_are_bounded_and_order_is_kept():
    rng = random.Random(1)
    times = sorted(random.Random(2).uniform(0, 2000) for _ in range(500))
    out, last = obfuscate_times(times, 100, rng)
    assert last == out[-1]
    assert out == sorted(out)
    for t, r in zip(times, out, strict=True):
        assert 0 <= r - int(t) <= 100


def test_a_burst_raises_the_lower_bound():
    # Ten events in the same millisecond: each waits for the one before it,
    # so the later ones are pushed toward the maximum delay.
    out, _ = obfuscate_times([5.0] * 10, 100, random.Random(3))
    assert out == sorted(out)
    assert out[-1] - 5 >= out[0] - 5
    assert all(0 <= r - 5 <= 100 for r in out)


def test_zero_delay_keeps_only_the_millisecond_clock():
    out, _ = obfuscate_times([0.4, 1.7, 1.9, 10.2], 0, random.Random(0))
    assert out == [0, 1, 1, 10]


def test_the_schedule_is_deterministic_for_a_seed():
    times = [float(t) for t in range(0, 1000, 37)]
    a, _ = obfuscate_times(times, 100, random.Random(7))
    b, _ = obfuscate_times(times, 100, random.Random(7))
    assert a == b


def test_cmu_events_round_trip(tmp_path):
    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    s = load_cmu(path)[0]
    back = cmu_from_events(s.subject, cmu_events(s, cols).events, cols)
    # H and DD come back exactly; UD is rebuilt as DD - H, and the corpus rounds
    # its UD column on its own, so it may differ by one unit of the last digit.
    for c, x, y in zip(cols, s.features, back.features, strict=True):
        assert abs(x - y) < (2e-4 if c.startswith("UD.") else 1e-9)


def test_obfuscated_repetition_stays_within_the_delay(tmp_path):
    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    s = load_cmu(path)[0]
    o = obfuscate_cmu(s, cols, 50, random.Random(4))
    # A hold or a latency moves by at most the maximum delay plus the clock.
    for x, y in zip(s.features, o.features, strict=True):
        assert abs(x - y) <= 0.051
    same = obfuscate_cmu(s, cols, 0, random.Random(4))
    for x, y in zip(s.features, same.features, strict=True):
        assert abs(x - y) <= 0.001


def test_windows_follow_the_published_split_at_k1(tmp_path):
    path = _cmu_csv(tmp_path, subjects=3, reps=12)
    samples = load_cmu(path)
    w = windowed(samples, samples, 1, n_train=6, n_impostor=2)
    train, gen, imp = w["s000"]
    assert (len(train), len(gen), len(imp)) == (6, 6, 4)
    w3 = windowed(samples, samples, 3, n_train=6, n_impostor=2)
    train, gen, imp = w3["s000"]
    assert (len(train), len(gen), len(imp)) == (4, 2, 4)


def test_protocol_runs_end_to_end(tmp_path):
    path = _cmu_csv(tmp_path, subjects=3, reps=12)
    cols = cmu_columns(path)
    clean = load_cmu(path)
    obf = obfuscate_corpus(clean, cols, 100, seed=5)
    assert obfuscate_corpus(clean, cols, 100, seed=5)[3].features == obf[3].features
    res = verify_and_identify(windowed(clean, clean, 1, n_train=6, n_impostor=2))
    # The synthetic subjects are far apart: the clean protocol separates them.
    assert res["eer_mean"] < 0.1 and res["identification"] > 0.9
    assert 0.0 <= verify_and_identify(
        windowed(obf, obf, 1, n_train=6, n_impostor=2))["eer_mean"] <= 1.0
    lg = lag(clean, cols, 100)
    assert 0 < lg["mean_ms"] <= lg["p95_ms"] <= lg["max_ms"] <= 100
    nz = noise(clean, obf, cols)
    assert set(nz) == {"H", "DD", "UD"} and nz["DD"]["added_sd_ms"] > 0
