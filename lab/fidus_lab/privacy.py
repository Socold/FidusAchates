"""Keep secrets out of the reduced stream: what I type into a password prompt.

The trace never holds a key code, but it does hold the class of every key
and its timing, and for a password that is its length and shape (letters,
digits, punctuation, in order). Two moments are known to be password entry,
without reading any content:

- the screen is locked: whatever is typed is the unlock password. GNOME says
  when through org.gnome.ScreenSaver ActiveChanged;
- I just ran an elevation or a credentials command (sudo, passwd, ssh-keygen...,
  from the action hook of ADR-0014): what follows up to the next Enter is the
  prompt's answer. If no prompt came (sudo's cached ticket), the next line I
  type is dropped instead, which costs a few keystrokes of data.

Key events in those spans are dropped before anything is written or scored;
pointer events are kept. The hook's line can arrive up to half a second after
the command, so records wait a short delay before release, long enough for
the arming to land first. A browser's password field is not covered: nothing
content-free says a field is one.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import replace

from .trace import DIGRAPH_NONE, EventKind, KeyClass, Record

DELAY_US = 1_500_000
# An armed prompt that never sees an Enter stops dropping after this long.
MAX_ARMED_US = 60_000_000
KEY_KINDS = (EventKind.KEY_DOWN, EventKind.KEY_UP)


class SecretInputFilter:
    def __init__(self, delay_us: int = DELAY_US) -> None:
        self.delay_us = delay_us
        self._buf: deque[Record] = deque()
        self._mutex = threading.Lock()
        self._locks: list[tuple[int, int | None]] = []
        self._arms: list[int] = []
        self._armed_since: int | None = None
        self._enter_down = False
        self._dropped_last = False
        self.dropped = 0

    # --- inputs from other threads ---------------------------------------------

    def lock_changed(self, active: bool, at_us: int) -> None:
        with self._mutex:
            if active:
                if not self._locks or self._locks[-1][1] is not None:
                    self._locks.append((at_us, None))
            elif self._locks and self._locks[-1][1] is None:
                self._locks[-1] = (self._locks[-1][0], at_us)

    def arm(self, at_us: int) -> None:
        with self._mutex:
            self._arms.append(at_us)
            self._arms.sort()

    # --- the stream ---------------------------------------------------------------

    def push(self, r: Record) -> None:
        self._buf.append(r)

    def release(self, now_us: int, flush: bool = False) -> list[Record]:
        """Records old enough to be judged, with the secret ones removed."""
        out: list[Record] = []
        with self._mutex:
            while self._buf and (flush or self._buf[0].time_us <= now_us - self.delay_us):
                r = self._buf.popleft()
                if r.event.kind in KEY_KINDS and self._secret(r):
                    self.dropped += 1
                    self._dropped_last = True
                    continue
                if r.event.kind == EventKind.KEY_DOWN and self._dropped_last:
                    # Its digraph relates it to a key I just dropped.
                    r = replace(r, event=replace(r.event, digraph=DIGRAPH_NONE))
                if r.event.kind == EventKind.KEY_DOWN:
                    self._dropped_last = False
                out.append(r)
            self._prune(now_us)
        return out

    def _secret(self, r: Record) -> bool:
        t = r.time_us
        if any(start <= t and (end is None or t <= end) for start, end in self._locks):
            return True
        while self._arms and self._arms[0] <= t:
            self._armed_since = self._arms.pop(0)
            self._enter_down = False
        if self._armed_since is None:
            return False
        if t - self._armed_since > MAX_ARMED_US:
            self._armed_since = None
            return False
        if r.event.key_class == KeyClass.ENTER:
            if r.event.kind == EventKind.KEY_DOWN:
                self._enter_down = True
            elif self._enter_down:
                self._armed_since = None  # the answer ends with this Enter
        return True

    def _prune(self, now_us: int) -> None:
        horizon = now_us - self.delay_us - MAX_ARMED_US
        self._locks = [(s, e) for s, e in self._locks if e is None or e >= horizon]
