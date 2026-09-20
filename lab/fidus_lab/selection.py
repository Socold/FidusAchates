"""Measure each candidate signal's discriminating power, and select a subset.

Work package 4: the catalogue is an inventory of candidates; this turns it into
a specification of about fifteen kept signals, by measurement rather than
intuition. Two steps:

1. Per-feature discriminating power, as d-prime between genuine and impostor
   feature values (a scale-free effect size). A feature that does not separate
   is dropped, not kept out of habit.
2. Greedy forward selection: add the feature that most improves a simple fused
   separability, until it stops improving. This handles redundancy, which
   per-feature ranking alone does not.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


def _clean(values: list[float]) -> list[float]:
    return [v for v in values if not math.isnan(v) and not math.isinf(v)]


def d_prime(genuine: list[float], impostor: list[float]) -> float:
    """Standardised mean difference: |mu_g - mu_i| / rms(sigma). Scale-free."""
    g, i = _clean(genuine), _clean(impostor)
    if len(g) < 2 or len(i) < 2:
        return 0.0
    mg, mi = statistics.fmean(g), statistics.fmean(i)
    sg, si = statistics.pstdev(g), statistics.pstdev(i)
    denom = math.sqrt((sg * sg + si * si) / 2) or 1e-9
    return abs(mg - mi) / denom


@dataclass(frozen=True)
class FeatureScore:
    name: str
    d_prime: float


def rank_features(
    genuine: dict[str, list[float]],
    impostor: dict[str, list[float]],
) -> list[FeatureScore]:
    """Per-feature discriminating power, most discriminating first."""
    scores = [
        FeatureScore(name, d_prime(genuine.get(name, []), impostor.get(name, [])))
        for name in genuine
    ]
    return sorted(scores, key=lambda s: s.d_prime, reverse=True)


def _fused_separability(
    names: list[str],
    genuine: dict[str, list[float]],
    impostor: dict[str, list[float]],
) -> float:
    """Separability of a naive equal-weight z-sum over the given features.

    Each feature is standardised on the genuine set, then summed; d-prime of the
    resulting score between genuine and impostor measures how well the subset
    separates together. Rows are aligned by index across features.
    """
    if not names:
        return 0.0
    stats = {}
    for n in names:
        g = _clean(genuine.get(n, []))
        if len(g) < 2:
            return 0.0
        mu = statistics.fmean(g)
        sd = statistics.pstdev(g) or 1e-9
        stats[n] = (mu, sd)

    def score_rows(rows: dict[str, list[float]]) -> list[float]:
        length = min(len(rows[n]) for n in names)
        out = []
        for r in range(length):
            s = 0.0
            ok = True
            for n in names:
                v = rows[n][r]
                if math.isnan(v) or math.isinf(v):
                    ok = False
                    break
                mu, sd = stats[n]
                s += (v - mu) / sd
            if ok:
                out.append(s)
        return out

    return d_prime(score_rows(genuine), score_rows(impostor))


def greedy_select(
    genuine: dict[str, list[float]],
    impostor: dict[str, list[float]],
    max_features: int = 15,
    min_gain: float = 0.02,
) -> list[str]:
    """Forward selection: add the feature that most improves fused separability,
    stop when the gain falls below min_gain or the cap is reached."""
    candidates = list(genuine.keys())
    chosen: list[str] = []
    current = 0.0
    while candidates and len(chosen) < max_features:
        best_name, best_val = None, current
        for c in candidates:
            val = _fused_separability(chosen + [c], genuine, impostor)
            if val > best_val:
                best_name, best_val = c, val
        if best_name is None or best_val - current < min_gain:
            break
        chosen.append(best_name)
        candidates.remove(best_name)
        current = best_val
    return chosen
