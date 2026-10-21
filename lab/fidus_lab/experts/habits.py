"""A habits expert: how I go about things, not how fast my fingers are.

The keystroke and pointer experts model durations. This one models choices and
shapes, each from the content-free trace (or the content-free focus category):

- B06 pointing time for distance: log time against log2(distance + 1), a
  Fitts-like law. The target width is unknown (positions are never stored), so
  this is the time-distance relation, not Fitts's law proper.
- B07 overshoot: how far past the target the pointer goes before coming back.
- B08 final micro-corrections: direction reversals in the last stretch.
- B15 approach direction: the direction of the last stretch before a click.
- B25 departure direction after a pause: which way the hand moves first.
- A16 shortcut repertoire: which shortcut classes I use, and how often.
- C02 application transitions: which category of application follows which.
- C03 opening sequence: the first applications of a session, in order.

Choices are categorical, scored against a smoothed categorical model; the
time-distance law is a regression with Gaussian residuals. Without an impostor
population, the reference is uniform over the categories (or three times the
residual spread for the law), the same honest-but-weak fallback as the other
experts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..context import CATEGORIES, OPENING_LENGTH
from ..evidence import deciban_from_logpdf, pooled
from ..segment import Segment
from ..stats import Categorical
from ..trace import EventKind, ShortcutClass

# A gesture starts after this long without motion; a departure counts only
# after a real pause (the hand at rest), which is longer.
REST_US = 300_000
PAUSE_US = 1_000_000
# Travel (in device counts) used to read a departure or an approach direction.
DIRECTION_TRAVEL = 20.0
# The final stretch where micro-corrections are counted.
FINAL_TRAVEL = 100.0
MIN_GESTURE_DISTANCE = 20.0

N_OCTANTS = 8
N_OVERSHOOT = 3   # none, small, large
N_MICRO = 4       # 0, 1, 2, 3 or more reversals
N_SHORTCUTS = len(ShortcutClass)
N_CATEGORIES = len(CATEGORIES)


@dataclass
class Gesture:
    """One pointer movement: from rest to a click, or from rest to rest."""

    rest_before_us: int
    # Cumulative positions (device counts) and their times, from (0, 0).
    path: list[tuple[int, float, float]] = field(default_factory=list)
    clicked: bool = False
    click_us: int | None = None

    @property
    def end(self) -> tuple[float, float]:
        return (self.path[-1][1], self.path[-1][2]) if self.path else (0.0, 0.0)

    @property
    def distance(self) -> float:
        x, y = self.end
        return math.hypot(x, y)


def gestures(seg: Segment) -> list[Gesture]:
    """Cut the segment's motion into gestures. Motion events with the same
    timestamp (one REL_X, one REL_Y) are one step."""
    out: list[Gesture] = []
    cur: Gesture | None = None
    last_motion: int | None = None
    x = y = 0.0
    for r in seg.records:
        k = r.event.kind
        if k == EventKind.MOTION:
            rest = r.time_us - last_motion if last_motion is not None else PAUSE_US
            if cur is None or rest >= REST_US:
                if cur is not None and cur.path:
                    out.append(cur)
                cur = Gesture(rest_before_us=rest, path=[(r.time_us, 0.0, 0.0)])
                x = y = 0.0
            x += r.event.dx
            y += r.event.dy
            if cur.path and cur.path[-1][0] == r.time_us:
                cur.path[-1] = (r.time_us, x, y)
            else:
                cur.path.append((r.time_us, x, y))
            last_motion = r.time_us
        elif k == EventKind.BUTTON_DOWN and cur is not None and not cur.clicked:
            cur.clicked = True
            cur.click_us = r.time_us
            out.append(cur)
            cur = None
    if cur is not None and len(cur.path) > 1:
        out.append(cur)
    return [g for g in out if len(g.path) > 1]


def octant(dx: float, dy: float) -> int:
    """0 right, 2 up, 4 left, 6 down (screen y grows downwards)."""
    angle = math.atan2(-dy, dx)
    return int(round(angle / (math.pi / 4))) % N_OCTANTS


def departure_direction(g: Gesture) -> int | None:
    if g.rest_before_us < PAUSE_US:
        return None
    for _, x, y in g.path:
        if math.hypot(x, y) >= DIRECTION_TRAVEL:
            return octant(x, y)
    return None


def approach_direction(g: Gesture) -> int | None:
    if not g.clicked or g.distance < MIN_GESTURE_DISTANCE:
        return None
    ex, ey = g.end
    for _, x, y in reversed(g.path):
        if math.hypot(ex - x, ey - y) >= DIRECTION_TRAVEL:
            return octant(ex - x, ey - y)
    return None


def overshoot_bin(g: Gesture) -> int | None:
    d = g.distance
    if not g.clicked or d < 5 * MIN_GESTURE_DISTANCE:
        return None
    ux, uy = g.end[0] / d, g.end[1] / d
    furthest = max(x * ux + y * uy for _, x, y in g.path)
    ratio = (furthest - d) / d
    return 0 if ratio < 0.02 else 1 if ratio < 0.10 else 2


def micro_corrections(g: Gesture) -> int | None:
    """Direction reversals along the gesture axis over the final stretch."""
    d = g.distance
    if not g.clicked or d < MIN_GESTURE_DISTANCE:
        return None
    ux, uy = g.end[0] / d, g.end[1] / d
    ex, ey = g.end
    tail = [(x, y) for _, x, y in g.path if math.hypot(ex - x, ey - y) <= FINAL_TRAVEL]
    signs = []
    for (x0, y0), (x1, y1) in zip(tail, tail[1:], strict=False):
        p = (x1 - x0) * ux + (y1 - y0) * uy
        if p != 0:
            signs.append(p > 0)
    reversals = sum(1 for a, b in zip(signs, signs[1:], strict=False) if a != b)
    return min(reversals, N_MICRO - 1)


def pointing_time(g: Gesture) -> tuple[float, float] | None:
    """(log2(D + 1), log of the time from gesture start to click in us)."""
    if not g.clicked or g.click_us is None or g.distance < MIN_GESTURE_DISTANCE:
        return None
    t = g.click_us - g.path[0][0]
    if t <= 0:
        return None
    return math.log2(g.distance + 1.0), math.log(t)


def shortcuts(seg: Segment, _gs: list[Gesture] | None = None) -> list[int]:
    return [
        int(r.event.shortcut) for r in seg.records
        if r.event.kind == EventKind.KEY_DOWN and r.event.shortcut != ShortcutClass.NONE
    ]


def transitions(seg: Segment, _gs: list[Gesture] | None = None) -> list[int]:
    return [e.previous * N_CATEGORIES + e.category for e in seg.context
            if e.previous is not None]


def openings(seg: Segment, _gs: list[Gesture] | None = None) -> list[int]:
    return [e.opening_rank * N_CATEGORIES + e.category for e in seg.context
            if e.opening_rank is not None and e.opening_rank < OPENING_LENGTH]


def _per_gesture(fn):
    # Extractors take the segment's gestures precomputed: cutting gestures is
    # the costly part, and five signals read the same ones.
    def extract(seg: Segment, gs: list[Gesture] | None = None) -> list[int]:
        gs = gestures(seg) if gs is None else gs
        return [v for v in (fn(g) for g in gs) if v is not None]
    return extract


# Categorical habits: name -> (extractor, number of categories).
_CATEGORICAL = {
    "B07_overshoot": (_per_gesture(overshoot_bin), N_OVERSHOOT),
    "B08_micro_corrections": (_per_gesture(micro_corrections), N_MICRO),
    "B15_approach": (_per_gesture(approach_direction), N_OCTANTS),
    "B25_departure": (_per_gesture(departure_direction), N_OCTANTS),
    "A16_shortcut": (shortcuts, N_SHORTCUTS),
    "C02_transition": (transitions, N_CATEGORIES * N_CATEGORIES),
    "C03_opening": (openings, OPENING_LENGTH * N_CATEGORIES),
}


@dataclass(frozen=True)
class TimeDistanceLaw:
    """log T = a + b log2(D + 1), with Gaussian residuals of spread sigma."""

    a: float
    b: float
    sigma: float
    n: int

    SIGMA_FLOOR = 0.05

    @classmethod
    def fit(cls, points: list[tuple[float, float]]) -> "TimeDistanceLaw":
        n = len(points)
        if n < 3:
            raise ValueError("need at least three pointings")
        mx = sum(p[0] for p in points) / n
        my = sum(p[1] for p in points) / n
        sxx = sum((p[0] - mx) ** 2 for p in points)
        b = sum((p[0] - mx) * (p[1] - my) for p in points) / sxx if sxx > 0 else 0.0
        a = my - b * mx
        res = [p[1] - (a + b * p[0]) for p in points]
        sigma = math.sqrt(sum(r * r for r in res) / max(n - 2, 1))
        return cls(a=a, b=b, sigma=max(sigma, cls.SIGMA_FLOOR), n=n)

    def logpdf(self, x: float, y: float, widen: float = 1.0) -> float:
        s = self.sigma * widen
        z = (y - (self.a + self.b * x)) / s
        return -math.log(s) - 0.5 * math.log(2 * math.pi) - 0.5 * z * z


@dataclass
class HabitTemplate:
    categorical: dict[str, Categorical] = field(default_factory=dict)
    law: TimeDistanceLaw | None = None

    @classmethod
    def fit(cls, segments: list[Segment], min_obs: int = 20) -> "HabitTemplate":
        values: dict[str, list[int]] = {k: [] for k in _CATEGORICAL}
        points: list[tuple[float, float]] = []
        for seg in segments:
            gs = gestures(seg)
            for name, (fn, _) in _CATEGORICAL.items():
                values[name].extend(fn(seg, gs))
            for g in gs:
                p = pointing_time(g)
                if p is not None:
                    points.append(p)
        cats = {
            name: Categorical.fit(values[name], k)
            for name, (_, k) in _CATEGORICAL.items()
            if len(values[name]) >= min_obs
        }
        law = TimeDistanceLaw.fit(points) if len(points) >= min_obs else None
        return cls(categorical=cats, law=law)

    @property
    def empty(self) -> bool:
        return not self.categorical and self.law is None


@dataclass
class HabitExpert:
    name: str = "habits"
    clamp_db: float = 6.0
    # The no-population reference for the law is this many times as wide.
    wide_factor: float = 3.0
    # At most this many observations' worth per signal and segment.
    n_eff_max: int = 20

    def evidence(
        self,
        seg: Segment,
        genuine: HabitTemplate,
        reference: HabitTemplate | None = None,
    ) -> tuple[dict[str, float], int]:
        per: dict[str, list[float]] = {}
        n = 0
        gs = gestures(seg)
        for name, (fn, k) in _CATEGORICAL.items():
            g = genuine.categorical.get(name)
            if g is None:
                continue
            r = (reference.categorical.get(name) if reference else None) or Categorical.uniform(k)
            for v in fn(seg, gs):
                e = deciban_from_logpdf(r.logpmf(v), g.logpmf(v))
                per.setdefault(name, []).append(self._clamp(e))
                n += 1
        if genuine.law is not None:
            ref_law = reference.law if reference and reference.law else None
            for g in gs:
                p = pointing_time(g)
                if p is None:
                    continue
                lg = genuine.law.logpdf(*p)
                lr = ref_law.logpdf(*p) if ref_law else genuine.law.logpdf(*p, widen=self.wide_factor)
                per.setdefault("B06_pointing_time", []).append(
                    self._clamp(deciban_from_logpdf(lr, lg)))
                n += 1
        return {k: pooled(v, self.n_eff_max) for k, v in per.items()}, n

    def _clamp(self, e: float) -> float:
        return max(-self.clamp_db, min(self.clamp_db, e))
