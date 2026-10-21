"""Application context, content-free (FR-5): which *category* of application
has focus, and when it changed.

The GNOME extension emits an `ActivityTick(category)` on every focus change;
the daemon timestamps it on the same monotonic clock as the recorder and
attaches it to the segment it falls in. A context event knows the category it
came from, so a transition can be scored inside one segment, and its rank in
the session's opening sequence (catalogue C02, C03). Never a window title,
never an executable name: the category is all the extension ever sends.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

# Order matters: a category is stored as its index here.
CATEGORIES = ("browser", "terminal", "development", "office", "communication",
              "media", "other")

# Focus changes within the first few after a session start make up the
# opening sequence; later ones are ordinary transitions.
OPENING_LENGTH = 3


def category_index(name: str) -> int:
    try:
        return CATEGORIES.index(name)
    except ValueError:
        return CATEGORIES.index("other")


@dataclass(frozen=True)
class ContextEvent:
    time_us: int
    category: int
    # The category focused before this one, None at a session start.
    previous: int | None = None
    # Position in the session's opening sequence, None once past it.
    opening_rank: int | None = None


@dataclass
class ContextTracker:
    """Turns raw focus ticks into ContextEvents: fills in the previous category
    and the opening rank. `new_session` is called at login and after a long
    idle, which is what starts an opening sequence."""

    _previous: int | None = None
    _rank: int = 0

    def new_session(self) -> None:
        self._previous = None
        self._rank = 0

    def tick(self, time_us: int, category: str) -> ContextEvent | None:
        cat = category_index(category)
        if cat == self._previous:
            return None  # same category refocused: no transition
        rank = self._rank if self._rank < OPENING_LENGTH else None
        ev = ContextEvent(time_us=time_us, category=cat, previous=self._previous,
                          opening_rank=rank)
        self._previous = cat
        self._rank += 1
        return ev


def write_events(path: Path, events: Iterable[ContextEvent]) -> None:
    """Append events as JSON lines, one small object each."""
    with open(path, "a", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps({"t": e.time_us, "c": e.category, "p": e.previous,
                                 "r": e.opening_rank}, separators=(",", ":")) + "\n")


def read_events(path: Path) -> Iterator[ContextEvent]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                yield ContextEvent(time_us=int(d["t"]), category=int(d["c"]),
                                   previous=d.get("p"), opening_rank=d.get("r"))
            except (ValueError, KeyError, TypeError):
                continue  # a torn last line after a crash


def attach(segments: list, events: list[ContextEvent]) -> None:
    """Give each segment the context events inside its time span. A focus
    change outside any segment (no input around it) is left out here; phantom
    activity (E20) is the attribution channel's business, not identity's.
    Segments need not be in order: a day can hold two boots, whose monotonic
    clocks overlap (an event is then attached by time alone, best effort)."""
    events = sorted(events, key=lambda e: e.time_us)
    times = [e.time_us for e in events]
    for seg in segments:
        i = bisect.bisect_left(times, seg.start_us)
        j = bisect.bisect_right(times, seg.end_us)
        seg.context.extend(events[i:j])
