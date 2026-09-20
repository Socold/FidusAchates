"""`python -m fidus_lab <trace>`: analyse a reduced trace and print the report.

Enrolment on the same trace's first segments is a placeholder for a real
enrolment; this is a demonstration runner, not the operational path.
"""

from __future__ import annotations

import sys

from .analyze import analyze_segments
from .engine import IdentityEngine
from .experts import KeystrokeTemplate
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
    # Placeholder enrolment: fit on all segments (a real run enrols separately).
    tpl = KeystrokeTemplate.fit(segments)
    engine = IdentityEngine(genuine=tpl, reference=tpl)
    report = analyze_segments(segments, engine, SanctionRegistry())
    print(report.as_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
