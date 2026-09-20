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

    def _closest_pair(self) -> tuple[int, int, float, float] | None:
        best = None
        for i in range(len(self.profiles)):
            for j in range(i + 1, len(self.profiles)):
                d = self._profile_distance(self.profiles[i], self.profiles[j])
                inter = temporal_interleaving(
                    self.profiles[i].session_ids, self.profiles[j].session_ids
                )
                if best is None or d < best[2]:
                    best = (i, j, d, inter)
        return best

    @staticmethod
    def _profile_distance(a: Profile, b: Profile) -> float:
        # Closest pair of modes across the two profiles.
        return min(
            template_stability(ma.template, mb.template)
            for ma in a.modes for mb in b.modes
        )

    def revise(self) -> None:
        """Merge indistinguishable profiles. Two profiles merge when their
        templates are close (below merge_distance) OR they are close-ish and
        temporally interleaved (same person, two modes)."""
        changed = True
        while changed and len(self.profiles) > 1:
            changed = False
            pair = self._closest_pair()
            if pair is None:
                break
            i, j, d, inter = pair
            interleaved_merge = d < self.merge_distance * 2.5 and inter > 0.2
            if d < self.merge_distance or interleaved_merge:
                self._merge(i, j, d, inter)
                changed = True

    def _merge(self, i: int, j: int, d: float, inter: float) -> None:
        a, b = self.profiles[i], self.profiles[j]
        reason = (
            f"{b.profile_id} into {a.profile_id}: JS distance {d:.3f}"
            f", temporal interleaving {inter:.2f}"
        )
        # If interleaved, they are two modes of one person; otherwise fold modes.
        a.modes.extend(b.modes)
        self.history.append(RevisionEvent("merge", reason))
        self.profiles.pop(j)

    @property
    def count(self) -> int:
        return len(self.profiles)
