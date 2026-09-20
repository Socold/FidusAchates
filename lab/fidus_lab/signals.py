"""Candidate signal extraction for the signal study (work package 4).

Turns a segment into named scalar features, the granularity at which
discriminating power is measured and signals are selected (ADR-0010, catalogue
parsimony target). Every feature is content-free: it comes from timings and the
classes the recorder already keeps.

Family A (keystroke) and the timing part of the meta family are covered here.
Pointer features (family B) join when pointer-rich traces exist; the framework
does not change.
"""

from __future__ import annotations

import math
import statistics

from .segment import Segment
from .trace import EventKind, KeyClass


def _hold_times(seg: Segment) -> list[float]:
    pending: dict[int, int] = {}
    out: list[float] = []
    for r in seg.records:
        if r.event.kind == EventKind.KEY_DOWN:
            pending[int(r.event.key_class)] = r.time_us
        elif r.event.kind == EventKind.KEY_UP:
            kc = int(r.event.key_class)
            if kc in pending:
                out.append(float(r.time_us - pending.pop(kc)))
    return out


def _key_down_times(seg: Segment) -> list[int]:
    return [r.time_us for r in seg.records if r.event.kind == EventKind.KEY_DOWN]


def _flight_times(seg: Segment) -> list[float]:
    """Release-to-next-press. Approximated as down-to-down minus hold is noisy;
    here we use up[i] to down[i+1] by walking events in order."""
    out: list[float] = []
    last_up: int | None = None
    for r in seg.records:
        if r.event.kind == EventKind.KEY_UP:
            last_up = r.time_us
        elif r.event.kind == EventKind.KEY_DOWN and last_up is not None:
            out.append(float(r.time_us - last_up))
            last_up = None
    return [f for f in out if f >= 0]


def _log_stats(values: list[float]) -> tuple[float, float]:
    """Mean and std of log values, the natural scale for latencies."""
    logs = [math.log(v) for v in values if v > 0]
    if len(logs) < 2:
        return float("nan"), float("nan")
    return statistics.fmean(logs), statistics.pstdev(logs)


def features(seg: Segment) -> dict[str, float]:
    """Named scalar features for one segment. NaN where undefined."""
    f: dict[str, float] = {}

    holds = _hold_times(seg)
    hm, hs = _log_stats(holds)
    f["A01_hold_log_mean"] = hm
    f["A01_hold_log_std"] = hs

    flights = _flight_times(seg)
    fm, fs = _log_stats(flights)
    f["A02_flight_log_mean"] = fm
    f["A02_flight_log_std"] = fs

    downs = _key_down_times(seg)
    intervals = [float(b - a) for a, b in zip(downs, downs[1:], strict=False)]
    im, is_ = _log_stats(intervals)
    f["A03_dd_log_mean"] = im
    f["A03_dd_log_std"] = is_

    # A08 typing speed: key-downs per second over the segment.
    dur_s = seg.duration_us / 1_000_000 if seg.duration_us > 0 else float("nan")
    f["A08_speed_keys_per_s"] = len(downs) / dur_s if dur_s and dur_s > 0 else float("nan")

    # A10 correction rate: share of correction-class key-downs.
    n_down = len(downs)
    n_corr = sum(
        1 for r in seg.records
        if r.event.kind == EventKind.KEY_DOWN and r.event.key_class == KeyClass.CORRECTION
    )
    f["A10_correction_rate"] = n_corr / n_down if n_down else float("nan")

    # E03 under-dispersion: coefficient of variation of dd intervals. Low = machine.
    if intervals:
        m = statistics.fmean(intervals)
        f["E03_dd_cv"] = statistics.pstdev(intervals) / m if m > 0 else float("nan")
    else:
        f["E03_dd_cv"] = float("nan")

    return f


FEATURE_NAMES = [
    "A01_hold_log_mean", "A01_hold_log_std",
    "A02_flight_log_mean", "A02_flight_log_std",
    "A03_dd_log_mean", "A03_dd_log_std",
    "A08_speed_keys_per_s", "A10_correction_rate", "E03_dd_cv",
]
