"""Public-corpus ingestion for within-corpus experiments (protocol, tier 1).

The CMU Keystroke Dynamics benchmark (Killourhy and Maxion) is fixed-text: every
row is the same password typed once, with per-key hold times (H.*) and per-pair
latencies (DD.*, UD.*) in seconds. That is a different shape from our free-text,
class-based model, so we do not force it through the keystroke expert. We ingest
it in its native per-key form and score it with the canonical scaled-Manhattan
detector, whose published EER (~0.096) is the yardstick that validates our
metrics harness. Separately, a row can be rebuilt as the key records the
recorder would have written for it, to run the keystroke expert itself and to
compare digraph classes with true digraphs (roadmap 4.2).

The Balabit Mouse Dynamics Challenge sessions are ingested into pointer
records, so the pointer expert runs on them unchanged.

No corpus is redistributed; the loaders read files the user provides.
Everything here is tested on synthetic rows in the corpus shapes.
"""

from __future__ import annotations

import csv
import os
import statistics
from dataclasses import dataclass

from .trace import DIGRAPH_NONE, Event, EventKind, KeyClass, Record, has_digraph


@dataclass
class CmuSample:
    subject: str
    features: list[float]  # H/DD/UD values, in the header's column order


def load_cmu(path: str) -> list[CmuSample]:
    """Parse a CMU-format CSV into per-row samples."""
    out: list[CmuSample] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        feature_cols = [
            c for c in (reader.fieldnames or [])
            if c.startswith(("H.", "DD.", "UD."))
        ]
        if not feature_cols:
            raise ValueError("no H./DD./UD. feature columns found")
        for row in reader:
            feats = [float(row[c]) for c in feature_cols]
            out.append(CmuSample(subject=row["subject"], features=feats))
    return out


@dataclass
class ScaledManhattan:
    """The canonical CMU baseline: distance to a per-feature mean, scaled by the
    feature's mean absolute deviation. Higher distance = more impostor-like."""

    mean: list[float]
    mad: list[float]

    @classmethod
    def train(cls, samples: list[CmuSample]) -> "ScaledManhattan":
        cols = list(zip(*[s.features for s in samples], strict=True))
        mean = [statistics.fmean(c) for c in cols]
        mad = [
            max(statistics.fmean([abs(v - m) for v in c]), 1e-9)
            for c, m in zip(cols, mean, strict=True)
        ]
        return cls(mean=mean, mad=mad)

    def score(self, sample: CmuSample) -> float:
        return sum(
            abs(x - m) / a
            for x, m, a in zip(sample.features, self.mean, self.mad, strict=True)
        )


# --- CMU in the engine's own representation ---------------------------------
#
# The password is ".tie5Roanl" then Return, typed on a US keyboard, so keys are
# placed on the QWERTY grid exactly as `fidus_core::biomech` places the evdev
# codes (codes are positional, and QWERTY is the identity layout).

# Rows of the main block: (row, column of the first key, keys).
_QWERTY_ROWS = (
    (0, 0, "`1234567890-="),
    (1, 1, "qwertyuiop[]"),
    (2, 1, "asdfghjkl;'"),
    (3, 1, "zxcvbnm,./"),
)
_QWERTY_EXTRA = {"\\": (2, 12)}

# CMU key names to the character on the key. "Shift.r" is the R key typed with
# Shift; the reducer skips modifiers when it forms digraphs, so the pair is
# five -> r, as it would be live. Return is outside the main block.
_CMU_KEYS = {"period": ".", "five": "5", "Shift.r": "r", "Return": None}


def qwerty_position(ch: str) -> tuple[str, int, int] | None:
    """(hand, finger, row) of a character's key on a QWERTY board, following
    `fidus_core::biomech::position`. None outside the main block."""
    cell = _QWERTY_EXTRA.get(ch)
    if cell is None:
        for row, first, keys in _QWERTY_ROWS:
            if ch in keys:
                cell = (row, first + keys.index(ch))
                break
    if cell is None:
        return None
    row, col = cell
    if col <= 1:
        hand, finger = "L", 0
    elif col == 2:
        hand, finger = "L", 1
    elif col == 3:
        hand, finger = "L", 2
    elif col <= 5:
        hand, finger = "L", 3
    elif col <= 7:
        hand, finger = "R", 3
    elif col == 8:
        hand, finger = "R", 2
    elif col == 9:
        hand, finger = "R", 1
    else:
        hand, finger = "R", 0
    return hand, finger, row


def digraph_class(previous: str | None, current: str | None) -> int:
    """Packed digraph class of a character pair, as the recorder writes it
    (relation in bits 0-2, row distance in bits 3-4). DIGRAPH_NONE when either
    key is outside the main block."""
    if previous is None or current is None:
        return DIGRAPH_NONE
    p, c = qwerty_position(previous), qwerty_position(current)
    if p is None or c is None:
        return DIGRAPH_NONE
    row_move = min(abs(p[2] - c[2]), 2)
    if previous == current:
        relation = 1
    elif p[0] != c[0]:
        relation = 5
    else:
        relation = {0: 2, 1: 3}.get(abs(p[1] - c[1]), 4)
    return relation | (row_move << 3)


def cmu_columns(path: str) -> list[str]:
    """The feature columns of a CMU-format CSV, in file order (the order of
    `CmuSample.features`)."""
    with open(path, newline="") as fh:
        header = next(csv.reader(fh))
    return [c for c in header if c.startswith(("H.", "DD.", "UD."))]


def cmu_keys(columns: list[str]) -> list[str]:
    """The typed key names, in order, from the hold-time columns."""
    return [c[2:] for c in columns if c.startswith("H.")]


def _cmu_char(name: str) -> str | None:
    return _CMU_KEYS[name] if name in _CMU_KEYS else name.lower()


def _cmu_key_class(name: str) -> KeyClass:
    ch = _cmu_char(name)
    if ch is None:
        return KeyClass.ENTER
    if ch.isalpha():
        return KeyClass.LETTER
    if ch.isdigit():
        return KeyClass.DIGIT
    return KeyClass.PUNCTUATION


def cmu_digraph_classes(columns: list[str]) -> list[int]:
    """Digraph class of each successive key pair of the password."""
    chars = [_cmu_char(k) for k in cmu_keys(columns)]
    return [digraph_class(a, b) for a, b in zip(chars, chars[1:], strict=False)]


def cmu_records(
    sample: CmuSample, columns: list[str], pair_digraphs: bool = False,
    start_us: int = 0,
) -> list[Record]:
    """One CMU repetition as recorder records: key-down times from the DD
    latencies, key-up times from the holds, sorted (overlaps are kept).

    With `pair_digraphs`, each key pair the recorder can class gets its own
    opaque tag instead of its class: the "true digraph" counterfactual. The
    same pairs are tagged in both modes, so only the pooling differs.
    """
    vals = dict(zip(columns, sample.features, strict=True))
    keys = cmu_keys(columns)
    classes = cmu_digraph_classes(columns)
    downs = [0.0]
    for a, b in zip(keys, keys[1:], strict=False):
        downs.append(downs[-1] + vals[f"DD.{a}.{b}"])
    out: list[Record] = []
    for i, name in enumerate(keys):
        dg = DIGRAPH_NONE
        if i > 0 and has_digraph(classes[i - 1]):
            # Pair tags keep the relation bits non-zero so has_digraph accepts them.
            dg = ((i << 3) | 5) if pair_digraphs else classes[i - 1]
        kc = _cmu_key_class(name)
        t_down = start_us + round(downs[i] * 1e6)
        t_up = t_down + round(vals[f"H.{name}"] * 1e6)
        out.append(Record(t_down, 0, False, Event(EventKind.KEY_DOWN, key_class=kc, digraph=dg)))
        out.append(Record(t_up, 0, False, Event(EventKind.KEY_UP, key_class=kc)))
    out.sort(key=lambda r: r.time_us)
    return out


def _classed_pairs(columns: list[str]) -> list[tuple[str, str, int]]:
    keys = cmu_keys(columns)
    pairs = zip(keys, keys[1:], strict=False)
    return [(a, b, dc) for (a, b), dc in zip(pairs, cmu_digraph_classes(columns), strict=True)
            if has_digraph(dc)]


def cmu_class_features(sample: CmuSample, columns: list[str]) -> list[float]:
    """The row reduced to what the class model keeps: mean hold per key class
    and mean down-down latency per digraph class (UD and unclassed pairs
    dropped), in a fixed order so rows stay comparable."""
    vals = dict(zip(columns, sample.features, strict=True))
    holds: dict[int, list[float]] = {}
    for k in cmu_keys(columns):
        holds.setdefault(int(_cmu_key_class(k)), []).append(vals[f"H.{k}"])
    dds: dict[int, list[float]] = {}
    for a, b, dc in _classed_pairs(columns):
        dds.setdefault(dc, []).append(vals[f"DD.{a}.{b}"])
    return ([statistics.fmean(holds[k]) for k in sorted(holds)]
            + [statistics.fmean(dds[k]) for k in sorted(dds)])


def cmu_pair_features(sample: CmuSample, columns: list[str]) -> list[float]:
    """The same information without the pooling: every hold, and the
    down-down latency of every pair the class model keeps."""
    vals = dict(zip(columns, sample.features, strict=True))
    out = [vals[f"H.{k}"] for k in cmu_keys(columns)]
    out += [vals[f"DD.{a}.{b}"] for a, b, _ in _classed_pairs(columns)]
    return out


# --- Balabit Mouse Dynamics Challenge ---------------------------------------
#
# Session CSVs of RDP mouse events: record timestamp, client timestamp (s),
# button, state, absolute x, y. The recorder only ever sees relative motion, so
# positions become deltas between successive events and the absolute position
# is dropped, as it would be live. Mapping:
#   Move, Drag            -> MOTION (dx, dy from the previous position)
#   Pressed / Released    -> BUTTON_DOWN / BUTTON_UP (Left 0, Right 1, Middle 2)
#   Scroll Down / Up      -> WHEEL, one notch each (dy -1 / +1)
# Timing is the client timestamp, kept non-decreasing. RDP coalesces motion
# (events every ~16 to 110 ms, often several with the same timestamp), so this
# is coarser than a local evdev stream, and the deltas are screen pixels, not
# device counts.

_BALABIT_BUTTONS = {"Left": 0, "Right": 1, "Middle": 2}


def load_balabit_session(path: str, split_axes: bool = False, device: int = 1) -> list[Record]:
    """Records of one Balabit session file.

    `split_axes` mimics the live recorder, which writes REL_X and REL_Y as two
    motion records with the same timestamp (and none for a zero axis); the
    default writes one record per event with both deltas.
    """
    out: list[Record] = []
    last_xy: tuple[int, int] | None = None
    last_t = 0
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            if len(row) < 6:
                continue
            _, client_t, button, state, xs, ys = row[:6]
            t = max(last_t, round(float(client_t) * 1e6))
            last_t = t
            x, y = int(float(xs)), int(float(ys))
            if state in ("Move", "Drag"):
                if last_xy is not None:
                    dx, dy = x - last_xy[0], y - last_xy[1]
                    if split_axes:
                        if dx:
                            out.append(Record(t, device, False, Event(EventKind.MOTION, dx=dx)))
                        if dy:
                            out.append(Record(t, device, False, Event(EventKind.MOTION, dy=dy)))
                    elif dx or dy:
                        out.append(Record(t, device, False,
                                          Event(EventKind.MOTION, dx=dx, dy=dy)))
            elif state in ("Pressed", "Released"):
                kind = EventKind.BUTTON_DOWN if state == "Pressed" else EventKind.BUTTON_UP
                out.append(Record(t, device, False,
                                  Event(kind, button=_BALABIT_BUTTONS.get(button, 3))))
            elif button == "Scroll" and state in ("Down", "Up"):
                out.append(Record(t, device, False,
                                  Event(EventKind.WHEEL, dy=-1 if state == "Down" else 1)))
            last_xy = (x, y)
    return out


def load_balabit_labels(path: str) -> dict[str, bool]:
    """public_labels.csv: session file name -> True if the session is illegal
    (an impostor)."""
    with open(path, newline="") as fh:
        return {row["filename"]: row["is_illegal"].strip() == "1"
                for row in csv.DictReader(fh)}


def balabit_sessions(root: str, split: str) -> dict[str, list[str]]:
    """{user: [session paths]} under `root/<split>_files/`, sorted."""
    base = os.path.join(root, f"{split}_files")
    out: dict[str, list[str]] = {}
    for user in sorted(os.listdir(base)):
        d = os.path.join(base, user)
        if os.path.isdir(d):
            out[user] = sorted(os.path.join(d, f) for f in os.listdir(d))
    return out
