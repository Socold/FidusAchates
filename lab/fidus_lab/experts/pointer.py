"""A pointer expert (family B), so the engine is not blind when nobody types.

From the reduced trace the recorder gives us content-free pointer behaviour:
relative motion deltas, wheel notches, button presses. Four signals, each a
latency-like quantity modelled log-normal like the keystroke ones:

- B01 velocity: pixels per millisecond over each motion event.
- B09 pause before click: from the last motion to the button-down.
- B10 click duration: button-down to button-up.
- B13 wheel cadence: interval between wheel notches.

The absolute position is never known (only deltas are stored), so nothing here
can locate what was clicked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..evidence import deciban_from_logpdf
from ..segment import Segment
from ..stats import Distribution, LogNormal, fit_best, wide_reference
from ..trace import EventKind


def _velocities(seg: Segment) -> list[float]:
    out: list[float] = []
    last_t: int | None = None
    for r in seg.records:
        if r.event.kind != EventKind.MOTION:
            continue
        if last_t is not None:
            dt_ms = (r.time_us - last_t) / 1000.0
            if 0 < dt_ms < 500:  # within one gesture
                dist = math.hypot(r.event.dx, r.event.dy)
                if dist > 0:
                    out.append(dist / dt_ms)
        last_t = r.time_us
    return out


def _pauses_before_click(seg: Segment) -> list[float]:
    out: list[float] = []
    last_motion: int | None = None
    for r in seg.records:
        if r.event.kind == EventKind.MOTION:
            last_motion = r.time_us
        elif r.event.kind == EventKind.BUTTON_DOWN and last_motion is not None:
            out.append(float(r.time_us - last_motion))
    return [p for p in out if p > 0]


def _click_durations(seg: Segment) -> list[float]:
    out: list[float] = []
    down: dict[int | None, int] = {}
    for r in seg.records:
        if r.event.kind == EventKind.BUTTON_DOWN:
            down[r.event.button] = r.time_us
        elif r.event.kind == EventKind.BUTTON_UP and r.event.button in down:
            out.append(float(r.time_us - down.pop(r.event.button)))
    return [d for d in out if d > 0]


def _wheel_intervals(seg: Segment) -> list[float]:
    times = [r.time_us for r in seg.records if r.event.kind == EventKind.WHEEL]
    return [float(b - a) for a, b in zip(times, times[1:], strict=False) if b > a]


_SIGNALS = {
    "B01_velocity": _velocities,
    "B09_pause_before_click": _pauses_before_click,
    "B10_click_duration": _click_durations,
    "B13_wheel_interval": _wheel_intervals,
}


@dataclass
class PointerTemplate:
    models: dict[str, Distribution] = field(default_factory=dict)

    @classmethod
    def fit(cls, segments: list[Segment], min_obs: int = 4) -> "PointerTemplate":
        values: dict[str, list[float]] = {k: [] for k in _SIGNALS}
        for seg in segments:
            for name, fn in _SIGNALS.items():
                values[name].extend(fn(seg))
        models = {k: fit_best(v) for k, v in values.items() if len(v) >= min_obs}
        return cls(models=models)


@dataclass
class PointerExpert:
    name: str = "pointer"
    clamp_db: float = 6.0

    def evidence(
        self,
        seg: Segment,
        genuine: PointerTemplate,
        reference: PointerTemplate,
    ) -> tuple[dict[str, float], int]:
        out: dict[str, float] = {}
        n = 0
        for name, fn in _SIGNALS.items():
            g = genuine.models.get(name)
            if g is None:
                continue
            r = reference.models.get(name)
            for x in fn(seg):
                logp_g = g.logpdf(x)
                logp_r = r.logpdf(x) if r is not None else self._wide(x, g)
                e = deciban_from_logpdf(logp_r, logp_g)
                e = max(-self.clamp_db, min(self.clamp_db, e))
                out[name] = out.get(name, 0.0) + e
                n += 1
        return out, n

    @staticmethod
    def _wide(x: float, g: Distribution) -> float:
        return wide_reference(g).logpdf(x)
