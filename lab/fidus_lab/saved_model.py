"""The last model fitted on my activity, kept beyond the traces it came from.

    ~/.local/share/fidusachates/model.json

The model is refitted from the stored days, which are deleted after the
retention period. Without this file, a month away from the machine would
delete every day and the daemon would start learning me from nothing. With
it, the daemon falls back on what it last knew until the fresh data is as
good again.

What it holds is the fitted parameters only: per-class log-normals and
mixtures (mu, sigma, weight, count), category counts of habits, the
time-distance law. No event, no window, no time of day. It is written as
plain JSON through an explicit codec, never pickle, so the file can be read
and loading it never runs code.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

from .experts import HabitTemplate, KeystrokeTemplate, PointerTemplate
from .experts.habits import TimeDistanceLaw
from .learning import Enrolled
from .stats import Categorical, LogNormal, LogNormalMixture

FORMAT = 1
_LEAVES = {c.__name__: c for c in (LogNormal, LogNormalMixture, Categorical, TimeDistanceLaw)}


def _leaf(x) -> dict | None:
    if x is None:
        return None
    return {"t": type(x).__name__} | {f.name: getattr(x, f.name) for f in dataclasses.fields(x)}


def _unleaf(d: dict | None):
    if d is None:
        return None
    cls = _LEAVES[d["t"]]
    return cls(**{f.name: tuple(d[f.name]) if isinstance(d[f.name], list) else d[f.name]
                  for f in dataclasses.fields(cls) if f.name in d})


def _keystroke(t: KeystrokeTemplate) -> dict:
    return {"hold": {str(k): _leaf(v) for k, v in t.hold.items()},
            "digraph": {str(k): _leaf(v) for k, v in t.digraph.items()}}


def _unkeystroke(d: dict) -> KeystrokeTemplate:
    return KeystrokeTemplate(hold={int(k): _unleaf(v) for k, v in d["hold"].items()},
                             digraph={int(k): _unleaf(v) for k, v in d["digraph"].items()})


def _pointer(t: PointerTemplate | None) -> dict | None:
    return None if t is None else {"models": {k: _leaf(v) for k, v in t.models.items()}}


def _unpointer(d: dict | None) -> PointerTemplate | None:
    return None if d is None else PointerTemplate(
        models={k: _unleaf(v) for k, v in d["models"].items()})


def _habits(t: HabitTemplate | None) -> dict | None:
    return None if t is None else {
        "categorical": {k: _leaf(v) for k, v in t.categorical.items()}, "law": _leaf(t.law)}


def _unhabits(d: dict | None) -> HabitTemplate | None:
    return None if d is None else HabitTemplate(
        categorical={k: _unleaf(v) for k, v in d["categorical"].items()}, law=_unleaf(d["law"]))


def encode(enrolled: Enrolled) -> dict:
    return {
        "modes": [_keystroke(m) for m in enrolled.modes],
        "pointer": _pointer(enrolled.pointer),
        "habits": _habits(enrolled.habits),
        "context_keystroke": {str(k): [_keystroke(m) for m in v]
                              for k, v in enrolled.context_keystroke.items()},
        "context_pointer": {str(k): _pointer(v) for k, v in enrolled.context_pointer.items()},
    }


def decode(d: dict) -> Enrolled:
    return Enrolled(
        modes=[_unkeystroke(m) for m in d["modes"]],
        pointer=_unpointer(d["pointer"]),
        habits=_unhabits(d["habits"]),
        context_keystroke={int(k): [_unkeystroke(m) for m in v]
                           for k, v in d["context_keystroke"].items()},
        context_pointer={int(k): _unpointer(v) for k, v in d["context_pointer"].items()},
    )


def save(path: Path, enrolled: Enrolled, status: dict) -> None:
    """Write the model with the status it had when fitted, atomically, 0600."""
    blob = {"format": FORMAT, "status": status, "model": encode(enrolled)}
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, separators=(",", ":"))
    os.replace(tmp, path)


def load(path: Path) -> tuple[Enrolled, dict] | None:
    """The saved model and its status, or None if missing or unreadable."""
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        if blob.get("format") != FORMAT:
            return None
        return decode(blob["model"]), dict(blob["status"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def prefer_saved(fresh: dict | None, saved: dict) -> bool:
    """Whether the saved model should stand in for the fresh fit: no fresh
    data at all, the saved one was ready and the fresh one is not, or the
    fresh one is clearly behind (more than 10 points of progress), as after
    a long absence. Small dips while learning do not count, so the model does
    not flip back and forth."""
    if fresh is None:
        return True
    if saved.get("ready") and not fresh.get("ready"):
        return True
    return fresh.get("progress", 0.0) < saved.get("progress", 0.0) - 0.10
