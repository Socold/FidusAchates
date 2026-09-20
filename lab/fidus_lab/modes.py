"""Modes: one person's regimes as separate templates (decision engine 6.1).

A mixture handles bimodality within a signal. When the bimodality is across
segments (a segment is entirely on one keyboard or the other), every segment
is unimodal and a mixture sees nothing, yet a single template fitted over both
regimes is wrong for each. So enrolment groups segments into regimes and fits
one template per regime; the engine then scores a segment against its
best-matching mode, and an impostor has to be far from all of them.
"""

from __future__ import annotations

from .divergence import template_stability
from .experts import KeystrokeTemplate
from .segment import Segment


def fit_modes(
    segments: list[Segment],
    max_distance: float = 0.15,
    min_segments: int = 2,
) -> list[KeystrokeTemplate]:
    """Agglomerate segments whose per-segment templates are close, then fit
    one template per group. Groups too small to fit are folded into the
    nearest large one. Returns at least one template."""
    if not segments:
        return [KeystrokeTemplate()]
    per_seg = [KeystrokeTemplate.fit([s]) for s in segments]
    # Greedy single-linkage agglomeration on per-segment templates.
    groups: list[list[int]] = [[i] for i in range(len(segments))]
    merged = True
    while merged and len(groups) > 1:
        merged = False
        best = None
        for gi in range(len(groups)):
            for gj in range(gi + 1, len(groups)):
                d = min(
                    template_stability(per_seg[a], per_seg[b])
                    for a in groups[gi] for b in groups[gj]
                )
                if d < max_distance and (best is None or d < best[0]):
                    best = (d, gi, gj)
        if best is not None:
            _, gi, gj = best
            groups[gi].extend(groups.pop(gj))
            merged = True
    # Fold tiny groups into the nearest big one so every mode is fittable.
    big = [g for g in groups if len(g) >= min_segments]
    small = [g for g in groups if len(g) < min_segments]
    if not big:
        big = [sum(groups, [])]
        small = []
    for g in small:
        target = min(
            range(len(big)),
            key=lambda k: min(
                template_stability(per_seg[a], per_seg[b]) for a in g for b in big[k]
            ),
        )
        big[target].extend(g)
    return [KeystrokeTemplate.fit([segments[i] for i in g]) for g in big]
