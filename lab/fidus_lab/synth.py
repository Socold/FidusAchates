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
