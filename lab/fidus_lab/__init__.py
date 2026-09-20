"""The offline half of FidusAchates: trace reading, replay, attribution."""

from .corpus import CmuSample, ScaledManhattan, load_cmu
from .engine import Decision, IdentityEngine
from .evidence import Cusum, LogisticFusion, deciban, probability_from_evidence
from .experts import KeystrokeExpert, KeystrokeTemplate
from .metrics import eer, far_frr, run_lengths
from .stats import LogNormal, Welford, median_mad
from .synth import Typist
from .attribution import ActorLabel, Attribution, AttributionParams, attribute
from .policy import Outcome, Sensitivity, decide, stub_sensitivity
from .registry import AgentSession, SanctionRegistry
from .segment import Segment, segment_trace
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
    "KeystrokeExpert", "KeystrokeTemplate",
    "eer", "far_frr", "run_lengths",
    "LogNormal", "Welford", "median_mad",
    "Typist",
]
