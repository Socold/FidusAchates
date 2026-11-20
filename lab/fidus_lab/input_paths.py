"""What can happen to key timing between the finger and the recorder.

`fidus_lab.kloak` models one such path, random delays. This module adds the
others I measure on CMU, all as functions from a repetition's key events
(time in ms, key index, is_down; see `kloak.cmu_events`) to the events an
application, or the recorder, would see:

- `cadence`: a buffer that releases key-downs on a fixed clock, every
  `period_ms`, each held `hold_ms`. The output rhythm no longer depends on the
  typist, except where the typist is slower than the clock: a key cannot be
  released before it is typed, so a slow gap goes through as it is.
- `foreign`: the same buffer, but the gaps and holds are those of another
  person's real repetition (a donor). Everyone using it looks like the donor,
  again except where the typist is slower than the donor.
- `remote`: a remote-desktop hop. The sender batches events into packets on a
  frame clock, each packet crosses the network with a random delay, packets
  arrive in order, and the receiver injects a packet's events back to back.

Every function also returns how many key-downs left exactly when they were
typed (the leak of the two buffers), so that the protocols can report it.

Three more model what a careful operator or a device does to the delivery:

- `spread`: the receiver of a remote hop spaces the events of each packet
  evenly over one frame instead of injecting them back to back.
- `playout`: the sender stamps every event and the receiver replays it a
  fixed delay later, a jitter buffer: the timing arrives intact unless a
  packet is later than the buffer.
- `quantize`: events land on a polling grid, as a USB keyboard or a device
  between the keyboard and the machine reports them.
"""

from __future__ import annotations

import math
import random

from .corpus import CmuSample
from .kloak import cmu_events, cmu_from_events

Events = list[tuple[float, int, bool]]


def _downs_ups(events: Events) -> tuple[dict[int, float], dict[int, float]]:
    return ({i: t for t, i, d in events if d}, {i: t for t, i, d in events if not d})


def _rebuffer(events: Events, gaps: list[float], holds: list[float]) -> tuple[Events, int]:
    """Release down i at max(typed time, release of i-1 + gaps[i-1]), up i
    holds[i] later. Returns the events sorted by time and the count of downs
    released at their typed time (after the first)."""
    down, _ = _downs_ups(events)
    n = len(down)
    rel = [down[0]]
    leaks = 0
    for i in range(1, n):
        planned = rel[-1] + gaps[i - 1]
        if down[i] >= planned:
            leaks += 1
        rel.append(max(down[i], planned))
    out = [(rel[i], i, True) for i in range(n)] + [(rel[i] + holds[i], i, False) for i in range(n)]
    out.sort(key=lambda e: (e[0], not e[2], e[1]))
    return out, leaks


def cadence(events: Events, period_ms: float, hold_ms: float) -> tuple[Events, int]:
    n = len(_downs_ups(events)[0])
    return _rebuffer(events, [period_ms] * (n - 1), [hold_ms] * n)


def foreign(events: Events, donor: Events) -> tuple[Events, int]:
    d_down, d_up = _downs_ups(donor)
    n = len(d_down)
    gaps = [d_down[i + 1] - d_down[i] for i in range(n - 1)]
    holds = [d_up[i] - d_down[i] for i in range(n)]
    return _rebuffer(events, gaps, holds)


def remote(
    events: Events, rng: random.Random, frame_ms: float = 16.0,
    latency_ms: float = 40.0, jitter_ms: float = 10.0, inject_gap_ms: float = 0.05,
) -> tuple[Events, int]:
    """Events leave at the end of the frame they fall in; each packet takes a
    log-normal network delay of mean `latency_ms` and standard deviation
    `jitter_ms`, and arrives no earlier than the packet before it (one ordered
    stream). The second value is the number of packets."""
    if latency_ms > 0 and jitter_ms > 0:
        s2 = math.log(1 + (jitter_ms / latency_ms) ** 2)
        mu, sigma = math.log(latency_ms) - s2 / 2, math.sqrt(s2)
    else:
        mu, sigma = None, 0.0
    packets: dict[int, list[tuple[float, int, bool]]] = {}
    for e in events:
        packets.setdefault(math.floor(e[0] / frame_ms), []).append(e)
    out: Events = []
    last_arrival = -math.inf
    for frame in sorted(packets):
        sent = (frame + 1) * frame_ms
        delay = rng.lognormvariate(mu, sigma) if mu is not None else latency_ms
        arrival = max(sent + delay, last_arrival)
        for j, (_, i, d) in enumerate(packets[frame]):
            out.append((arrival + j * inject_gap_ms, i, d))
        last_arrival = out[-1][0]
    return out, len(packets)


def apply(sample: CmuSample, columns: list[str], fn) -> tuple[CmuSample, int]:
    """Run one path on a CMU repetition and read the columns back."""
    events = cmu_events(sample, columns).events
    out, extra = fn(events)
    return cmu_from_events(sample.subject, out, columns), extra


def lag_ms(before: Events, after: Events) -> list[float]:
    """Per key-down delay added by a path."""
    b, a = _downs_ups(before)[0], _downs_ups(after)[0]
    return [a[i] - b[i] for i in b]


def _sorted(out: Events) -> Events:
    return sorted(out, key=lambda e: (e[0], not e[2], e[1]))


def spread(events: Events, frame_ms: float = 16.0, burst_ms: float = 1.0) -> tuple[Events, int]:
    """Re-space each run of events closer than `burst_ms` evenly over
    `frame_ms`, never earlier than it arrived nor before the previous event.
    The second value is the number of runs spread."""
    ordered = sorted(events, key=lambda e: e[0])
    runs: list[list[tuple[float, int, bool]]] = []
    for e in ordered:
        if runs and e[0] - runs[-1][-1][0] < burst_ms:
            runs[-1].append(e)
        else:
            runs.append([e])
    out: Events = []
    spread_runs = 0
    last = -math.inf
    for run in runs:
        step = frame_ms / len(run)
        spread_runs += len(run) > 1
        for j, (t, i, d) in enumerate(run):
            at = max(run[0][0] + j * step, t, last)
            out.append((at, i, d))
            last = at
    return out, spread_runs


def playout(
    events: Events, rng: random.Random, buffer_ms: float = 250.0, frame_ms: float = 16.0,
    latency_ms: float = 150.0, jitter_ms: float = 40.0, tick_ms: float = 1.0,
) -> tuple[Events, int]:
    """Events cross the same packetised path as `remote`, but each carries
    its send-side time and is replayed `buffer_ms` after it, on the receiver's
    timer tick; a packet arriving later than that is replayed on arrival. The
    second value is the number of late events."""
    arrived, _ = remote(events, rng, frame_ms, latency_ms, jitter_ms, inject_gap_ms=0.0)
    arrival = {(i, d): t for t, i, d in arrived}
    out: Events = []
    late = 0
    last = -math.inf
    for t, i, d in sorted(events, key=lambda e: (e[0], not e[2], e[1])):
        due = t + buffer_ms
        if arrival[(i, d)] > due:
            late += 1
            due = arrival[(i, d)]
        at = max(math.ceil(due / tick_ms) * tick_ms, last)
        out.append((at, i, d))
        last = at
    return out, late


def quantize(events: Events, period_ms: float, phase_ms: float = 0.0,
             jitter_ms: float = 0.0, rng: random.Random | None = None) -> tuple[Events, int]:
    """Each event reported at the first poll at or after it, polls every
    `period_ms` from `phase_ms`, plus an optional Gaussian timestamping
    jitter. The second value is the number of events that moved."""
    out: Events = []
    moved = 0
    for t, i, d in events:
        at = math.ceil((t - phase_ms) / period_ms) * period_ms + phase_ms
        if jitter_ms > 0 and rng is not None:
            at += rng.gauss(0.0, jitter_ms)
        moved += at != t
        out.append((at, i, d))
    return _sorted(out), moved
