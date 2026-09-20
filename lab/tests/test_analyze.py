from fidus_lab.analyze import analyze_segments
from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.registry import SanctionRegistry
from fidus_lab.segment import segment_trace
from fidus_lab.synth import Typist

GEN = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)


def sessions(params, n, keys=40, seed0=0):
    out = []
    t = 0
    for s in range(n):
        recs = Typist(seed=seed0 + s, **params).type_segment(keys, start_us=t)
        out.extend(segment_trace(recs))
        t = recs[-1].time_us + 10_000_000
    return out


def test_pipeline_runs_and_reports():
    segs = sessions(GEN, 5, seed0=0)
    tpl = KeystrokeTemplate.fit(sessions(GEN, 8, seed0=1000))
    engine = IdentityEngine(genuine=tpl, reference=None)
    report = analyze_segments(segs, engine, SanctionRegistry())
    assert report.n_segments == 5
    text = report.as_text()
    assert "segment(s)" in text and "outcomes:" in text
    # Each segment has an actor label and an outcome.
    for s in report.segments:
        assert s.attribution.label is not None
        assert s.outcome is not None
