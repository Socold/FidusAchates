
from fidus_lab.evidence import (
    Cusum,
    LogisticFusion,
    deciban,
    probability_from_evidence,
)


def test_deciban_sign_and_zero():
    assert deciban(1.0, 1.0) == 0.0
    assert deciban(10.0, 1.0) == 10.0   # 10x more impostor-like -> +10 dB
    assert deciban(1.0, 10.0) == -10.0


def test_probability_uses_the_prior():
    # At S=0 the probability is the prior (-10 dB -> ~0.09).
    p0 = probability_from_evidence(0.0, prior_db=-10.0)
    assert abs(p0 - 1 / (1 + 10 ** 1.0)) < 1e-9
    # P=0.5 is reached at S = +10 dB with this prior.
    assert abs(probability_from_evidence(10.0, -10.0) - 0.5) < 1e-9


def test_cusum_reflects_at_zero_and_alarms():
    c = Cusum(h=20.0)
    # Negative (genuine) evidence cannot bank credit.
    for _ in range(10):
        c.update(-5.0)
    assert c.s == 0.0
    # Then sustained positive evidence crosses the threshold.
    fired = any(c.update(6.0) for _ in range(5))
    assert fired and c.alarmed


def test_fusion_contributions_sum_to_total():
    f = LogisticFusion(weights={"a": 2.0, "b": 0.5}, bias=1.0)
    ev = {"a": 3.0, "b": 4.0}
    total = f.fuse(ev)
    contribs = f.contributions(ev)
    assert abs(sum(contribs.values()) + f.bias - total) < 1e-9
