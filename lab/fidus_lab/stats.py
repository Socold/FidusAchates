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
