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
from typing import BinaryIO, Iterator

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


class ShortcutClass(IntEnum):
    """What a modifier combination does, never which key it was (catalogue
    A16, ADR-0012). Mirrors ``fidus_core::shortcut::ShortcutClass``."""

    NONE = 0
    COPY = 1
    PASTE = 2
    CUT = 3
    UNDO = 4
    REDO = 5
    SELECT_ALL = 6
    SAVE = 7
    FIND = 8
    NEW_TAB = 9
    CLOSE_TAB = 10
    REOPEN_TAB = 11
    RELOAD = 12
    NEW_WINDOW = 13
    OPEN = 14
    QUIT = 15
    PRINT = 16
    NEXT_TAB = 17
    PREV_TAB = 18
    SWITCH_APP = 19
    CLOSE_WINDOW = 20
    WORD_MOVE = 21
    WORD_DELETE = 22
    TERMINAL_COPY = 23
    TERMINAL_PASTE = 24
    LOCK_SCREEN = 25
    DOC_START_END = 26
    OTHER = 27


@dataclass(frozen=True)
class Event:
    kind: EventKind
    # Set for key events.
    key_class: KeyClass | None = None
    digraph: int | None = None
    # Set on key-down: the shortcut class, NONE outside a modifier combination.
    shortcut: ShortcutClass = ShortcutClass.NONE
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
        yield from read_stream(fh)


def read_stream(fh: BinaryIO) -> Iterator[Record]:
    """Yield records from an open binary stream: a file, or the recorder's
    stdout through a pipe (the live path). Blocks while the pipe is quiet."""
    magic = _read_exact(fh, len(MAGIC))
    if magic != MAGIC:
        raise ValueError(f"not a fidus trace: magic {magic!r}")
    while True:
        buf = _read_exact(fh, RECORD_LEN)
        if not buf:
            return
        if len(buf) != RECORD_LEN:
            raise ValueError("truncated final record")
        yield _decode(buf)


def _read_exact(fh: BinaryIO, n: int) -> bytes:
    """Read n bytes, or fewer only at end of stream. A pipe may return short
    reads mid-record; a file never does, so this is the same for both."""
    out = b""
    while len(out) < n:
        chunk = fh.read(n - len(out))
        if not chunk:
            break
        out += chunk
    return out


def encode(r: Record) -> bytes:
    """One record back to its 16 bytes: the lab writes the daily trace files
    it tees from the live stream, and tests build traces with it."""
    e = r.event
    if e.kind == EventKind.KEY_DOWN:
        payload = bytes([int(e.key_class or 0), int(e.digraph or 0), int(e.shortcut), 0])
    elif e.kind == EventKind.KEY_UP:
        payload = bytes([int(e.key_class or 0), 0, 0, 0])
    elif e.kind in (EventKind.MOTION, EventKind.WHEEL):
        payload = struct.pack("<hh", _i16(e.dx), _i16(e.dy))
    else:
        payload = bytes([int(e.button or 0), 0, 0, 0])
    flags = int(e.kind) | (PROV_VIRTUAL if r.virtual else 0)
    return struct.pack("<QHB", r.time_us, r.device, flags) + payload + b"\x00"


def _i16(v: int) -> int:
    """Saturate like the Rust writer, never wrap."""
    return max(-32768, min(32767, v))


def _decode(buf: bytes) -> Record:
    time_us, device, flags = struct.unpack_from("<QHB", buf, 0)
    payload = buf[11:15]
    kind = EventKind(flags & 0x7F)
    virtual = bool(flags & PROV_VIRTUAL)

    if kind in (EventKind.KEY_DOWN, EventKind.KEY_UP):
        down = kind == EventKind.KEY_DOWN
        digraph = payload[1] if down else 0
        # Unknown shortcut values (a newer recorder) read as OTHER, not a crash.
        sc = payload[2] if down else 0
        shortcut = ShortcutClass(sc) if sc in ShortcutClass._value2member_map_ else ShortcutClass.OTHER
        event = Event(kind=kind, key_class=KeyClass(payload[0]), digraph=digraph,
                      shortcut=shortcut)
    elif kind in (EventKind.MOTION, EventKind.WHEEL):
        dx, dy = struct.unpack_from("<hh", payload, 0)
        event = Event(kind=kind, dx=dx, dy=dy)
    else:  # BUTTON_DOWN / BUTTON_UP
        event = Event(kind=kind, button=payload[0])

    return Record(time_us=time_us, device=device, virtual=virtual, event=event)
