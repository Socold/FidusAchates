"""`python -m fidus_lab <trace>`: analyse a reduced trace and print the report.

Enrolment uses a temporal split: the first half of the segments enrols the
genuine template, the second half is evaluated against it, as the evaluation
protocol requires (never random). No impostor population is enrolled here, so
the Identity expert uses its wide fallback reference and says so. With too few
segments to split, only the Attribution channel is meaningful, and the report
says that too.
"""

from __future__ import annotations

import sys

from .analyze import analyze_segments
from .engine import IdentityEngine
from .experts import KeystrokeTemplate, PointerTemplate
from .modes import fit_modes
from .registry import SanctionRegistry
from .segment import segment_trace
from .trace import read_trace


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m fidus_lab <trace.fidustr>", file=sys.stderr)
        return 2
    segments = list(segment_trace(read_trace(argv[0])))
    if not segments:
        print("no segments in trace")
        return 0
    enrol, test = temporal_split(segments)
    if not enrol:
        print("note: too few segments for a temporal split; Identity is not "
              "enrolled, only the Attribution channel is meaningful here")
        tpl = KeystrokeTemplate.fit(segments)
        ptr = PointerTemplate.fit(segments)
        modes = [tpl]
        test = segments
    else:
        modes = fit_modes(enrol)
        tpl = modes[0]
        ptr = PointerTemplate.fit(enrol)
        print(f"enrolled on the first {len(enrol)} segment(s) as {len(modes)} "
              f"mode(s), evaluating the next {len(test)}; impostor reference: "
              f"wide fallback (no impostor population enrolled)")
    engine = IdentityEngine(genuine=tpl, reference=None,
                            pointer=ptr if ptr.models else None,
                            modes=modes if len(modes) > 1 else None)
    report = analyze_segments(test, engine, SanctionRegistry())
    print(report.as_text())
    return 0


def temporal_split(segments: list, min_each: int = 2) -> tuple[list, list]:
    """First half to enrol, second half to evaluate. Empty enrol if too few."""
    half = len(segments) // 2
    if half < min_each or len(segments) - half < min_each:
        return [], segments
    return segments[:half], segments[half:]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
