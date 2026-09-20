"""Feed the console and the overlay from a trace, in real-ish time.

The demonstration path: replay a trace segment by segment, analyse each segment,
publish it to the console, and drive the red overlay from the Identity
probability. The recorder's live streaming is a later piece; replay is enough to
show the whole chain on screen.
"""

from __future__ import annotations

import time

from .analyze import analyze_segments
from .console import Console
from .engine import IdentityEngine
from .experts import KeystrokeTemplate, PointerTemplate
from .modes import fit_modes
from .overlay import OverlayClient, best_overlay
from .profiles import ProfileSet
from .registry import SanctionRegistry
from .segment import Segment, segment_trace
from .trace import read_trace


def drive(
    segments: list[Segment],
    console: Console,
    genuine: KeystrokeTemplate,
    reference: KeystrokeTemplate | None = None,
    registry: SanctionRegistry | None = None,
    overlay: OverlayClient | None = None,
    delay_s: float = 0.0,
    pointer: PointerTemplate | None = None,
    modes: list[KeystrokeTemplate] | None = None,
) -> None:
    """Analyse each segment, publish to the console, drive the overlay."""
    overlay = overlay or best_overlay()
    engine = IdentityEngine(genuine=genuine, reference=reference, pointer=pointer,
                            modes=modes)
    report = analyze_segments(segments, engine, registry or SanctionRegistry())
    profiles = ProfileSet()
    for i, seg_report in enumerate(report.segments):
        console.state.publish(seg_report)
        pct = int(round(seg_report.identity_p_impostor * 100))
        if pct > 50:
            overlay.set_confidence(pct, "Identity")
        else:
            overlay.clear()
        # Profile count from what was actually observed: one regime per
        # segment, revised as they accumulate. Coarse (a segment is a short
        # window) but real, unlike a count that would only ever see the
        # enrolled template.
        seg_tpl = KeystrokeTemplate.fit([seg_report.segment])
        if seg_tpl.hold or seg_tpl.digraph:
            profiles.add_regime(seg_tpl, session_id=i)
            profiles.revise()
        console.state.set_profiles(profiles.count)
        if delay_s:
            time.sleep(delay_s)


def drive_trace(path: str, console: Console, delay_s: float = 0.0) -> None:
    """Temporal split: enrol on the first half, replay the second half."""
    segments = list(segment_trace(read_trace(path)))
    half = len(segments) // 2
    if half >= 2 and len(segments) - half >= 2:
        enrol, test = segments[:half], segments[half:]
    else:
        # Too short to split: self-enrol and replay everything. Identity
        # cannot diverge here; only Attribution is meaningful.
        enrol, test = segments, segments
    modes = fit_modes(enrol) if enrol else [KeystrokeTemplate()]
    ptr = PointerTemplate.fit(enrol) if enrol else PointerTemplate()
    drive(test, console, genuine=modes[0], reference=None, delay_s=delay_s,
          pointer=ptr if ptr.models else None,
          modes=modes if len(modes) > 1 else None)
