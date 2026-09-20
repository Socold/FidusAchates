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
    # The impostor reference. None means no impostor population is enrolled;
    # the expert then falls back to a wide reference around the genuine model,
    # which is weaker but honest. Never pass the genuine template here: the
    # LLR would be identically zero and the channel inert.
    reference: KeystrokeTemplate | None = None
    cusum_h: float = 25.0
    prior_db: float = -10.0
    expert: KeystrokeExpert = field(default_factory=KeystrokeExpert)
    fusion: LogisticFusion = field(default_factory=LogisticFusion)
    min_quality: int = 4

    def __post_init__(self) -> None:
        self._cusum = Cusum(h=self.cusum_h)
        if self.reference is not None and self.reference is self.genuine:
            raise ValueError(
                "reference must not be the genuine template: evidence would be "
                "identically zero. Pass None to use the wide fallback."
            )

    @property
    def reference_kind(self) -> str:
        return "population" if self.reference is not None else "wide-fallback"

    def step(self, seg: Segment) -> "Decision":
        e, n = self.expert.evidence(seg, self.genuine, self.reference or KeystrokeTemplate())
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
