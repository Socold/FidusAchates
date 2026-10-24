"""Where the live daemon keeps what it records, and for how long.

    ~/.local/share/fidusachates/
        traces/YYYY-MM-DD.fidustr     my activity, one reduced trace per day
        context/YYYY-MM-DD.jsonl      focus categories, same days
        guests/<id>.fidustr|.jsonl    someone else's labelled session
        guests/<id>.json              its label and day

Reduced traces only (classes, deltas, monotonic times), never a key code. The
file name carries the day, which the trace itself never does; that is what
lets the enrolment criteria count real days. Everything older than the
retention period is deleted, guest sessions included: they are another
person's behavioural data and are kept no longer than mine.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .context import ContextEvent, attach, read_events, write_events
from .segment import Segment, segment_trace
from .trace import MAGIC, Record, encode, read_trace

RETENTION_DAYS = 30
_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.(fidustr|jsonl)$")


def default_root() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "fidusachates"


class AppendTrace:
    """An append-only trace file: the magic once, then records."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not path.exists() or path.stat().st_size == 0
        self._fh = open(path, "ab")
        os.chmod(path, 0o600)
        if fresh:
            self._fh.write(MAGIC)

    def write(self, r: Record) -> None:
        self._fh.write(encode(r))

    def flush(self) -> None:
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


@dataclass
class Store:
    root: Path
    retention_days: int = RETENTION_DAYS

    def __post_init__(self) -> None:
        # Mine only, the root included: it holds the model and the flagged
        # windows next to the per-day folders.
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        for d in ("traces", "context", "guests"):
            (self.root / d).mkdir(parents=True, exist_ok=True, mode=0o700)
        self._day: str | None = None
        self._trace: AppendTrace | None = None

    # --- writing my activity -------------------------------------------------

    def write(self, records: Iterable[Record], today: dt.date | None = None) -> None:
        day = (today or dt.date.today()).isoformat()
        if day != self._day:
            if self._trace:
                self._trace.close()
            self._trace = AppendTrace(self.root / "traces" / f"{day}.fidustr")
            self._day = day
        for r in records:
            self._trace.write(r)

    def flush(self) -> None:
        if self._trace:
            self._trace.flush()

    def write_context(self, events: list[ContextEvent], today: dt.date | None = None) -> None:
        day = (today or dt.date.today()).isoformat()
        write_events(self.root / "context" / f"{day}.jsonl", events)

    def exclude(self, seg: Segment, today: dt.date | None = None) -> None:
        """Keep a flagged window out of every future enrolment."""
        day = (today or dt.date.today()).isoformat()
        fd = os.open(self.root / "excluded.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"d": day, "s": seg.start_us, "e": seg.end_us}) + "\n")

    def _excluded(self) -> dict[str, list[tuple[int, int]]]:
        out: dict[str, list[tuple[int, int]]] = {}
        p = self.root / "excluded.jsonl"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(line)
                    out.setdefault(d["d"], []).append((int(d["s"]), int(d["e"])))
                except (ValueError, KeyError, TypeError):
                    continue
        return out

    # --- guests ---------------------------------------------------------------

    def new_guest(self, label: str, consent: bool, today: dt.date | None = None) -> "GuestSession":
        """Open a guest session. Consent is a precondition, logged with the
        session before anything is collected (privacy 4.3 and 7.1)."""
        if consent is not True:
            raise ValueError("a guest session needs the person's explicit consent first")
        day = (today or dt.date.today()).isoformat()
        n = len(list((self.root / "guests").glob("*.json"))) + 1
        gid = f"{day}-{n:02d}"
        safe = re.sub(r"[^\w .-]", "", label)[:40] or f"guest {n}"
        meta = self.root / "guests" / f"{gid}.json"
        meta.write_text(json.dumps({"id": gid, "label": safe, "day": day, "consent": True,
                                    "consent_at": dt.datetime.now().isoformat(timespec="seconds")}))
        return GuestSession(gid, safe, AppendTrace(self.root / "guests" / f"{gid}.fidustr"),
                            self.root / "guests" / f"{gid}.jsonl")

    def guests(self) -> list[dict]:
        out = []
        for meta in sorted((self.root / "guests").glob("*.json")):
            try:
                d = json.loads(meta.read_text())
            except (OSError, ValueError):
                continue
            trace = meta.with_suffix(".fidustr")
            d["bytes"] = trace.stat().st_size if trace.exists() else 0
            out.append(d)
        return out

    def delete_guest(self, gid: str) -> bool:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}", gid):
            return False
        hit = False
        for ext in (".json", ".fidustr", ".jsonl"):
            p = self.root / "guests" / f"{gid}{ext}"
            if p.exists():
                p.unlink()
                hit = True
        return hit

    def load_guest_sessions(self) -> list[list[Segment]]:
        out = []
        for d in self.guests():
            trace = self.root / "guests" / f"{d['id']}.fidustr"
            ctx = trace.with_suffix(".jsonl")
            segs = _segments_of(trace, ctx)
            if segs:
                out.append(segs)
        return out

    # --- reading my activity back --------------------------------------------

    def days(self) -> list[str]:
        return sorted(m.group(1) for p in (self.root / "traces").iterdir()
                      if (m := _DAY_RE.match(p.name)))

    def load_owner(self, max_segments: int = 4000) -> tuple[list[Segment], list[int]]:
        """My most recent segments, oldest first, and the day index of each,
        newest days first until the cap so a long history stays affordable."""
        days = self.days()
        excluded = self._excluded()
        picked: list[tuple[int, list[Segment]]] = []
        total = 0
        for i in range(len(days) - 1, -1, -1):
            day = days[i]
            segs = _segments_of(self.root / "traces" / f"{day}.fidustr",
                                self.root / "context" / f"{day}.jsonl")
            spans = excluded.get(day, [])
            segs = [s for s in segs
                    if not any(s.start_us <= e and s.end_us >= b for b, e in spans)]
            picked.append((i, segs))
            total += len(segs)
            if total >= max_segments:
                break
        picked.reverse()
        segments: list[Segment] = []
        day_index: list[int] = []
        for i, segs in picked:
            segments += segs
            day_index += [i] * len(segs)
        if len(segments) > max_segments:
            segments, day_index = segments[-max_segments:], day_index[-max_segments:]
        return segments, day_index

    # --- retention ------------------------------------------------------------

    def prune(self, today: dt.date | None = None) -> list[Path]:
        cutoff = (today or dt.date.today()) - dt.timedelta(days=self.retention_days)
        removed = []
        for sub in ("traces", "context"):
            for p in (self.root / sub).iterdir():
                m = _DAY_RE.match(p.name)
                if m and dt.date.fromisoformat(m.group(1)) < cutoff:
                    p.unlink()
                    removed.append(p)
        if self._prune_excluded(cutoff):
            removed.append(self.root / "excluded.jsonl")
        for d in self.guests():
            if dt.date.fromisoformat(d["day"]) < cutoff:
                self.delete_guest(d["id"])
                removed.append(self.root / "guests" / d["id"])
        return removed


    def _prune_excluded(self, cutoff: dt.date) -> bool:
        """Drop flagged windows whose day is past the retention: their
        trace is gone, so they guard nothing."""
        p = self.root / "excluded.jsonl"
        if not p.exists():
            return False
        lines = p.read_text(encoding="utf-8").splitlines()
        keep = []
        for line in lines:
            try:
                if dt.date.fromisoformat(json.loads(line)["d"]) < cutoff:
                    continue
            except (ValueError, KeyError, TypeError):
                continue  # unreadable: nothing it could still guard
            keep.append(line)
        if len(keep) == len(lines):
            return False
        tmp = p.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.writelines(line + "\n" for line in keep)
        os.replace(tmp, p)
        return True


@dataclass
class GuestSession:
    id: str
    label: str
    trace: AppendTrace
    context_path: Path

    def write(self, records: Iterable[Record]) -> None:
        for r in records:
            self.trace.write(r)

    def write_context(self, events: list[ContextEvent]) -> None:
        write_events(self.context_path, events)

    def close(self) -> None:
        self.trace.close()


def monotonic_runs(records: Iterable[Record]) -> Iterator[list[Record]]:
    """Split where time goes backwards: a reboot restarts the monotonic clock,
    and one day's file can hold two boots."""
    run: list[Record] = []
    for r in records:
        if run and r.time_us < run[-1].time_us:
            yield run
            run = []
        run.append(r)
    if run:
        yield run


def _segments_of(trace: Path, context: Path) -> list[Segment]:
    if not trace.exists():
        return []
    try:
        records = list(read_trace(trace))
    except ValueError:
        # A crash can leave a torn final record; keep what precedes it.
        records = _read_prefix(trace)
    segs: list[Segment] = []
    for run in monotonic_runs(records):
        segs += list(segment_trace(run))
    if context.exists():
        attach(segs, list(read_events(context)))
    return segs


def _read_prefix(path: Path) -> list[Record]:
    out = []
    it = read_trace(path)
    while True:
        try:
            out.append(next(it))
        except (StopIteration, ValueError):
            return out
