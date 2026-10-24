"""How far my model moves over days: the measurement behind the frozen anchor.

The live model is refitted from a rolling window of days, so it follows me as
I change, and would follow, just as quietly, someone who used the machine a
little every day without ever raising an alarm (threat M10). Decision engine
5.4 answers with a frozen anchor and a drift alert. Before any threshold can
mean something, I need to know how much I drift on my own: this module only
measures, and alerts on nothing.

    ~/.local/share/fidusachates/models/YYYY-MM-DD.json

One snapshot per day, the first fresh fit of that day, in the same format as
model.json (parameters only), deleted after the retention period. At each
refit the current model is compared with the snapshot of the day before, of a
week before and with the oldest one kept.

Drift is a Jensen-Shannon divergence, base 2, in [0, 1]: 0 is the same model.
Per part:
- keystroke: each current mode against the closest mode of the reference,
  mean JS over the hold and digraph classes they share (as criterion C2);
- pointer: mean JS over the pointer signals both have;
- habits: mean JS over the smoothed category distributions both have.
Overall is the mean of the parts measured.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass
from pathlib import Path

from . import saved_model
from .divergence import gaussian_js, template_stability
from .experts import HabitTemplate, PointerTemplate
from .learning import Enrolled
from .stats import Categorical

_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
# Reference lags, in days, and their names in the history.
LAGS = {"1d": 1, "7d": 7}


def categorical_js(a: Categorical, b: Categorical) -> float:
    """JS divergence between two smoothed categorical distributions."""
    k = max(len(a.counts), len(b.counts))
    if k == 0:
        return 0.0

    def probs(c: Categorical) -> list[float]:
        counts = list(c.counts) + [0] * (k - len(c.counts))
        tot = sum(counts) + c.alpha * k
        return [(x + c.alpha) / tot for x in counts]

    p, q = probs(a), probs(b)
    js = 0.0
    for x, y in zip(p, q, strict=True):
        m = (x + y) / 2
        js += 0.5 * (x * math.log2(x / m) if x else 0.0) + 0.5 * (y * math.log2(y / m) if y else 0.0)
    return max(0.0, min(1.0, js))


def _keystroke(cur: Enrolled, ref: Enrolled) -> float | None:
    if not cur.modes or not ref.modes:
        return None
    return sum(min(template_stability(m, r) for r in ref.modes) for m in cur.modes) / len(cur.modes)


def _pointer(cur: PointerTemplate | None, ref: PointerTemplate | None) -> float | None:
    if cur is None or ref is None:
        return None
    shared = set(cur.models) & set(ref.models)
    if not shared:
        return None
    return sum(gaussian_js(cur.models[k].mu, cur.models[k].sigma,
                           ref.models[k].mu, ref.models[k].sigma) for k in shared) / len(shared)


def _habits(cur: HabitTemplate | None, ref: HabitTemplate | None) -> float | None:
    if cur is None or ref is None:
        return None
    shared = set(cur.categorical) & set(ref.categorical)
    if not shared:
        return None
    return sum(categorical_js(cur.categorical[k], ref.categorical[k]) for k in shared) / len(shared)


def model_drift(cur: Enrolled, ref: Enrolled) -> dict:
    parts = {"keystroke": _keystroke(cur, ref), "pointer": _pointer(cur.pointer, ref.pointer),
             "habits": _habits(cur.habits, ref.habits)}
    measured = [v for v in parts.values() if v is not None]
    out = {k: round(v, 4) for k, v in parts.items() if v is not None}
    out["overall"] = round(sum(measured) / len(measured), 4) if measured else None
    return out


@dataclass
class ModelSnapshots:
    root: Path
    retention_days: int = 30

    def __post_init__(self) -> None:
        (self.root / "models").mkdir(parents=True, exist_ok=True, mode=0o700)

    def _days(self) -> list[str]:
        return sorted(m.group(1) for p in (self.root / "models").iterdir()
                      if (m := _DAY_RE.match(p.name)))

    def save_daily(self, enrolled: Enrolled, status: dict, today: dt.date | None = None) -> bool:
        """Keep the first fresh fit of the day; later ones the same day are not kept."""
        path = self.root / "models" / f"{(today or dt.date.today()).isoformat()}.json"
        if path.exists():
            return False
        saved_model.save(path, enrolled, status)
        return True

    def references(self, today: dt.date | None = None) -> dict[str, tuple[str, Enrolled]]:
        """For each lag, the newest snapshot at least that many days old, and
        the oldest snapshot kept; today's own snapshot is never a reference."""
        today = today or dt.date.today()
        days = [d for d in self._days() if dt.date.fromisoformat(d) < today]
        picks: dict[str, str] = {}
        for name, lag in LAGS.items():
            old = [d for d in days if dt.date.fromisoformat(d) <= today - dt.timedelta(days=lag)]
            if old:
                picks[name] = old[-1]
        if days:
            picks["oldest"] = days[0]
        out: dict[str, tuple[str, Enrolled]] = {}
        loaded: dict[str, Enrolled | None] = {}
        for name, day in picks.items():
            if day not in loaded:
                got = saved_model.load(self.root / "models" / f"{day}.json")
                loaded[day] = got[0] if got else None
            if loaded[day] is not None:
                out[name] = (day, loaded[day])
        return out

    def drift(self, current: Enrolled, today: dt.date | None = None) -> dict:
        """Drift of the current model against each reference, with its day."""
        return {name: model_drift(current, ref) | {"day": day}
                for name, (day, ref) in self.references(today).items()}

    def prune(self, today: dt.date | None = None) -> list[Path]:
        cutoff = (today or dt.date.today()) - dt.timedelta(days=self.retention_days)
        removed = []
        for d in self._days():
            if dt.date.fromisoformat(d) < cutoff:
                p = self.root / "models" / f"{d}.json"
                p.unlink()
                removed.append(p)
        return removed
