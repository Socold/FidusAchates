"""A faithful model of kloak's keystroke obfuscation, to measure it offline.

kloak (github.com/vmonaco/kloak, maintained at github.com/Whonix/kloak) grabs
the input device and re-emits every event after a random delay. The schedule
is three lines of `kloak.c` (`queue_libinput_event_and_relocate_virtual_cursor`
in the Whonix tree, the main loop of `main.c` in the original):

    lower_bound = min(max(prev_release_time - current_time, 0), max_delay);
    random_delay = random_between(lower_bound, max_delay);
    sched_time = current_time + random_delay;  prev_release_time = sched_time

`current_time` is a millisecond clock and `random_between` is uniform over the
integers of the closed interval. The lower bound keeps the output in input
order: an event is never released before the one received just before it.
Every delay lies in [0, max_delay] (100 ms by default), so the lag is bounded.

`obfuscate_times` applies that rule to a sorted list of event times. The CMU
helpers rebuild a repetition's key events from its H/DD columns, run them
through the rule, and read the H/DD/UD columns back, so every CMU protocol of
`public_eval` runs unchanged on obfuscated data.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .corpus import CmuSample, cmu_keys

DEFAULT_MAX_DELAY_MS = 100


def obfuscate_times(
    times_ms: list[float], max_delay_ms: int, rng: random.Random,
    prev_release_ms: int = 0,
) -> tuple[list[int], int]:
    """Release times (integer ms) of events arriving at `times_ms` (sorted),
    and the scheduler state to carry to the next call. A zero delay leaves only
    the millisecond clock's truncation."""
    out: list[int] = []
    prev = prev_release_ms
    for t in times_ms:
        now = math.floor(t)
        lower = min(max(prev - now, 0), max_delay_ms)
        sched = now + (rng.randint(lower, max_delay_ms) if lower < max_delay_ms else lower)
        out.append(sched)
        prev = sched
    return out, prev


@dataclass
class KeyEvents:
    """One repetition as key events: (time in ms, key index, is_down)."""

    events: list[tuple[float, int, bool]]
    n_keys: int


def cmu_events(sample: CmuSample, columns: list[str]) -> KeyEvents:
    """Key-down times from the DD latencies, key-up times from the holds,
    sorted by time (overlaps kept, a down before an up on a tie)."""
    vals = dict(zip(columns, sample.features, strict=True))
    keys = cmu_keys(columns)
    downs = [0.0]
    for a, b in zip(keys, keys[1:], strict=False):
        downs.append(downs[-1] + vals[f"DD.{a}.{b}"])
    ev = []
    for i, name in enumerate(keys):
        ev.append((downs[i] * 1000.0, i, True))
        ev.append(((downs[i] + vals[f"H.{name}"]) * 1000.0, i, False))
    ev.sort(key=lambda e: (e[0], not e[2], e[1]))
    return KeyEvents(ev, len(keys))


def cmu_from_events(
    subject: str, events: list[tuple[float, int, bool]], columns: list[str],
) -> CmuSample:
    """The H/DD/UD columns, in `columns` order, read back from key events."""
    keys = cmu_keys(columns)
    down = {i: t for t, i, d in events if d}
    up = {i: t for t, i, d in events if not d}
    vals: dict[str, float] = {}
    for i, name in enumerate(keys):
        vals[f"H.{name}"] = (up[i] - down[i]) / 1000.0
        if i + 1 < len(keys):
            nxt = keys[i + 1]
            vals[f"DD.{name}.{nxt}"] = (down[i + 1] - down[i]) / 1000.0
            vals[f"UD.{name}.{nxt}"] = (down[i + 1] - up[i]) / 1000.0
    return CmuSample(subject, [vals[c] for c in columns])


def obfuscate_cmu(
    sample: CmuSample, columns: list[str], max_delay_ms: int, rng: random.Random,
) -> CmuSample:
    """The repetition as an application behind kloak would have timed it. The
    repetition starts on a fresh scheduler: CMU leaves seconds between two."""
    ke = cmu_events(sample, columns)
    released, _ = obfuscate_times([t for t, _, _ in ke.events], max_delay_ms, rng)
    out = [(float(r), i, d) for r, (_, i, d) in zip(released, ke.events, strict=True)]
    return cmu_from_events(sample.subject, out, columns)


def obfuscate_corpus(
    samples: list[CmuSample], columns: list[str], max_delay_ms: int, seed: int,
) -> list[CmuSample]:
    """Every repetition through its own draw; deterministic for a seed."""
    rng = random.Random(seed)
    return [obfuscate_cmu(s, columns, max_delay_ms, rng) for s in samples]
