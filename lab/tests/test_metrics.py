from fidus_lab.metrics import eer, far_frr, run_lengths


def test_perfectly_separable_has_zero_eer():
    genuine = [0.0, 0.1, 0.2]     # low = genuine-like
    impostor = [5.0, 5.1, 5.2]    # high = impostor-like
    assert eer(genuine, impostor) < 0.01


def test_far_frr_directions():
    genuine = [0.0, 1.0]
    impostor = [4.0, 5.0]
    r = far_frr(genuine, impostor, threshold=2.5)
    assert r.far == 0.0 and r.frr == 0.0


def test_run_lengths():
    rl = run_lengths(genuine_runs=[None, None, 100], impostor_runs=[3, 5, None])
    assert rl.anga == 100
    assert rl.ania == 4
    assert rl.ttd_median == 4
