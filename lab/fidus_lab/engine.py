"""The Identity decision engine over a segment stream (ADR-0007).

Ties the keystroke expert, logistic fusion and the CUSUM detector into a running
decision. This is the Python reference that the Rust agent will later have to
match by replay (FR-71). The Attribution channel lives in attribution.py and
policy.py; this file is the Identity channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import Cusum, LogisticFusion, probability_from_evidence
from .experts import KeystrokeExpert, KeystrokeTemplate
from .segment import Segment


@dataclass
class IdentityEngine:
    genuine: KeystrokeTemplate
    reference: KeystrokeTemplate
    cusum_h: float = 25.0
    prior_db: float = -10.0
    expert: KeystrokeExpert = field(default_factory=KeystrokeExpert)
    fusion: LogisticFusion = field(default_factory=LogisticFusion)
    min_quality: int = 4

    def __post_init__(self) -> None:
        self._cusum = Cusum(h=self.cusum_h)

    def step(self, seg: Segment) -> "Decision":
        e, n = self.expert.evidence(seg, self.genuine, self.reference)
        # Quality gate: a segment with too few observations does not vote.
        if n < self.min_quality:
            return Decision(seg, evidence_db=0.0, cumulative=self._cusum.s,
                            p_impostor=self._p(self._cusum.s), alarmed=False, quality=n)
        fused = self.fusion.fuse({self.expert.name: e})
        alarmed = self._cusum.update(fused)
        # The statistic at the moment of decision, before any reset, is what
        # the decision reports and what the probability is derived from.
        s_at_decision = self._cusum.s
        if alarmed:
            # L4: alert, full decision event, and the statistic resets so that
            # one alarm does not make every later window "alarmed" for good
            # (decision engine 4.3).
            self._cusum.reset()
        return Decision(seg, evidence_db=fused, cumulative=s_at_decision,
                        p_impostor=self._p(s_at_decision), alarmed=alarmed, quality=n)

    def _p(self, s: float) -> float:
        return probability_from_evidence(s, self.prior_db)

    def reset(self) -> None:
        self._cusum.reset()


@dataclass(frozen=True)
class Decision:
    segment: Segment
    evidence_db: float
    cumulative: float
    p_impostor: float
    alarmed: bool
    quality: int
