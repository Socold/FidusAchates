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
from .experts import KeystrokeTemplate
from .overlay import OverlayClient, best_overlay
from .profiles import ProfileSet
from .registry import SanctionRegistry
from .segment import Segment, segment_trace
from .trace import read_trace


def drive(
    segments: list[Segment],
    console: Console,
    genuine: KeystrokeTemplate,
    reference: KeystrokeTemplate,
    registry: SanctionRegistry | None = None,
    overlay: OverlayClient | None = None,
    delay_s: float = 0.0,
) -> None:
    """Analyse each segment, publish to the console, drive the overlay."""
    overlay = overlay or best_overlay()
    engine = IdentityEngine(genuine=genuine, reference=reference)
    report = analyze_segments(segments, engine, registry or SanctionRegistry())
    profiles = ProfileSet()
    for i, seg_report in enumerate(report.segments):
        console.state.publish(seg_report)
        pct = int(round(seg_report.identity_p_impostor * 100))
        if pct > 50:
            overlay.set_confidence(pct, "Identity")
        else:
            overlay.clear()
        # Grow the profile estimate as sessions accumulate (a coarse live view).
        profiles.add_regime(genuine, session_id=i)
        profiles.revise()
        console.state.set_profiles(profiles.count)
        if delay_s:
            time.sleep(delay_s)


def drive_trace(path: str, console: Console, delay_s: float = 0.0) -> None:
    segments = list(segment_trace(read_trace(path)))
    tpl = KeystrokeTemplate.fit(segments) if segments else KeystrokeTemplate()
    drive(segments, console, genuine=tpl, reference=tpl, delay_s=delay_s)
