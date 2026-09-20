"""The offline half of FidusAchates: trace reading, replay, attribution."""

from .analyze import AnalysisReport, SegmentReport, analyze_segments, analyze_trace
from .attribution import ActorLabel, Attribution, AttributionParams, attribute
from .console import Console, ConsoleState, start
from .corpus import CmuSample, ScaledManhattan, load_cmu
from .divergence import gaussian_js, template_stability
from .engine import Decision, IdentityEngine
from .enrolment import (
    Convergence,
    CriteriaParams,
    EnrolmentTracker,
    Phase,
    assess,
    rolling_stability,
)
from .evidence import Cusum, LogisticFusion, deciban, probability_from_evidence
from .experts import KeystrokeExpert, KeystrokeTemplate, PointerExpert, PointerTemplate
from .explain import Contribution, Explanation, explain, waterfall
from .live import drive, drive_trace
from .metrics import eer, far_frr, run_lengths
from .overlay import NullOverlay, OverlayClient, best_overlay
from .poisoning import AnchorWatch, admits, bounded_update
from .policy import Outcome, Sensitivity, decide, stub_sensitivity
from .profiles import Mode, Profile, ProfileSet, RevisionEvent, temporal_interleaving
from .registry import AgentSession, SanctionRegistry
from .segment import Segment, segment_trace
from .stats import Distribution, LogNormal, LogNormalMixture, Welford, fit_best, median_mad, wide_reference
from .synth import HostileTypist, Mouser, Typist
from .trace import Event, EventKind, KeyClass, Record, read_trace

__all__ = [
    "ActorLabel",
    "Attribution",
    "AttributionParams",
    "attribute",
    "Outcome",
    "Sensitivity",
    "decide",
    "stub_sensitivity",
    "AgentSession",
    "SanctionRegistry",
    "Segment",
    "segment_trace",
    "Event",
    "EventKind",
    "KeyClass",
    "Record",
    "read_trace",
    "CmuSample", "ScaledManhattan", "load_cmu",
    "Decision", "IdentityEngine",
    "Cusum", "LogisticFusion", "deciban", "probability_from_evidence",
    "KeystrokeExpert", "KeystrokeTemplate", "PointerExpert", "PointerTemplate",
    "eer", "far_frr", "run_lengths",
    "Distribution", "LogNormal", "LogNormalMixture", "Welford", "fit_best", "median_mad", "wide_reference",
    "Typist", "Mouser", "HostileTypist",
    "Contribution", "Explanation", "explain", "waterfall",
    "gaussian_js", "template_stability",
    "Convergence", "CriteriaParams", "EnrolmentTracker", "Phase", "assess", "rolling_stability",
    "AnchorWatch", "admits", "bounded_update",
    "Mode", "Profile", "ProfileSet", "RevisionEvent", "temporal_interleaving",
    "AnalysisReport", "SegmentReport", "analyze_segments", "analyze_trace",
    "NullOverlay", "OverlayClient", "best_overlay",
    "Console", "ConsoleState", "start",
    "drive", "drive_trace",
]
