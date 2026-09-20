"""Small statistical helpers, standard library only.

Latencies live on a log scale (design review B7): typing and pointing times are
right-skewed, close to log-normal, so we fit a Gaussian to their logarithm. A
robust variant (median / MAD) is kept for enrolment, where outliers are the
rule.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class LogNormal:
    """A Gaussian on log-values: the model for a latency signal."""

    mu: float          # mean of log(x)
    sigma: float       # std of log(x), floored away from zero
    n: int             # observations it was fitted on

    SIGMA_FLOOR = 1e-3

    @classmethod
    def fit(cls, values: list[float]) -> "LogNormal":
        logs = [math.log(v) for v in values if v > 0]
        if len(logs) < 2:
            raise ValueError("need at least two positive values")
        mu = statistics.fmean(logs)
        sigma = max(statistics.stdev(logs), cls.SIGMA_FLOOR)
        return cls(mu=mu, sigma=sigma, n=len(logs))

    def logpdf(self, x: float) -> float:
        """log density at x (natural log). -inf for x <= 0."""
        if x <= 0:
            return -math.inf
        lx = math.log(x)
        z = (lx - self.mu) / self.sigma
        # log of the log-normal density.
        return -math.log(x) - math.log(self.sigma) - 0.5 * math.log(2 * math.pi) - 0.5 * z * z

    def z(self, x: float) -> float:
        return (math.log(x) - self.mu) / self.sigma if x > 0 else math.inf


@dataclass
class Welford:
    """Streaming mean and variance, no stored samples (NFR-2)."""

    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def add(self, x: float) -> None:
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.m2 += d * (x - self.mean)

    @property
    def variance(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)


def median_mad(values: list[float]) -> tuple[float, float]:
    """Median and median absolute deviation, scaled to a std estimate."""
    if not values:
        raise ValueError("empty")
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values])
    return med, 1.4826 * mad


@dataclass(frozen=True)
class LogNormalMixture:
    """A two-component Gaussian mixture on log-values (decision engine 3).

    The remedy for a bimodal signal: a single log-normal fitted to two regimes
    inflates its sigma and swallows anyone near the centre, which is how a
    close impostor went undetected (off-model validation). Two tight components
    keep the density low in the valley between the regimes.

    Fitted by EM, standard library only, deterministic. `mu` and `sigma` expose
    the mixture's overall moments so code that only needs an envelope (template
    stability, bounded updates) keeps working.
    """

    weights: tuple[float, float]
    mus: tuple[float, float]
    sigmas: tuple[float, float]
    n: int

    SIGMA_FLOOR = 1e-3

    @classmethod
    def fit(
        cls, values: list[float], iterations: int = 60, trim_mad: float = 3.0
    ) -> "LogNormalMixture":
        """Fit by EM on log-values, after dropping heavy-tail outliers beyond
        `trim_mad` MADs of the median. Without the trim, a few extreme values
        get absorbed into one component and inflate its sigma, hiding a real
        bimodality (seen on synthetic data with 3 % four-fold holds)."""
        raw = sorted(math.log(v) for v in values if v > 0)
        if len(raw) < 4:
            raise ValueError("need at least four positive values")
        med = raw[len(raw) // 2]
        mad = sorted(abs(x - med) for x in raw)[len(raw) // 2] * 1.4826 or cls.SIGMA_FLOOR
        logs = [x for x in raw if abs(x - med) <= trim_mad * mad] or raw
        n = len(logs)
        # Init from the lower and upper quartiles, equal weights, shared spread.
        q1, q3 = logs[n // 4], logs[(3 * n) // 4]
        spread = max(statistics.pstdev(logs), cls.SIGMA_FLOOR)
        w = [0.5, 0.5]
        mu = [q1, q3]
        sg = [spread / 2, spread / 2]
        for _ in range(iterations):
            # E step: responsibilities of component 0 for each point.
            resp0 = []
            for x in logs:
                p0 = w[0] * _gauss(x, mu[0], sg[0])
                p1 = w[1] * _gauss(x, mu[1], sg[1])
                tot = p0 + p1
                resp0.append(p0 / tot if tot > 0 else 0.5)
            # M step.
            n0 = sum(resp0)
            n1 = n - n0
            if n0 < 1e-9 or n1 < 1e-9:
                break
            w = [n0 / n, n1 / n]
            mu = [
                sum(r * x for r, x in zip(resp0, logs, strict=True)) / n0,
                sum((1 - r) * x for r, x in zip(resp0, logs, strict=True)) / n1,
            ]
            var0 = sum(r * (x - mu[0]) ** 2 for r, x in zip(resp0, logs, strict=True)) / n0
            var1 = sum((1 - r) * (x - mu[1]) ** 2 for r, x in zip(resp0, logs, strict=True)) / n1
            sg = [max(math.sqrt(var0), cls.SIGMA_FLOOR), max(math.sqrt(var1), cls.SIGMA_FLOOR)]
        # Order components by mean so callers can match them.
        if mu[0] > mu[1]:
            w, mu, sg = w[::-1], mu[::-1], sg[::-1]
        return cls(weights=(w[0], w[1]), mus=(mu[0], mu[1]), sigmas=(sg[0], sg[1]), n=n)

    def logpdf(self, x: float) -> float:
        if x <= 0:
            return -math.inf
        lx = math.log(x)
        dens = sum(
            w * _gauss(lx, m, s)
            for w, m, s in zip(self.weights, self.mus, self.sigmas, strict=True)
        )
        if dens <= 0:
            return -math.inf
        # density of x = density of log x / x
        return math.log(dens) - lx

    def loglik(self, values: list[float]) -> float:
        return sum(self.logpdf(v) for v in values if v > 0)

    @property
    def mu(self) -> float:
        """Overall mean of log-values (the envelope)."""
        return sum(w * m for w, m in zip(self.weights, self.mus, strict=True))

    @property
    def sigma(self) -> float:
        """Overall std of log-values (the envelope)."""
        m = self.mu
        var = sum(
            w * (s * s + (mm - m) ** 2)
            for w, mm, s in zip(self.weights, self.mus, self.sigmas, strict=True)
        )
        return max(math.sqrt(var), self.SIGMA_FLOOR)

    @property
    def separation(self) -> float:
        """Distance between the two means in units of the pooled sigma, so one
        tail-inflated component cannot veto a real bimodality on its own."""
        pooled = math.sqrt((self.sigmas[0] ** 2 + self.sigmas[1] ** 2) / 2)
        return abs(self.mus[1] - self.mus[0]) / max(pooled, self.SIGMA_FLOOR)


def _gauss(x: float, mu: float, sigma: float) -> float:
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))


Distribution = LogNormal | LogNormalMixture


def fit_best(
    values: list[float],
    min_n_for_mixture: int = 20,
    min_separation: float = 1.5,
    bic_margin: float = 6.0,
) -> Distribution:
    """A single log-normal, or a two-component mixture if the data is clearly
    bimodal: the mixture must win on BIC by a margin AND its components must be
    separated, so a merely skewed or heavy-tailed sample does not get split."""
    single = LogNormal.fit(values)
    positives = [v for v in values if v > 0]
    n = len(positives)
    if n < min_n_for_mixture:
        return single
    try:
        mix = LogNormalMixture.fit(positives)
    except ValueError:
        return single
    ll_single = sum(single.logpdf(v) for v in positives)
    ll_mix = mix.loglik(positives)
    bic_single = -2 * ll_single + 2 * math.log(n)
    bic_mix = -2 * ll_mix + 5 * math.log(n)
    if bic_mix + bic_margin < bic_single and mix.separation >= min_separation:
        return mix
    return single


def wide_reference(g: Distribution, factor: float = 3.0) -> LogNormal:
    """The no-population fallback: a unimodal reference centred on the genuine
    model, `factor` times as wide as the genuine model's *within-regime*
    spread. For a mixture that spread is the pooled component sigma, not the
    envelope: the envelope of a bimodal signal is inflated by the distance
    between the regimes, and a reference scaled from it was so wide that
    everything near the user looked genuine (the close-impostor failure)."""
    if isinstance(g, LogNormalMixture):
        pooled = math.sqrt((g.sigmas[0] ** 2 + g.sigmas[1] ** 2) / 2)
        return LogNormal(mu=g.mu, sigma=max(pooled * factor, LogNormal.SIGMA_FLOOR), n=g.n)
    return LogNormal(mu=g.mu, sigma=g.sigma * factor, n=g.n)
