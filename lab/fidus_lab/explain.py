"""Explanation of a decision (decision engine section 7).

The explanation is the fusion formula read term by term, not a surrogate model:
because fusion is a weighted sum, each signal's contribution is exact. This
module renders those contributions as a waterfall and as natural-language
sentences for the console and the logs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contribution:
    signal: str
    decibans: float  # signed: positive supports the impostor hypothesis


def waterfall(contributions: dict[str, float]) -> list[Contribution]:
    """Contributions sorted by absolute value, largest first."""
    items = [Contribution(k, v) for k, v in contributions.items()]
    return sorted(items, key=lambda c: abs(c.decibans), reverse=True)


# A short, content-free phrase template per signal family. Reads the sign so the
# same code explains both directions.
_TEMPLATES = {
    "A01_hold": "key hold times",
    "A02_flight": "flight times between keys",
    "A03_dd": "key-to-key rhythm",
    "A05_digraph": "digraph rhythm (motor class)",
    "A08_speed": "typing speed",
    "A10_correction": "correction rate",
    "B01_velocity": "pointer velocity",
    "B09_pause": "pause before click",
    "B10_click": "click duration",
    "B13_wheel": "wheel cadence",
    "E03_dd_cv": "timing regularity",
    "keystroke": "keystroke timing",
    "pointer": "pointer behaviour",
}


def _label(signal: str) -> str:
    for prefix, phrase in _TEMPLATES.items():
        if signal.startswith(prefix):
            return phrase
    return signal


def describe(contribution: Contribution) -> str:
    """One natural-language sentence for a contribution."""
    mag = abs(contribution.decibans)
    who = "against the legitimate user" if contribution.decibans > 0 else "for the legitimate user"
    return f"{_label(contribution.signal)}: {mag:.1f} dB {who}"


@dataclass(frozen=True)
class Explanation:
    channel: str
    total_db: float
    top_against: list[str]
    top_for: list[str]

    def as_text(self) -> str:
        lines = [f"[{self.channel}] cumulative evidence {self.total_db:+.1f} dB"]
        if self.top_against:
            lines.append("  points to a different actor:")
            lines += [f"    - {s}" for s in self.top_against]
        if self.top_for:
            lines.append("  supports the legitimate user:")
            lines += [f"    - {s}" for s in self.top_for]
        return "\n".join(lines)


def explain(
    contributions: dict[str, float],
    channel: str = "Identity",
    top_n: int = 5,
) -> Explanation:
    """Build the explanation: the dominant evidence each way, and the total."""
    ordered = waterfall(contributions)
    against = [describe(c) for c in ordered if c.decibans > 0][:top_n]
    supporting = [describe(c) for c in ordered if c.decibans < 0][:top_n]
    total = sum(contributions.values())
    return Explanation(channel=channel, total_db=total, top_against=against, top_for=supporting)
