"""The CMU harness on synthetic rows in the CMU shape.

We do not ship the real corpus. This checks the parser and that the
scaled-Manhattan detector separates a genuine subject from others, so that when
the real CSV is dropped in, the EER number is trustworthy.
"""

import random

from fidus_lab.corpus import CmuSample, ScaledManhattan, load_cmu
from fidus_lab.metrics import eer


def _synthetic_cmu(tmp_path, n_features=6, per_subject=20):
    r = random.Random(0)
    header = ["subject", "sessionIndex", "rep"]
    header += [f"H.k{i}" for i in range(n_features)]
    rows = [",".join(header)]
    # Two subjects with different feature means.
    for subj, base in (("s001", 0.10), ("s002", 0.16)):
        for rep in range(per_subject):
            feats = [f"{r.gauss(base, 0.02):.5f}" for _ in range(n_features)]
            rows.append(",".join([subj, "1", str(rep), *feats]))
    p = tmp_path / "cmu.csv"
    p.write_text("\n".join(rows) + "\n")
    return p


def test_parser_and_separation(tmp_path):
    path = _synthetic_cmu(tmp_path)
    samples = load_cmu(str(path))
    assert len(samples) == 40
    assert len(samples[0].features) == 6

    genuine = [s for s in samples if s.subject == "s001"]
    others = [s for s in samples if s.subject != "s001"]
    model = ScaledManhattan.train(genuine[:15])

    g_scores = [model.score(s) for s in genuine[15:]]
    i_scores = [model.score(s) for s in others]
    # Distinct subjects must be separable by the canonical detector.
    assert eer(g_scores, i_scores) < 0.2
