"""Learning curves: how much of my own activity the model needs before it
recognises me, and how fast it then catches someone else.

For a growing enrolment budget (minutes of active use, oldest first), fit the
templates on that much of my data only, then replay data the model never saw:

- my later sessions: how long until the evidence says "this is the owner"
  (time to recognise), and how many false alarms per hour of activity;
- someone else's sessions: the share caught, and how long it took (time to
  detect). Guest sessions are real people. Without any, impostors are
  *simulated* from my held-out data with distorted timings and habits; the
  report always says which kind each number comes from.

Times are active time (the sum of segment durations), never wall-clock time.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import asdict, dataclass, field, replace

from .engine import IdentityEngine
from .enrolment import CriteriaParams, EnrolmentTracker
from .experts import HabitTemplate, KeystrokeTemplate, PointerTemplate
from .modes import fit_modes
from .segment import Segment
from .trace import EventKind, Record, ShortcutClass

# The genuine evidence must sum to this, from a fresh session, for the owner to
# count as recognised: 20 dB is odds of 100 to 1 on top of the prior.
RECOGNISED_DB = -20.0
# A usage gets its own templates once it holds this much of my activity;
# below, its segments are judged by the global ones.
CONTEXT_MIN_SEGMENTS = 30
CONTEXT_MIN_KEYS = 1500
CONTEXT_MIN_MOTIONS = 3000
DEFAULT_BUDGETS_MIN = (2, 5, 10, 20, 40, 80, 160, 320, 640, 1280)
# Readiness targets: what "ready" means on the curve.
TARGET_DETECTION = 0.9
TARGET_FALSE_ALARMS_PER_HOUR = 0.2


def spread(segments: list[Segment], cap: int) -> list[Segment]:
    """At most `cap` segments, evenly spaced, order kept."""
    if len(segments) <= cap:
        return segments
    step = len(segments) / cap
    return [segments[int(i * step)] for i in range(cap)]


def active_seconds(segments: list[Segment]) -> float:
    return sum(max(s.duration_us, 0) for s in segments) / 1e6


@dataclass
class Population:
    """Pooled templates of other people (guest sessions): the impostor
    reference that replaces the wide fallback (decision engine 3)."""

    keystroke: KeystrokeTemplate | None = None
    pointer: PointerTemplate | None = None
    habits: HabitTemplate | None = None

    @classmethod
    def fit(cls, segments: list[Segment]) -> "Population | None":
        if not segments:
            return None
        k = KeystrokeTemplate.fit(segments)
        p = PointerTemplate.fit(segments)
        h = HabitTemplate.fit(segments)
        return cls(keystroke=k if (k.hold or k.digraph) else None,
                   pointer=p if p.models else None,
                   habits=None if h.empty else h)


@dataclass
class Enrolled:
    """Everything fitted on the owner's enrolment data."""

    modes: list[KeystrokeTemplate]
    pointer: PointerTemplate | None
    habits: HabitTemplate | None
    context_keystroke: dict[int, list[KeystrokeTemplate]] = field(default_factory=dict)
    context_pointer: dict[int, PointerTemplate] = field(default_factory=dict)

    @classmethod
    def fit(cls, segments: list[Segment], max_segments: int = 600) -> "Enrolled":
        # Days of data hold millions of pointer events, and the fits are pure
        # Python: an evenly spread subset keeps every period represented at a
        # bounded cost.
        segments = spread(segments, max_segments)
        # Units of about a minute of activity keep mode fitting affordable.
        chunk = max(1, len(segments) // 40)
        modes = fit_modes(segments, chunk=chunk) if segments else [KeystrokeTemplate()]
        ptr = PointerTemplate.fit(segments)
        hab = HabitTemplate.fit(segments)
        ck, cp = fit_contexts(segments)
        return cls(modes=modes, pointer=ptr if ptr.models else None,
                   habits=None if hab.empty else hab,
                   context_keystroke=ck, context_pointer=cp)

    def engine(self, population: Population | None = None) -> IdentityEngine:
        pop = population or Population()
        return IdentityEngine(
            genuine=self.modes[0],
            reference=pop.keystroke,
            pointer=self.pointer,
            pointer_reference=pop.pointer if self.pointer else None,
            modes=self.modes if len(self.modes) > 1 else None,
            habits=self.habits,
            habits_reference=pop.habits if self.habits else None,
            context_keystroke=self.context_keystroke,
            context_pointer=self.context_pointer,
        )


def fit_contexts(segments: list[Segment]) -> tuple[dict[int, list[KeystrokeTemplate]],
                                                  dict[int, PointerTemplate]]:
    """Keystroke modes and a pointer template per usage that has enough of my
    data."""
    by_cat: dict[int, list[Segment]] = {}
    for s in segments:
        if s.category is not None:
            by_cat.setdefault(s.category, []).append(s)
    keys: dict[int, list[KeystrokeTemplate]] = {}
    pointers: dict[int, PointerTemplate] = {}
    for cat, segs in by_cat.items():
        if len(segs) < CONTEXT_MIN_SEGMENTS:
            continue
        kinds = [r.event.kind for s in segs for r in s.records]
        if kinds.count(EventKind.KEY_DOWN) >= CONTEXT_MIN_KEYS:
            modes = [k for k in fit_modes(segs, chunk=max(1, len(segs) // 40))
                     if k.hold or k.digraph]
            if modes:
                keys[cat] = modes
        if kinds.count(EventKind.MOTION) >= CONTEXT_MIN_MOTIONS:
            p = PointerTemplate.fit(segs)
            if p.models:
                pointers[cat] = p
    return keys, pointers


@dataclass
class SessionRun:
    seconds: float
    # Active seconds until the event, None if it never happened.
    recognised_after_s: float | None
    first_alarm_after_s: float | None
    alarms: int


def replay(engine: IdentityEngine, session: list[Segment]) -> SessionRun:
    """One fresh session through the engine, timing what matters."""
    t = 0.0
    total = 0.0
    recognised = None
    first_alarm = None
    alarms = 0
    for seg in session:
        d = engine.step(seg)
        t += max(seg.duration_us, 0) / 1e6
        total += d.evidence_db
        if recognised is None and total <= RECOGNISED_DB:
            recognised = t
        if d.alarmed:
            alarms += 1
            if first_alarm is None:
                first_alarm = t
    return SessionRun(seconds=t, recognised_after_s=recognised,
                      first_alarm_after_s=first_alarm, alarms=alarms)


@dataclass
class CurvePoint:
    enrol_minutes: float
    enrol_segments: int
    # Owner, held-out.
    genuine_minutes_tested: float
    recognised_share: float | None
    median_time_to_recognise_s: float | None
    false_alarms_per_hour: float | None
    # Someone else.
    impostor_kind: str               # "guest", "simulated" or "none"
    impostor_sessions: int
    detected_share: float | None
    median_time_to_detect_s: float | None
    # Enrolment criteria at this budget (decision engine 5).
    volume: float = 0.0
    stability: float = 0.0
    coverage: float = 0.0
    ready: bool = False


@dataclass
class LearningCurve:
    points: list[CurvePoint] = field(default_factory=list)
    owner_minutes: float = 0.0
    impostor_kind: str = "none"
    population_reference: bool = False
    note: str = ""

    @property
    def ready_at_minutes(self) -> float | None:
        for p in self.points:
            if p.ready:
                return p.enrol_minutes
        return None

    def as_dict(self) -> dict:
        d = asdict(self)
        d["ready_at_minutes"] = self.ready_at_minutes
        return d


def split_sessions(segments: list[Segment], max_segments: int = 30,
                   gap_us: int = 30 * 60 * 1_000_000) -> list[list[Segment]]:
    """Cut segments into replay sessions: a long idle, a reboot (time going
    back) or a size cap starts a new one, as a fresh login would."""
    out: list[list[Segment]] = []
    cur: list[Segment] = []
    for s in segments:
        gap = s.start_us - cur[-1].end_us if cur else 0
        if cur and (gap > gap_us or gap < 0 or len(cur) >= max_segments):
            out.append(cur)
            cur = []
        cur.append(s)
    if cur:
        out.append(cur)
    return out


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def simulate_impostor(session: list[Segment], seed: int) -> list[Segment]:
    """Someone else, made from my own held-out data: hold, gap and pointer
    timings scaled by per-session factors, pointer directions rotated, and
    shortcut and application habits permuted. Close enough to be a fair
    first test, but not a person: real guest sessions replace it."""
    rng = random.Random(seed)

    def factor() -> float:
        # At least 10 % off, at most about 40 %, either way.
        f = math.exp(rng.choice((-1, 1)) * rng.uniform(0.1, 0.35))
        return f

    f_hold, f_gap, f_ptr = factor(), factor(), factor()
    angle = rng.choice((math.pi / 4, math.pi / 2, math.pi, -math.pi / 2, -math.pi / 4))
    ca, sa = math.cos(angle), math.sin(angle)
    perm_sc = list(range(1, len(ShortcutClass)))
    rng.shuffle(perm_sc)
    out: list[Segment] = []
    for seg in session:
        recs: list[Record] = []
        t_new = float(seg.start_us)
        prev = seg.start_us
        for r in seg.records:
            dt = r.time_us - prev
            prev = r.time_us
            k = r.event.kind
            f = f_hold if k == EventKind.KEY_UP else f_gap if k == EventKind.KEY_DOWN else f_ptr
            t_new += dt * f
            ev = r.event
            if k == EventKind.MOTION:
                ev = replace(ev, dx=int(round(ev.dx * ca - ev.dy * sa)),
                             dy=int(round(ev.dx * sa + ev.dy * ca)))
            elif k == EventKind.KEY_DOWN and ev.shortcut != ShortcutClass.NONE:
                ev = replace(ev, shortcut=ShortcutClass(perm_sc[int(ev.shortcut) - 1]))
            recs.append(Record(int(t_new), r.device, r.virtual, ev))
        new = Segment(start_us=seg.start_us, end_us=recs[-1].time_us if recs else seg.start_us,
                      records=recs)
        out.append(new)
    return out


def learning_curve(
    genuine: list[Segment],
    guest_sessions: list[list[Segment]] | None = None,
    budgets_min: tuple[float, ...] = DEFAULT_BUDGETS_MIN,
    holdout_share: float = 0.25,
    max_holdout_sessions: int = 12,
    days: list[int] | None = None,
    params: CriteriaParams = CriteriaParams(),
) -> LearningCurve:
    """The whole curve. `genuine` is my data in time order; `days`, when
    given, is the calendar day index of each segment (the trace has no
    wall-clock, the daemon's daily files do)."""
    genuine = [s for s in genuine if s.records]
    if len(genuine) < 8:
        return LearningCurve(note="not enough of the owner's activity yet")
    cut = int(len(genuine) * (1 - holdout_share))
    enrol_pool, held = genuine[:cut], genuine[cut:]
    held_sessions = split_sessions(held)[-max_holdout_sessions:]

    guests = [s for s in (guest_sessions or []) if s]
    if guests:
        kind = "guest"
        impostors = guests
    else:
        kind = "simulated"
        impostors = [simulate_impostor(s, seed=i) for i, s in enumerate(held_sessions)]

    pool_seconds = active_seconds(enrol_pool)
    curve = LearningCurve(owner_minutes=active_seconds(genuine) / 60, impostor_kind=kind,
                          population_reference=len(guests) >= 2)

    # Enrolment criteria along the same budgets, from the tracker.
    tracker = EnrolmentTracker(params=params)
    fed = 0

    budgets = [b for b in budgets_min if b * 60 <= pool_seconds]
    if not budgets or budgets[-1] * 60 < pool_seconds * 0.9:
        budgets.append(pool_seconds / 60)
    for b in budgets:
        # The oldest segments up to the budget of active time.
        acc = 0.0
        k = 0
        while k < len(enrol_pool) and acc < b * 60:
            acc += max(enrol_pool[k].duration_us, 0) / 1e6
            k += 1
        enrol = enrol_pool[:k]
        while fed < k:
            tracker.feed(enrol_pool[fed])
            fed += 1
        n_days = len(set(days[:k])) if days else None
        enrolled = Enrolled.fit(enrol)

        g_runs = [replay(enrolled.engine(), s) for s in held_sessions]
        tested = sum(r.seconds for r in g_runs)
        i_runs = []
        for i, s in enumerate(impostors):
            # Leave-one-guest-out: the population reference never contains
            # the person being tested.
            pop = None
            if kind == "guest" and len(guests) >= 2:
                pop = Population.fit([seg for j, g in enumerate(guests) if j != i for seg in g])
            i_runs.append(replay(enrolled.engine(pop), s))

        rec = [r.recognised_after_s for r in g_runs if r.recognised_after_s is not None]
        det = [r.first_alarm_after_s for r in i_runs if r.first_alarm_after_s is not None]
        fa_h = (sum(r.alarms for r in g_runs) / (tested / 3600)) if tested > 0 else None
        detected = len(det) / len(i_runs) if i_runs else None
        conv = tracker.convergence(performance_ok=False, n_days=n_days)
        ready = (detected is not None and detected >= TARGET_DETECTION
                 and fa_h is not None and fa_h <= TARGET_FALSE_ALARMS_PER_HOUR)
        curve.points.append(CurvePoint(
            enrol_minutes=round(acc / 60, 2),
            enrol_segments=k,
            genuine_minutes_tested=round(tested / 60, 2),
            recognised_share=len(rec) / len(g_runs) if g_runs else None,
            median_time_to_recognise_s=_median(rec),
            false_alarms_per_hour=fa_h,
            impostor_kind=kind,
            impostor_sessions=len(i_runs),
            detected_share=detected,
            median_time_to_detect_s=_median(det),
            volume=conv.volume,
            stability=conv.stability,
            coverage=conv.coverage,
            ready=ready,
        ))
    if kind == "simulated":
        curve.note = ("impostors are simulated from the owner's own held-out data; "
                      "record guest sessions for real numbers")
    return curve
