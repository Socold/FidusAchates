"""Distribution divergences for template stability (enrolment criterion C2).

Jensen-Shannon divergence between two Gaussians (our latencies are Gaussian in
log space) by numerical integration on a shared grid: bounded in [0, 1] with a
base-2 log, deterministic, standard library only. Template stability is the mean
JS over the classes the two templates share.
"""

from __future__ import annotations

import math

from .experts import KeystrokeTemplate
from .stats import LogNormal


def _gauss_pdf(x: float, mu: float, sigma: float) -> float:
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))


def gaussian_js(mu1: float, s1: float, mu2: float, s2: float, points: int = 400) -> float:
    """Jensen-Shannon divergence (base 2, in [0,1]) between two Gaussians."""
    lo = min(mu1 - 5 * s1, mu2 - 5 * s2)
    hi = max(mu1 + 5 * s1, mu2 + 5 * s2)
    if hi <= lo:
        return 0.0
    step = (hi - lo) / points

    def kl_term(p: float, m: float) -> float:
        if p <= 0 or m <= 0:
            return 0.0
        return p * math.log2(p / m)

    js = 0.0
    for i in range(points + 1):
        x = lo + i * step
        p = _gauss_pdf(x, mu1, s1)
        q = _gauss_pdf(x, mu2, s2)
        m = 0.5 * (p + q)
        w = step * (0.5 if i in (0, points) else 1.0)  # trapezoid
        js += w * 0.5 * (kl_term(p, m) + kl_term(q, m))
    return max(0.0, min(1.0, js))


def _mean_js(a: dict[int, LogNormal], b: dict[int, LogNormal]) -> float | None:
    shared = set(a) & set(b)
    if not shared:
        return None
    total = sum(gaussian_js(a[k].mu, a[k].sigma, b[k].mu, b[k].sigma) for k in shared)
    return total / len(shared)


def template_stability(a: KeystrokeTemplate, b: KeystrokeTemplate) -> float:
    """Mean JS over shared hold and digraph classes. 0 = identical, higher =
    the template is still moving. Returns 1.0 if the two share nothing."""
    parts = [p for p in (_mean_js(a.hold, b.hold), _mean_js(a.digraph, b.digraph)) if p is not None]
    if not parts:
        return 1.0
    return sum(parts) / len(parts)
