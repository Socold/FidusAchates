"""Public-corpus ingestion for within-corpus experiments (protocol, tier 1).

The CMU Keystroke Dynamics benchmark (Killourhy and Maxion) is fixed-text: every
row is the same password typed once, with per-key hold times (H.*) and per-pair
latencies (DD.*, UD.*) in seconds. That is a different shape from our free-text,
class-based model, so we do not force it through the keystroke expert. We ingest
it in its native per-key form and score it with the canonical scaled-Manhattan
detector, whose published EER (~0.096) is the yardstick that validates our
metrics harness.

The real CSV is not redistributed; `load_cmu` reads a file the user provides.
Everything here is tested on synthetic rows in the CMU shape.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass


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
        cols = list(zip(*[s.features for s in samples]))
        mean = [statistics.fmean(c) for c in cols]
        mad = [
            max(statistics.fmean([abs(v - m) for v in c]), 1e-9)
            for c, m in zip(cols, mean)
        ]
        return cls(mean=mean, mad=mad)

    def score(self, sample: CmuSample) -> float:
        return sum(
            abs(x - m) / a
            for x, m, a in zip(sample.features, self.mean, self.mad)
        )
