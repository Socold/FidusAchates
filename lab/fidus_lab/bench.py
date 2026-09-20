"""Run the Identity engine over labelled sessions and report protocol metrics.

Used both by tests and to produce a results directory in the format of
research/EVALUATION-PROTOCOL.md. Deterministic: same seeds give the same
numbers (FR-71).
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import IdentityEngine
from .metrics import RunLengths, eer, run_lengths


@dataclass
class BenchResult:
    eer_per_segment: float
    run_lengths: RunLengths
    n_genuine_sessions: int
    n_impostor_sessions: int


def evaluate(
    engine_factory,
    genuine_sessions: list[list],
    impostor_sessions: list[list],
) -> BenchResult:
    """Each session is a list of segments. A fresh engine per session models a
    fresh login. Returns per-segment EER and the run-length metrics."""
    g_scores: list[float] = []
    i_scores: list[float] = []
    genuine_runs: list[int | None] = []
    impostor_runs: list[int | None] = []

    for session in genuine_sessions:
        eng: IdentityEngine = engine_factory()
        first_alarm = None
        for i, seg in enumerate(session, start=1):
            d = eng.step(seg)
            g_scores.append(d.evidence_db)
            if d.alarmed and first_alarm is None:
                first_alarm = i
        genuine_runs.append(first_alarm)  # None if never (good)

    for session in impostor_sessions:
        eng = engine_factory()
        detected = None
        for i, seg in enumerate(session, start=1):
            d = eng.step(seg)
            i_scores.append(d.evidence_db)
            if d.alarmed:
                detected = i
                break
        impostor_runs.append(detected)  # None if never (bad)

    return BenchResult(
        eer_per_segment=eer(g_scores, i_scores),
        run_lengths=run_lengths(genuine_runs, impostor_runs),
        n_genuine_sessions=len(genuine_sessions),
        n_impostor_sessions=len(impostor_sessions),
    )
