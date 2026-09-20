"""The signal study picks discriminating signals and drops useless ones."""

from fidus_lab.segment import segment_trace
from fidus_lab.signals import FEATURE_NAMES, features
from fidus_lab.synth import Typist
from fidus_lab.selection import d_prime, greedy_select, rank_features


def feature_table(params, n=60, keys=40, seed0=0):
    cols: dict[str, list[float]] = {name: [] for name in FEATURE_NAMES}
    for s in range(n):
        recs = Typist(seed=seed0 + s, **params).type_segment(keys)
        seg = next(segment_trace(recs))
        f = features(seg)
        for name in FEATURE_NAMES:
            cols[name].append(f[name])
    return cols


# Genuine vs impostor differ mostly in hold and gap means, not in correction
# rate (both never correct) -> that feature should rank low and be dropped.
GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.30)
IMP = dict(hold_mu=11.9, hold_sigma=0.35, gap_mu=12.1, gap_sigma=0.40)


def test_discriminating_feature_outranks_useless_one():
    g = feature_table(GEN, seed0=0)
    i = feature_table(IMP, seed0=1000)
    ranked = rank_features(g, i)
    names = [r.name for r in ranked]
    # Hold mean separates the two; correction rate (identical, ~0) does not.
    assert names.index("A01_hold_log_mean") < names.index("A10_correction_rate")
    assert dict((r.name, r.d_prime) for r in ranked)["A10_correction_rate"] < 0.5


def test_greedy_selects_a_small_useful_subset():
    g = feature_table(GEN, seed0=0)
    i = feature_table(IMP, seed0=1000)
    chosen = greedy_select(g, i, max_features=15)
    assert 0 < len(chosen) <= 15
    # It must pick at least one of the genuinely discriminating timing means.
    assert any(n.startswith(("A01", "A02", "A03")) for n in chosen)
    # The near-useless correction rate should not be chosen.
    assert "A10_correction_rate" not in chosen


def test_d_prime_zero_for_identical():
    assert d_prime([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) < 1e-9
