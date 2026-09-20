"""The bimodal mixture: sharper genuine density where a close impostor hides."""

import math
import random

from fidus_lab.stats import LogNormal, LogNormalMixture, fit_best, wide_reference


def bimodal(n=300, seed=0, lo=11.2, hi=11.9, sg=0.15, tail=0.0):
    r = random.Random(seed)
    out = []
    for i in range(n):
        v = math.exp(r.gauss(lo if i % 2 else hi, sg))
        if r.random() < tail:
            v *= 4.0
        out.append(v)
    return out


def unimodal(n=300, seed=0, mu=11.5, sg=0.3):
    r = random.Random(seed)
    return [math.exp(r.gauss(mu, sg)) for _ in range(n)]


def test_bimodal_data_selects_the_mixture_and_unimodal_stays_single():
    assert isinstance(fit_best(bimodal()), LogNormalMixture)
    assert isinstance(fit_best(unimodal()), LogNormal)


def test_heavy_tails_do_not_hide_bimodality():
    """Found while fixing: 3 % four-fold outliers were absorbed into one
    component, inflating its sigma and dropping the separation below the
    guard. The robust trim keeps the two regimes visible."""
    mix = fit_best(bimodal(tail=0.03))
    assert isinstance(mix, LogNormalMixture)
    assert mix.separation >= 1.5


def test_mixture_is_sharper_in_the_valley():
    data = bimodal()
    single = LogNormal.fit(data)
    mix = LogNormalMixture.fit(data)
    valley = math.exp((11.2 + 11.9) / 2)
    assert mix.logpdf(valley) < single.logpdf(valley)


def test_envelope_moments_are_sane():
    mix = LogNormalMixture.fit(bimodal())
    assert 11.2 < mix.mu < 11.9
    assert mix.sigma > max(mix.sigmas)  # envelope wider than either component


def test_wide_reference_uses_component_width_for_a_mixture():
    """The old reference scaled the ENVELOPE by three, which for a bimodal
    signal was so wide that everything near the user looked genuine."""
    mix = LogNormalMixture.fit(bimodal())
    ref = wide_reference(mix)
    assert ref.sigma < 3.0 * mix.sigma
    pooled = math.sqrt((mix.sigmas[0] ** 2 + mix.sigmas[1] ** 2) / 2)
    assert abs(ref.sigma - 3.0 * pooled) < 1e-9
