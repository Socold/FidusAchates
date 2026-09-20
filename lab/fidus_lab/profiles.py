"""Counting distinct users, and revising the count (decision engine section 6).

The original question the project answers: how many people use this machine? We
do not know the number in advance, and the count must be revisable, first
believing in several profiles then merging them on cross-checking. And a single
person has several regimes (external keyboard, trackpad, late night), so the
model is hierarchical: identity, then modes. The discriminant between a new mode
and a new person is temporal interleaving: modes of one person alternate within
a session; two people occupy disjoint times.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .divergence import template_stability
from .experts import KeystrokeTemplate
from .segment import Segment


@dataclass
class Mode:
    """One behavioural regime, with the sessions it was seen in."""

    template: KeystrokeTemplate
    session_ids: set[int] = field(default_factory=set)


@dataclass
class Profile:
    """A presumed person: one or more modes."""

    profile_id: str
    modes: list[Mode] = field(default_factory=list)

    @property
    def session_ids(self) -> set[int]:
        s: set[int] = set()
        for m in self.modes:
            s |= m.session_ids
        return s


def temporal_interleaving(a: set[int], b: set[int]) -> float:
    """How much two session sets alternate. 1 = fully interleaved (shared
    sessions), 0 = disjoint. Sessions shared by both regimes are the strongest
    sign they belong to one person."""
    if not a or not b:
        return 0.0
    shared = a & b
    return len(shared) / len(a | b)


@dataclass
class RevisionEvent:
    kind: str            # "merge" or "split"
    detail: str


@dataclass
class ProfileSet:
    """The current partition, plus the revision history."""

    profiles: list[Profile] = field(default_factory=list)
    history: list[RevisionEvent] = field(default_factory=list)
    merge_distance: float = 0.15   # JS below this pairs are candidates to merge
    _next_id: int = 0

    def add_regime(self, template: KeystrokeTemplate, session_id: int) -> None:
        """Add one observed regime as a new profile; revision merges later."""
        pid = f"p{self._next_id:03d}"
        self._next_id += 1
        self.profiles.append(Profile(pid, [Mode(template, {session_id})]))

    def _candidates(self) -> list[tuple[int, int, float, float, str]]:
        """Every pair that qualifies for a merge, best first.

        Two ways to qualify, deliberately different in strictness:
        - by distance alone, using AVERAGE linkage over all mode pairs, which
          resists chaining (one close mode somewhere no longer pulls two
          distinct people together);
        - by distance AND temporal interleaving, using the closest mode pair,
          because alternation within sessions is the real evidence that two
          regimes are one person's modes (a person on two keyboards).
        """
        out = []
        for i in range(len(self.profiles)):
            for j in range(i + 1, len(self.profiles)):
                a, b = self.profiles[i], self.profiles[j]
                d_avg = self._avg_distance(a, b)
                d_min = self._min_distance(a, b)
                inter = temporal_interleaving(a.session_ids, b.session_ids)
                if d_avg < self.merge_distance:
                    out.append((i, j, d_avg, inter, "average linkage"))
                elif d_min < self.merge_distance * 2.5 and inter > 0.2:
                    out.append((i, j, d_min, inter, "interleaved modes"))
        # Best (smallest distance) first; interleaved merges are not favoured
        # over plain ones, the distance decides.
        return sorted(out, key=lambda t: t[2])

    @staticmethod
    def _min_distance(a: Profile, b: Profile) -> float:
        return min(
            template_stability(ma.template, mb.template)
            for ma in a.modes for mb in b.modes
        )

    @staticmethod
    def _avg_distance(a: Profile, b: Profile) -> float:
        ds = [
            template_stability(ma.template, mb.template)
            for ma in a.modes for mb in b.modes
        ]
        return sum(ds) / len(ds)

    def revise(self) -> None:
        """Merge qualifying profiles until none qualifies. Each round takes the
        best pair, merges it, and recomputes, so a merge can enable or disable
        later ones."""
        while len(self.profiles) > 1:
            cands = self._candidates()
            if not cands:
                break
            i, j, d, inter, how = cands[0]
            self._merge(i, j, d, inter, how)

    def _merge(self, i: int, j: int, d: float, inter: float, how: str) -> None:
        a, b = self.profiles[i], self.profiles[j]
        reason = (
            f"{b.profile_id} into {a.profile_id} ({how}): distance {d:.3f}"
            f", temporal interleaving {inter:.2f}"
        )
        a.modes.extend(b.modes)
        self.history.append(RevisionEvent("merge", reason))
        self.profiles.pop(j)

    @property
    def count(self) -> int:
        return len(self.profiles)
