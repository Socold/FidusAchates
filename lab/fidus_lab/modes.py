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
    chunk: int = 1,
) -> list[KeystrokeTemplate]:
    """Agglomerate segments whose per-segment templates are close, then fit
    one template per group. Groups too small to fit are folded into the
    nearest large one. Returns at least one template.

    `chunk` groups that many consecutive segments into one unit before
    agglomerating: on days of real data, a unit of a few minutes is still
    within one regime, and the pairwise distances stay affordable."""
    if not segments:
        return [KeystrokeTemplate()]
    units = [segments[i:i + chunk] for i in range(0, len(segments), max(chunk, 1))]
    per_unit = [KeystrokeTemplate.fit(u) for u in units]
    n = len(units)
    # Pairwise distances once; single linkage then only reads the matrix.
    dist = [[0.0] * n for _ in range(n)]
    for a in range(n):
        for b in range(a + 1, n):
            dist[a][b] = dist[b][a] = template_stability(per_unit[a], per_unit[b])

    def linkage(g1: list[int], g2: list[int]) -> float:
        return min(dist[a][b] for a in g1 for b in g2)

    # Greedy single-linkage agglomeration on per-unit templates.
    groups: list[list[int]] = [[i] for i in range(n)]
    merged = True
    while merged and len(groups) > 1:
        merged = False
        best = None
        for gi in range(len(groups)):
            for gj in range(gi + 1, len(groups)):
                d = linkage(groups[gi], groups[gj])
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
        target = min(range(len(big)), key=lambda k: linkage(g, big[k]))
        big[target].extend(g)
    return [KeystrokeTemplate.fit([s for i in g for s in units[i]]) for g in big]
