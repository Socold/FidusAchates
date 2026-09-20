"""A first keystroke expert (work packages 4-5, in Python per ADR-0010).

It models two things the recorder gives us content-free:
- hold time per key class (down-to-up of the same key),
- inter-key-down latency per biomechanical digraph class.

Both are latencies, so both are modelled log-normal (design review B7). The
expert compares a segment's observations against a genuine template and against
an impostor reference, and returns evidence in decibans for the whole segment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..evidence import deciban_from_logpdf
from ..segment import Segment
from ..stats import LogNormal
from ..trace import EventKind, KeyClass


def _hold_times(seg: Segment) -> list[tuple[KeyClass, float]]:
    """Match each key-down to the next key-up of the same class."""
    pending: dict[KeyClass, int] = {}
    out: list[tuple[KeyClass, float]] = []
    for r in seg.records:
        if r.event.kind == EventKind.KEY_DOWN:
            pending[r.event.key_class] = r.time_us
        elif r.event.kind == EventKind.KEY_UP:
            kc = r.event.key_class
            if kc in pending:
                out.append((kc, float(r.time_us - pending.pop(kc))))
    return out


def _digraph_latencies(seg: Segment) -> list[tuple[int, float]]:
    """Inter-key-down intervals tagged with the current key's digraph class."""
    out: list[tuple[int, float]] = []
    last_t: int | None = None
    for r in seg.records:
        if r.event.kind != EventKind.KEY_DOWN:
            continue
        if last_t is not None and r.event.digraph:
            out.append((r.event.digraph, float(r.time_us - last_t)))
        last_t = r.time_us
    return out


@dataclass
class KeystrokeTemplate:
    """Fitted per-class distributions for one actor (genuine or reference)."""

    hold: dict[int, LogNormal] = field(default_factory=dict)
    digraph: dict[int, LogNormal] = field(default_factory=dict)

    @classmethod
    def fit(cls, segments: list[Segment], min_obs: int = 4) -> "KeystrokeTemplate":
        holds: dict[int, list[float]] = {}
        digs: dict[int, list[float]] = {}
        for seg in segments:
            for kc, dt in _hold_times(seg):
                holds.setdefault(int(kc), []).append(dt)
            for dc, dt in _digraph_latencies(seg):
                digs.setdefault(dc, []).append(dt)
        hold = {k: LogNormal.fit(v) for k, v in holds.items() if len(v) >= min_obs}
        digraph = {k: LogNormal.fit(v) for k, v in digs.items() if len(v) >= min_obs}
        return cls(hold=hold, digraph=digraph)


@dataclass
class KeystrokeExpert:
    name: str = "keystroke"
    # Per-observation evidence is clamped so one weird keystroke cannot swamp
    # the segment (robustness against outliers and model tails).
    clamp_db: float = 6.0

    def evidence(
        self,
        seg: Segment,
        genuine: KeystrokeTemplate,
        reference: KeystrokeTemplate,
    ) -> tuple[float, int]:
        """Total decibans for the segment, and the observation count (quality)."""
        total = 0.0
        n = 0
        for kc, dt in _hold_times(seg):
            total += self._one(dt, genuine.hold.get(int(kc)), reference.hold.get(int(kc)))
            n += 1
        for dc, dt in _digraph_latencies(seg):
            total += self._one(dt, genuine.digraph.get(dc), reference.digraph.get(dc))
            n += 1
        return total, n

    def _one(self, x: float, g: LogNormal | None, r: LogNormal | None) -> float:
        # Need the genuine model; without an impostor model, fall back to a wide
        # reference so an out-of-distribution value still scores as suspicious.
        if g is None:
            return 0.0
        logp_g = g.logpdf(x)
        logp_r = r.logpdf(x) if r is not None else self._wide_logpdf(x, g)
        e = deciban_from_logpdf(logp_r, logp_g)
        return max(-self.clamp_db, min(self.clamp_db, e))

    @staticmethod
    def _wide_logpdf(x: float, g: LogNormal) -> float:
        # A reference three times as broad as the genuine model, same centre.
        wide = LogNormal(mu=g.mu, sigma=g.sigma * 3.0, n=g.n)
        return wide.logpdf(x)
