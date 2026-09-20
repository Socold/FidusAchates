"""Reader for the reduced trace format (research/TRACE-FORMAT.md).

The mirror image of ``fidus_core::trace``: same 8-byte magic, same fixed
16-byte little-endian records. It yields classes, deltas and timings, and can
never yield a key code, because the format contains none.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Iterator

MAGIC = b"FIDUSTR\x01"
RECORD_LEN = 16
PROV_VIRTUAL = 0x80


class EventKind(IntEnum):
    KEY_DOWN = 1
    KEY_UP = 2
    MOTION = 3
    WHEEL = 4
    BUTTON_DOWN = 5
    BUTTON_UP = 6


class KeyClass(IntEnum):
    OTHER = 0
    LETTER = 1
    DIGIT = 2
    PUNCTUATION = 3
    SPACE = 4
    ENTER = 5
    TAB = 6
    CORRECTION = 7
    MODIFIER = 8
    NAVIGATION = 9
    FUNCTION = 10
    KEYPAD = 11


@dataclass(frozen=True)
class Event:
    kind: EventKind
    # Set for key events.
    key_class: KeyClass | None = None
    digraph: int | None = None
    # Set for motion and wheel.
    dx: int = 0
    dy: int = 0
    # Set for buttons: 0 left, 1 right, 2 middle, 3 other.
    button: int | None = None


@dataclass(frozen=True)
class Record:
    time_us: int
    device: int
    virtual: bool
    event: Event


def read_trace(path: str | Path) -> Iterator[Record]:
    """Yield the records of a trace file in order.

    Raises ``ValueError`` on a bad magic or a truncated final record.
    """
    with open(path, "rb") as fh:
        magic = fh.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError(f"not a fidus trace: magic {magic!r}")
        while True:
            buf = fh.read(RECORD_LEN)
            if not buf:
                return
            if len(buf) != RECORD_LEN:
                raise ValueError("truncated final record")
            yield _decode(buf)


def _decode(buf: bytes) -> Record:
    time_us, device, flags = struct.unpack_from("<QHB", buf, 0)
    payload = buf[11:15]
    kind = EventKind(flags & 0x7F)
    virtual = bool(flags & PROV_VIRTUAL)

    if kind in (EventKind.KEY_DOWN, EventKind.KEY_UP):
        digraph = payload[1] if kind == EventKind.KEY_DOWN else 0
        event = Event(kind=kind, key_class=KeyClass(payload[0]), digraph=digraph)
    elif kind in (EventKind.MOTION, EventKind.WHEEL):
        dx, dy = struct.unpack_from("<hh", payload, 0)
        event = Event(kind=kind, dx=dx, dy=dy)
    else:  # BUTTON_DOWN / BUTTON_UP
        event = Event(kind=kind, button=payload[0])

    return Record(time_us=time_us, device=device, virtual=virtual, event=event)
