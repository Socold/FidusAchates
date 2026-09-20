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
