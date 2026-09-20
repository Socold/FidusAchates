"""Evaluation metrics (research/EVALUATION-PROTOCOL.md).

Primary: ANIA, ANGA, TTD (continuous-authentication metrics). Secondary: FAR,
FRR, EER, DET points, kept for comparison with the state of the art. Every
number states its decision unit; mixing per-window and cumulative is the classic
way to get flattering, false figures.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorRates:
    threshold: float
    far: float  # impostor scores accepted as genuine
    frr: float  # genuine scores rejected


def _rate(scores: list[float], threshold: float, above_is_positive: bool) -> float:
    if not scores:
        return 0.0
    if above_is_positive:
        hits = sum(1 for s in scores if s >= threshold)
    else:
        hits = sum(1 for s in scores if s < threshold)
    return hits / len(scores)


def far_frr(
    genuine: list[float], impostor: list[float], threshold: float
) -> ErrorRates:
    """Higher score = more impostor-like. FAR: impostor below threshold
    (accepted). FRR: genuine at/above threshold (rejected)."""
    far = _rate(impostor, threshold, above_is_positive=False)
    frr = _rate(genuine, threshold, above_is_positive=True)
    return ErrorRates(threshold, far, frr)


def eer(genuine: list[float], impostor: list[float], steps: int = 400) -> float:
    """Equal error rate by sweeping the threshold over the score range."""
    if not genuine or not impostor:
        return float("nan")
    lo = min(min(genuine), min(impostor))
    hi = max(max(genuine), max(impostor))
    if hi == lo:
        return 0.5
    best = 1.0
    for i in range(steps + 1):
        t = lo + (hi - lo) * i / steps
        r = far_frr(genuine, impostor, t)
        best = min(best, max(r.far, r.frr))
    return best


def det_points(
    genuine: list[float], impostor: list[float], steps: int = 200
) -> list[tuple[float, float]]:
    """(FAR, FRR) points for a DET curve."""
    if not genuine or not impostor:
        return []
    lo = min(min(genuine), min(impostor))
    hi = max(max(genuine), max(impostor))
    pts = []
    for i in range(steps + 1):
        t = lo + (hi - lo) * i / steps
        r = far_frr(genuine, impostor, t)
        pts.append((r.far, r.frr))
    return pts


@dataclass(frozen=True)
class RunLengths:
    anga: float | None  # mean genuine actions before a false alarm
    ania: float | None  # mean impostor actions before detection
    ttd_median: float | None  # median actions to detect, impostor sessions


def run_lengths(
    genuine_runs: list[int | None], impostor_runs: list[int | None]
) -> RunLengths:
    """From per-session run lengths. A None genuine run means no false alarm in
    that session; a None impostor run means the impostor was never caught."""
    ga = [r for r in genuine_runs if r is not None]
    ia = [r for r in impostor_runs if r is not None]
    anga = sum(ga) / len(ga) if ga else None
    ania = sum(ia) / len(ia) if ia else None
    ttd = None
    if ia:
        s = sorted(ia)
        m = len(s) // 2
        ttd = float(s[m]) if len(s) % 2 else (s[m - 1] + s[m]) / 2
    return RunLengths(anga=anga, ania=ania, ttd_median=ttd)
