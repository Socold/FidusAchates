"""What the live daemon remembers of itself over the retention period.

    ~/.local/share/fidusachates/
        history/YYYY-MM-DD.jsonl    learning snapshots and hourly score summaries
        learning.json               the last learning curve computed

Three kinds of line, each with a wall-clock time "w" (ISO, seconds):

    fit    after a refit: progress, the four criteria, keystrokes, days, guests;
           at most one per FIT_EVERY_S unless the phase or readiness changes
    hour   the scores of one clock hour: windows, mean recognition confidence,
           mean and highest probability of someone else, alarms
    curve  after a learning curve: minutes enrolled, ready point, and the last
           point's false alarms, time to recognise, share caught

Only figures the engine already computed; no event, no window, no category.
This is the detector watching itself learn, so I can see it over a month
instead of over one session: a restart no longer starts the console from zero.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

FIT_EVERY_S = 30 * 60
_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")


def _now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


@dataclass
class HourScores:
    """Running summary of the windows scored within one clock hour."""

    hour: dt.datetime
    windows: int = 0
    conf_sum: float = 0.0
    p_sum: float = 0.0
    p_max: float = 0.0
    alarms: int = 0

    def add(self, confidence: float, p_impostor: float, alarmed: bool) -> None:
        self.windows += 1
        self.conf_sum += confidence
        self.p_sum += p_impostor
        self.p_max = max(self.p_max, p_impostor)
        self.alarms += int(alarmed)

    def as_line(self) -> dict:
        n = max(self.windows, 1)
        return {"k": "hour", "w": self.hour.isoformat(), "n": self.windows,
                "conf": round(self.conf_sum / n, 3), "p": round(self.p_sum / n, 3),
                "p_max": round(self.p_max, 3), "alarms": self.alarms}


@dataclass
class History:
    root: Path
    retention_days: int = 30
    _hour: HourScores | None = None
    _last_fit: dict | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        (self.root / "history").mkdir(parents=True, exist_ok=True, mode=0o700)

    # --- writing --------------------------------------------------------------

    def _append(self, line: dict, at: dt.datetime) -> None:
        path = self.root / "history" / f"{at.date().isoformat()}.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, separators=(",", ":")) + "\n")

    def fit(self, status: dict, at: dt.datetime | None = None) -> dict | None:
        """Record a refit's status; None when it is too soon after the last
        one and nothing that matters changed."""
        at = at or _now()
        line = {"k": "fit", "w": at.isoformat(), "progress": status.get("progress"),
                "phase": status.get("phase"), "ready": status.get("ready"),
                "criteria": status.get("criteria"),
                "keystrokes": status.get("owner_keystrokes"),
                "days": status.get("days"), "guests": status.get("guests")}
        with self._lock:
            last = self._last_fit
            if last is not None:
                elapsed = (at - dt.datetime.fromisoformat(last["w"])).total_seconds()
                same = (last["phase"], last["ready"]) == (line["phase"], line["ready"])
                if same and 0 <= elapsed < FIT_EVERY_S:
                    return None
            self._last_fit = line
            self._append(line, at)
        return line

    def score(self, confidence: float, p_impostor: float, alarmed: bool,
              at: dt.datetime | None = None) -> dict | None:
        """Count one scored window; returns the previous hour's line when
        this window opens a new hour."""
        at = at or _now()
        hour = at.replace(minute=0, second=0)
        closed = None
        with self._lock:
            if self._hour is not None and self._hour.hour != hour:
                closed = self._close_hour()
            if self._hour is None:
                self._hour = HourScores(hour)
            self._hour.add(confidence, p_impostor, alarmed)
        return closed

    def current(self) -> dict | None:
        """The hour in progress, not written yet."""
        with self._lock:
            return self._hour.as_line() if self._hour and self._hour.windows else None

    def flush(self) -> dict | None:
        """Write the hour in progress, at shutdown."""
        with self._lock:
            return self._close_hour()

    def _close_hour(self) -> dict | None:
        h, self._hour = self._hour, None
        if h is None or not h.windows:
            return None
        line = h.as_line()
        self._append(line, h.hour)
        return line

    def curve(self, learning: dict, at: dt.datetime | None = None) -> dict:
        """Keep the curve for the next start, and its headline in the history."""
        at = at or _now()
        tmp = self.root / "learning.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(learning, fh)
        os.replace(tmp, self.root / "learning.json")
        pts = learning.get("points") or []
        last = pts[-1] if pts else {}
        line = {"k": "curve", "w": at.isoformat(),
                "owner_minutes": learning.get("owner_minutes"),
                "ready_at_minutes": learning.get("ready_at_minutes"),
                "false_alarms_per_hour": last.get("false_alarms_per_hour"),
                "time_to_recognise_s": last.get("median_time_to_recognise_s"),
                "detected_share": last.get("detected_share"),
                "impostor_kind": learning.get("impostor_kind")}
        with self._lock:
            self._append(line, at)
        return line

    # --- reading back -----------------------------------------------------------

    def load_learning(self) -> dict | None:
        try:
            d = json.loads((self.root / "learning.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return d if isinstance(d, dict) else None

    def load(self) -> list[dict]:
        """Every line kept, oldest first. Also primes the fit throttle, so a
        restart does not write a snapshot it already has."""
        out: list[dict] = []
        for p in sorted((self.root / "history").iterdir()):
            if not _DAY_RE.match(p.name):
                continue
            for raw in p.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(raw)
                except ValueError:
                    continue  # a torn last line after a crash
                if isinstance(d, dict) and "k" in d and "w" in d:
                    out.append(d)
        out.sort(key=lambda d: d["w"])
        fits = [d for d in out if d["k"] == "fit"]
        with self._lock:
            self._last_fit = fits[-1] if fits else None
        return out

    def prune(self, today: dt.date | None = None) -> list[Path]:
        cutoff = (today or dt.date.today()) - dt.timedelta(days=self.retention_days)
        removed = []
        for p in (self.root / "history").iterdir():
            m = _DAY_RE.match(p.name)
            if m and dt.date.fromisoformat(m.group(1)) < cutoff:
                p.unlink()
                removed.append(p)
        return removed
