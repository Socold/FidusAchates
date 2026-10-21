"""Action sensitivity (FR-47, work package 9): what is being done, as classes.

The policy needs to know whether a segment did something that matters before
it lifts a doubt on unsanctioned automation (ADR-0011). The source is a small
hook in my interactive shell (contrib/shell/fidus-actions.bash, ADR-0014):
for each command line it appends one line per command, the wall-clock time
and a **class**, to a file in my runtime directory. The classification happens
inside the shell; the command name, its arguments and its paths never leave
it (catalogue C09). Elevation requests (C10) are one of the classes.

Classes, and the sensitivity they give a segment:

- HIGH: `elevation` (sudo, pkexec, run0, su), `destructive` (recursive rm,
  shred, mkfs, dd to a target, forced push, hard reset...), `credentials`
  (ssh-keygen, gpg, passwd, secret stores, cloud CLI logins);
- MEDIUM: `network`, `package`, `containers`;
- LOW: `vcs`, `files`, `read`, `other`.

The file is mine (0600 in a 0700 directory), but any process running as me
can append to it. A forged line can only raise a segment's sensitivity, which
turns a tag on unsanctioned automation into an alert: it can cause a false
alert, never hide one. A takeover that runs commands outside my interactive
shell is not seen here; the Attribution and Identity channels still are.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .policy import Sensitivity
from .segment import Segment

ACTION_CLASSES = ("read", "files", "vcs", "network", "package", "containers",
                  "elevation", "destructive", "credentials", "other")
HIGH = frozenset({"elevation", "destructive", "credentials"})
MEDIUM = frozenset({"network", "package", "containers"})

# The Enter that runs a command is the last key of its segment, and the
# segment only closes after an idle gap; an action this long after the last
# event still belongs to it.
SLACK_US = 2_000_000
KEEP_US = 3600 * 1_000_000
# A line longer than this is not one the hook wrote.
MAX_LINE = 64
# Truncated at start when larger: nothing old is ever needed.
MAX_FILE = 1 << 20


def sensitivity_of(actions: list[str]) -> Sensitivity:
    if any(a in HIGH for a in actions):
        return Sensitivity.HIGH
    if any(a in MEDIUM for a in actions):
        return Sensitivity.MEDIUM
    return Sensitivity.LOW


@dataclass(frozen=True)
class ActionEvent:
    time_us: int  # CLOCK_MONOTONIC, the recorder's clock
    action: str


def parse_line(line: str, now_real: float, now_mono_us: int) -> ActionEvent | None:
    """`<EPOCHREALTIME> <class>` to an event on the monotonic clock, or None
    for anything the hook would not have written."""
    if len(line) > MAX_LINE:
        return None
    parts = line.split()
    if len(parts) != 2 or parts[1] not in ACTION_CLASSES:
        return None
    try:
        t_real = float(parts[0].replace(",", "."))  # EPOCHREALTIME follows the locale
    except ValueError:
        return None
    age_us = int((now_real - t_real) * 1e6)
    if age_us < -SLACK_US or age_us > KEEP_US:
        return None
    return ActionEvent(now_mono_us - age_us, parts[1])


class ActionLog:
    """Recent actions, and the sensitivity of a segment from those inside it."""

    def __init__(self) -> None:
        self._events: deque[ActionEvent] = deque()
        self._lock = threading.Lock()

    def add(self, ev: ActionEvent) -> None:
        with self._lock:
            self._events.append(ev)
            while self._events and self._events[0].time_us < ev.time_us - KEEP_US:
                self._events.popleft()

    def actions_in(self, seg: Segment) -> list[str]:
        with self._lock:
            return [e.action for e in self._events
                    if seg.start_us <= e.time_us <= seg.end_us + SLACK_US]

    def sensitivity(self, seg: Segment) -> tuple[Sensitivity, list[str]]:
        actions = self.actions_in(seg)
        return sensitivity_of(actions), sorted(set(actions))


def actions_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / "fidusachates" / "actions"


def follow(path: Path, log: ActionLog, stop: threading.Event,
           mono_us, poll_s: float = 0.5) -> None:
    """Tail the hook's file into `log` until `stop`. Starts at the end: an
    action from before the daemon started has no segment to belong to."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        if path.stat().st_size > MAX_FILE:
            path.write_bytes(b"")
    except FileNotFoundError:
        pass
    offset = path.stat().st_size if path.exists() else 0
    pending = b""
    while not stop.wait(poll_s):
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            offset, pending = 0, b""
            continue
        if size < offset:
            offset, pending = 0, b""  # truncated or replaced
        if size == offset:
            continue
        with open(path, "rb") as fh:
            fh.seek(offset)
            data = fh.read(size - offset)
        offset = size
        lines = (pending + data).split(b"\n")
        pending = lines.pop()[:MAX_LINE + 1]
        now_real, now_mono = time.time(), mono_us()
        for raw in lines:
            ev = parse_line(raw.decode("ascii", "replace"), now_real, now_mono)
            if ev is not None:
                log.add(ev)
