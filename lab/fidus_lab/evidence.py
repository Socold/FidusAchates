"""Evidence in decibans, CUSUM accumulation and logistic fusion.

The decision engine of ADR-0007, as pure functions on scores. Evidence is
always evidence *for the impostor hypothesis*: up means suspicious.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def deciban(p_impostor: float, p_genuine: float) -> float:
    """10 log10 [ P(x|impostor) / P(x|genuine) ], from two densities."""
    if p_genuine <= 0:
        return math.inf if p_impostor > 0 else 0.0
    if p_impostor <= 0:
        return -math.inf
    return 10.0 * math.log10(p_impostor / p_genuine)


def deciban_from_logpdf(logp_impostor: float, logp_genuine: float) -> float:
    """Same, from natural-log densities (avoids underflow)."""
    return 10.0 / math.log(10.0) * (logp_impostor - logp_genuine)


def pooled(values: list[float], n_eff_max: int) -> float:
    """Total evidence of one signal over one segment, counting at most
    `n_eff_max` observations' worth. Up to that many, the plain sum; beyond,
    the mean per observation times `n_eff_max`. Observations of one signal in
    one segment are not independent (successive pointer motion events are one
    gesture), so summing hundreds of them let the most talkative signal drown
    every other. The mean keeps the direction and strength of the signal; the
    cap bounds how many independent votes it gets."""
    if not values:
        return 0.0
    if len(values) <= n_eff_max:
        return sum(values)
    return sum(values) / len(values) * n_eff_max


def probability_from_evidence(cumulative_db: float, prior_db: float = -10.0) -> float:
    """P(impostor) from cumulative evidence and a prior, both in decibans."""
    posterior = prior_db + cumulative_db
    return 1.0 / (1.0 + 10.0 ** (-posterior / 10.0))


@dataclass
class Cusum:
    """One-sided CUSUM change detector (ADR-0007).

    S = max(0, S + E). Alarm when S >= h; the caller resets after acting. No
    forgetting factor: the reflecting barrier at zero replaces it.
    """

    h: float
    s: float = 0.0
    peak: float = 0.0

    def update(self, evidence_db: float) -> bool:
        self.s = max(0.0, self.s + evidence_db)
        self.peak = max(self.peak, self.s)
        return self.s >= self.h

    def reset(self) -> None:
        self.s = 0.0

    @property
    def alarmed(self) -> bool:
        return self.s >= self.h


@dataclass
class RecognitionMeter:
    """How sure the engine is, right now, that the person is the enrolled
    user. Separate from the CUSUM, which only looks for a change and so stops
    at zero: this one sums evidence both ways, bounded on each side, so it can
    say "recognised" with more than the prior's confidence yet still turn
    within a few windows when someone else takes over. It never alarms.
    """

    bound_db: float = 20.0
    r: float = 0.0

    def update(self, evidence_db: float) -> float:
        self.r = min(self.bound_db, max(-self.bound_db, self.r + evidence_db))
        return self.r

    def reset(self) -> None:
        self.r = 0.0


@dataclass
class LogisticFusion:
    """Linear fusion of expert LLRs: E = b + sum(w_i * e_i).

    Weights are learned elsewhere (design review B3); here we just apply them,
    which keeps each expert's contribution exact and inspectable.
    """

    weights: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0

    def fuse(self, evidences: dict[str, float]) -> float:
        return self.bias + sum(
            self.weights.get(name, 1.0) * e for name, e in evidences.items()
        )

    def contributions(self, evidences: dict[str, float]) -> dict[str, float]:
        """Per-expert contribution to the sum, for the explanation view."""
        return {
            name: self.weights.get(name, 1.0) * e for name, e in evidences.items()
        }
