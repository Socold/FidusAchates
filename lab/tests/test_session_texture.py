"""The session texture model and evaluation, on synthetic rows. No real data."""

import math
import random

from fidus_lab.corpus import cmu_columns, load_cmu
from fidus_lab.metrics import eer_exact
from fidus_lab.mimicry_eval import lag1_autocorrelation
from fidus_lab.session_eval import (
    Texture,
    cholesky,
    first_component,
    log_vector,
    run,
    shrinkage_for,
    window_stats,
)
from tests.test_public_corpora import _cmu_csv


def _correlated(rng, n, d=6, drift=0.0):
    """Rows sharing one speed factor, optionally drifting from row to row."""
    rows, speed = [], 0.0
    for _ in range(n):
        speed = drift * speed + math.sqrt(1 - drift * drift) * rng.gauss(0, 1)
        rows.append([-2.0 + 0.3 * speed + 0.05 * rng.gauss(0, 1) for _ in range(d)])
    return rows


def test_cholesky_rebuilds_the_matrix():
    a = [[4.0, 2.0, 0.4], [2.0, 5.0, 1.0], [0.4, 1.0, 3.0]]
    low = cholesky(a)
    for i in range(3):
        for j in range(3):
            assert abs(sum(low[i][k] * low[j][k] for k in range(3)) - a[i][j]) < 1e-9


def test_first_component_points_along_the_shared_factor():
    v = first_component([[1.0, 0.9, 0.9], [0.9, 1.0, 0.9], [0.9, 0.9, 1.0]])
    assert all(abs(x - 1 / math.sqrt(3)) < 1e-6 for x in v)


def test_shrinkage_is_total_when_the_sample_is_too_small():
    assert shrinkage_for(5, 21) == 1.0
    assert shrinkage_for(400, 21) == 0.1


def test_texture_prefers_the_victims_correlations():
    rng = random.Random(1)
    model = Texture(_correlated(rng, 300))
    real = _correlated(rng, 1000)
    indep = model.draw(rng, 1000, diagonal=True)
    stolen = model.draw(rng, 1000)
    real_s = window_stats(model, real, 10)["texture"]
    e_indep = eer_exact(real_s, window_stats(model, indep, 10)["texture"])
    e_stolen = eer_exact(real_s, window_stats(model, stolen, 10)["texture"])
    assert e_indep < 0.05
    # A forger holding the full covariance is close to the real thing.
    assert e_stolen > 0.2 and e_stolen > 5 * e_indep


def test_drift_forger_reproduces_the_speed_autocorrelation():
    rng = random.Random(2)
    model = Texture(_correlated(rng, 400, drift=0.7))
    assert model.speed_autocorr > 0.5
    speeds = [model.speed(x) for x in model.draw(rng, 400, phi=model.speed_autocorr)]
    assert lag1_autocorrelation(speeds) > 0.5
    flat = [model.speed(x) for x in model.draw(rng, 400)]
    assert abs(lag1_autocorrelation(flat)) < 0.2


def test_log_vector_keeps_holds_and_down_downs_only(tmp_path):
    path = _cmu_csv(tmp_path, subjects=1, reps=1)
    cols = cmu_columns(path)
    v = log_vector(load_cmu(path)[0], cols)
    assert len(v) == sum(c.startswith(("H.", "DD.")) for c in cols)


def test_run_reports_every_forger_and_window(tmp_path):
    res = run(_cmu_csv(tmp_path, subjects=2, reps=400))
    assert res["victims"] == 2
    assert set(res["eer"]) >= {"laplace_independent", "gauss_full", "observed_5"}
    k1, k50 = res["eer"]["gauss_diagonal"]["k1"], res["eer"]["gauss_diagonal"]["k50"]
    assert "speed_autocorr" not in k1 and "speed_autocorr" in k50
    assert all(0.0 <= v <= 1.0 for v in k50.values())
