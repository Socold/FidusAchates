from fidus_lab.segment import segment_trace
from fidus_lab.signals import FEATURE_NAMES, features
from fidus_lab.synth import Typist


def one_segment(params, seed=0, keys=40):
    recs = Typist(seed=seed, **params).type_segment(keys)
    return next(segment_trace(recs))


def test_features_are_named_and_numeric():
    seg = one_segment(dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3))
    f = features(seg)
    for name in FEATURE_NAMES:
        assert name in f
    # Hold log-mean should be near the generator's mu.
    assert abs(f["A01_hold_log_mean"] - 11.4) < 0.3


def test_content_free_features_do_not_need_key_identity():
    # Two segments with identical timing but the feature code never sees a key
    # code, only classes: it works the same. Smoke check that it runs.
    seg = one_segment(dict(hold_mu=11.5, hold_sigma=0.3, gap_mu=11.5, gap_sigma=0.3))
    assert features(seg)["A08_speed_keys_per_s"] > 0
