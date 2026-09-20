"""End-to-end offline analysis of a trace: the whole pipeline in one place.

Reads a reduced trace, segments it, and for each segment reports the actor
label (Attribution), the Identity decision with its explanation, and the outcome
of the malice policy. Also groups the segments into profiles to answer 'how many
people'. This is the offline runner the console will later stream from.
"""

from __future__ import annotations

from dataclasses import dataclass

from .attribution import Attribution, attribute
from .engine import IdentityEngine
from .experts import KeystrokeTemplate
from .explain import Explanation, explain
from .policy import Outcome, decide, stub_sensitivity
from .registry import SanctionRegistry
from .segment import Segment, segment_trace
from .trace import read_trace


@dataclass
class SegmentReport:
    index: int
    n_events: int
    segment: Segment
    attribution: Attribution
    identity_p_impostor: float
    identity_alarmed: bool
    outcome: Outcome
    explanation: Explanation


@dataclass
class AnalysisReport:
    segments: list[SegmentReport]

    @property
    def n_segments(self) -> int:
        return len(self.segments)

    def outcomes(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.segments:
            counts[s.outcome.value] = counts.get(s.outcome.value, 0) + 1
        return counts

    def as_text(self) -> str:
        lines = [f"{self.n_segments} segment(s)"]
        for s in self.segments:
            lines.append(
                f"  #{s.index} {s.n_events:3d} events  "
                f"actor={s.attribution.label.value:24s} "
                f"P(impostor)={s.identity_p_impostor:.2f}  "
                f"-> {s.outcome.value}"
            )
        by = self.outcomes()
        lines.append("outcomes: " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())))
        return "\n".join(lines)


def analyze_segments(
    segments: list[Segment],
    engine: IdentityEngine,
    registry: SanctionRegistry,
) -> AnalysisReport:
    reports: list[SegmentReport] = []
    for i, seg in enumerate(segments, start=1):
        a = attribute(seg, registry)
        d = engine.step(seg)
        exp = explain(d.contributions, channel="Identity")
        outcome = decide(a.label, identity_diverged=d.alarmed,
                         sensitivity=stub_sensitivity(seg))
        reports.append(SegmentReport(
            index=i, n_events=seg.n_events, segment=seg, attribution=a,
            identity_p_impostor=d.p_impostor, identity_alarmed=d.alarmed,
            outcome=outcome, explanation=exp,
        ))
    return AnalysisReport(reports)


def analyze_trace(
    path: str,
    genuine: KeystrokeTemplate,
    reference: KeystrokeTemplate | None = None,
    registry: SanctionRegistry | None = None,
) -> AnalysisReport:
    segments = list(segment_trace(read_trace(path)))
    engine = IdentityEngine(genuine=genuine, reference=reference)
    return analyze_segments(segments, engine, registry or SanctionRegistry())
