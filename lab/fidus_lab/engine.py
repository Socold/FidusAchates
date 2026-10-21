"""The Identity decision engine over a segment stream (ADR-0007).

Ties the experts (keystroke, pointer), logistic fusion and the CUSUM detector
into a running decision. Each expert returns per-signal evidence, the fusion is
a weighted sum over all of them, so every signal's contribution is exact and
the explanation is the sum read term by term. This is the Python reference the
Rust agent will later have to match by replay (FR-71).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import Cusum, LogisticFusion, RecognitionMeter, probability_from_evidence
from .experts import (
    HabitExpert,
    HabitTemplate,
    KeystrokeExpert,
    KeystrokeTemplate,
    PointerExpert,
    PointerTemplate,
)
from .segment import Segment


@dataclass
class IdentityEngine:
    genuine: KeystrokeTemplate
    # The impostor reference. None means no impostor population is enrolled;
    # the experts then fall back to a wide reference around the genuine model,
    # which is weaker but honest. Never pass the genuine template here: the
    # LLR would be identically zero and the channel inert.
    reference: KeystrokeTemplate | None = None
    # Pointer templates are optional: without them the engine is blind when
    # nobody types, which is exactly the gap the pointer expert closes.
    pointer: PointerTemplate | None = None
    pointer_reference: PointerTemplate | None = None
    # Modes: one keystroke template per regime of the same person (decision
    # engine 6.1). When given, a segment is scored against its best-matching
    # mode, so a person on two keyboards is not their own impostor, while an
    # impostor still has to be far from every mode. `genuine` is then only a
    # fallback and may be any of them.
    modes: list[KeystrokeTemplate] | None = None
    # Habits (shortcuts, pointing shape, application sequence): optional like
    # the pointer, with its own population reference when one is enrolled.
    habits: HabitTemplate | None = None
    habits_reference: HabitTemplate | None = None
    cusum_h: float = 25.0
    prior_db: float = -10.0
    keystroke_expert: KeystrokeExpert = field(default_factory=KeystrokeExpert)
    pointer_expert: PointerExpert = field(default_factory=PointerExpert)
    habit_expert: HabitExpert = field(default_factory=HabitExpert)
    fusion: LogisticFusion = field(default_factory=LogisticFusion)
    min_quality: int = 4
    # Bound of the recognition meter on each side, in decibans.
    recognition_bound_db: float = 20.0

    def __post_init__(self) -> None:
        self._cusum = Cusum(h=self.cusum_h)
        self._recognition = RecognitionMeter(bound_db=self.recognition_bound_db)
        if self.reference is not None and self.reference is self.genuine:
            raise ValueError(
                "reference must not be the genuine template: evidence would be "
                "identically zero. Pass None to use the wide fallback."
            )
        if self.pointer_reference is not None and self.pointer_reference is self.pointer:
            raise ValueError("pointer_reference must not be the genuine pointer template")
        if self.habits_reference is not None and self.habits_reference is self.habits:
            raise ValueError("habits_reference must not be the genuine habit template")

    @property
    def reference_kind(self) -> str:
        return "population" if self.reference is not None else "wide-fallback"

    def _keystroke_evidence(self, seg: Segment) -> tuple[dict[str, float], int]:
        """Against the best-matching mode when modes are enrolled: the mode
        with the least total evidence for the impostor hypothesis. Its
        per-signal contributions are what gets explained."""
        ref = self.reference or KeystrokeTemplate()
        candidates = self.modes or [self.genuine]
        best: tuple[dict[str, float], int] | None = None
        best_total = None
        for tpl in candidates:
            ev, n = self.keystroke_expert.evidence(seg, tpl, ref)
            total = sum(ev.values())
            if best is None or total < best_total:
                best, best_total = (ev, n), total
        return best  # type: ignore[return-value]

    def _collect(self, seg: Segment) -> tuple[dict[str, float], int]:
        """Per-signal evidence from every enrolled expert, and total quality."""
        ev, n = self._keystroke_evidence(seg)
        if self.pointer is not None:
            pev, pn = self.pointer_expert.evidence(
                seg, self.pointer, self.pointer_reference or PointerTemplate()
            )
            ev.update(pev)
            n += pn
        if self.habits is not None:
            hev, hn = self.habit_expert.evidence(seg, self.habits, self.habits_reference)
            ev.update(hev)
            n += hn
        return ev, n

    def step(self, seg: Segment) -> "Decision":
        contributions, n = self._collect(seg)
        # Quality gate: a segment with too few observations does not vote.
        if n < self.min_quality:
            return Decision(seg, evidence_db=0.0, cumulative=self._cusum.s,
                            p_impostor=self._p(self._cusum.s), alarmed=False,
                            quality=n, contributions={},
                            confidence=self._confidence())
        weighted = self.fusion.contributions(contributions)
        fused = self.fusion.fuse(contributions)
        alarmed = self._cusum.update(fused)
        self._recognition.update(fused)
        # The statistic at the moment of decision, before any reset, is what
        # the decision reports and what the probability is derived from.
        s_at_decision = self._cusum.s
        if alarmed:
            # L4: alert, full decision event, and the statistic resets so that
            # one alarm does not make every later window "alarmed" for good
            # (decision engine 4.3).
            self._cusum.reset()
        return Decision(seg, evidence_db=fused, cumulative=s_at_decision,
                        p_impostor=self._p(s_at_decision), alarmed=alarmed,
                        quality=n, contributions=weighted,
                        confidence=self._confidence())

    def _p(self, s: float) -> float:
        return probability_from_evidence(s, self.prior_db)

    def _confidence(self) -> float:
        """P(the enrolled user) from the recognition meter and the prior."""
        return 1.0 - probability_from_evidence(self._recognition.r, self.prior_db)

    def reset(self) -> None:
        self._cusum.reset()
        self._recognition.reset()


@dataclass(frozen=True)
class Decision:
    segment: Segment
    evidence_db: float
    cumulative: float
    p_impostor: float
    alarmed: bool
    quality: int
    # Weighted per-signal contributions; they sum to evidence_db minus the
    # fusion bias. This is what the explanation renders.
    contributions: dict[str, float] = field(default_factory=dict)
    # How sure the engine is that this is the enrolled user, from the
    # two-sided recognition meter; unlike 1 - p_impostor it is not floored at
    # the prior.
    confidence: float = 0.0
