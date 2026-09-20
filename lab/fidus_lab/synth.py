"""Synthetic keystroke generator, for testing the engine without real corpora.

A "typist" has per-class hold-time and per-digraph-class latency distributions
(log-normal). Two typists with different parameters stand in for a genuine user
and an impostor. This validates the machinery; real-corpus numbers are a
separate, data-gated step.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .trace import Event, EventKind, KeyClass, Record


@dataclass
class Typist:
    hold_mu: float          # log-us mean hold time
    hold_sigma: float
    gap_mu: float           # log-us mean inter-key gap
    gap_sigma: float
    seed: int = 0

    def __post_init__(self) -> None:
        self._r = random.Random(self.seed)

    def _ln(self, mu: float, sigma: float) -> float:
        return math.exp(self._r.gauss(mu, sigma))

    def type_segment(self, n_keys: int, start_us: int = 0) -> list[Record]:
        """Emit n_keys as down/up letter events with realistic timing.

        The digraph class alternates deterministically so templates have
        several classes to fit; hold and gap come from the typist's laws.
        """
        out: list[Record] = []
        t = float(start_us)
        # A few digraph-class codes (see biomech packing); values are opaque
        # here, we only need distinct, repeatable classes.
        digraph_cycle = [5, 3, 4, 11, 5, 4]
        for i in range(n_keys):
            hold = self._ln(self.hold_mu, self.hold_sigma)
            dc = digraph_cycle[i % len(digraph_cycle)] if i > 0 else 0
            out.append(Record(int(t), 0, False,
                              Event(EventKind.KEY_DOWN, KeyClass.LETTER, dc)))
            out.append(Record(int(t + hold), 0, False,
                              Event(EventKind.KEY_UP, KeyClass.LETTER, 0)))
            t += hold + self._ln(self.gap_mu, self.gap_sigma)
        return out


@dataclass
class Mouser:
    """A synthetic pointer user: motion velocity, pause before click and click
    duration drawn from log-normal laws, for testing the pointer expert."""

    vel_mu: float        # log pixels-per-ms
    vel_sigma: float
    pause_mu: float      # log-us pause before a click
    pause_sigma: float
    click_mu: float      # log-us click duration
    click_sigma: float
    seed: int = 0

    def __post_init__(self) -> None:
        self._r = random.Random(self.seed)

    def _ln(self, mu: float, sigma: float) -> float:
        return math.exp(self._r.gauss(mu, sigma))

    def move_and_click(self, n_gestures: int, start_us: int = 0, device: int = 1) -> list[Record]:
        """Each gesture: ~20 motion events at ~8 ms, a pause, a click."""
        out: list[Record] = []
        t = float(start_us)
        for _ in range(n_gestures):
            for _ in range(20):
                dt_ms = 8.0
                dist = self._ln(self.vel_mu, self.vel_sigma) * dt_ms
                dx = int(round(dist * self._r.choice((-1, 1))))
                out.append(Record(int(t), device, False,
                                  Event(EventKind.MOTION, dx=dx, dy=0)))
                t += dt_ms * 1000
            t += self._ln(self.pause_mu, self.pause_sigma)
            out.append(Record(int(t), device, False,
                              Event(EventKind.BUTTON_DOWN, button=0)))
            t += self._ln(self.click_mu, self.click_sigma)
            out.append(Record(int(t), device, False,
                              Event(EventKind.BUTTON_UP, button=0)))
            t += 300_000
        return out


@dataclass
class HostileTypist:
    """A typist built to violate the engine's assumptions, not to fit them.

    Every validation so far used log-normal typists, the very model the engine
    assumes: it 'worked' on data made for it. This generator breaks the
    assumptions on purpose so the engine's behaviour off-model is measured
    rather than hoped for:

    - bimodal hold times (two regimes mixed within a segment),
    - bursty gaps: runs of fast keys then long pauses, not one smooth law,
    - corrections: a share of key-downs are Correction class,
    - heavy tails: occasional very long holds.
    """

    fast_hold_mu: float = 11.2
    slow_hold_mu: float = 11.9
    hold_sigma: float = 0.2
    burst_gap_mu: float = 11.0     # fast run
    pause_gap_mu: float = 13.5     # long pause between runs
    gap_sigma: float = 0.3
    burst_len: int = 6
    correction_rate: float = 0.08
    tail_rate: float = 0.03
    seed: int = 0

    def __post_init__(self) -> None:
        self._r = random.Random(self.seed)

    def _ln(self, mu: float, sigma: float) -> float:
        return math.exp(self._r.gauss(mu, sigma))

    def type_segment(self, n_keys: int, start_us: int = 0) -> list[Record]:
        out: list[Record] = []
        t = float(start_us)
        digraph_cycle = [5, 3, 4, 11, 5, 4]
        for i in range(n_keys):
            mode_mu = self.fast_hold_mu if self._r.random() < 0.5 else self.slow_hold_mu
            hold = self._ln(mode_mu, self.hold_sigma)
            if self._r.random() < self.tail_rate:
                hold *= 4.0  # a heavy-tail outlier
            kc = KeyClass.CORRECTION if self._r.random() < self.correction_rate else KeyClass.LETTER
            dc = digraph_cycle[i % len(digraph_cycle)] if i > 0 else 0
            out.append(Record(int(t), 0, False, Event(EventKind.KEY_DOWN, kc, dc)))
            out.append(Record(int(t + hold), 0, False, Event(EventKind.KEY_UP, kc, 0)))
            in_burst = (i % self.burst_len) != self.burst_len - 1
            gap_mu = self.burst_gap_mu if in_burst else self.pause_gap_mu
            t += hold + self._ln(gap_mu, self.gap_sigma)
        return out


@dataclass
class ModalTypist:
    """One person, two regimes that alternate ACROSS segments (never within):
    an internal laptop keyboard and an external one, say. Each segment is
    entirely in one regime. This is the case modes exist for: a mixture inside
    a signal does not help when every segment is unimodal on its own, but a
    single template fitted over both regimes is wrong for each of them."""

    a: dict
    b: dict
    seed: int = 0

    def segment(self, index: int, n_keys: int = 40, start_us: int = 0) -> list[Record]:
        params = self.a if index % 2 == 0 else self.b
        return Typist(seed=self.seed + index, **params).type_segment(n_keys, start_us=start_us)
