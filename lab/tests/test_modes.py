"""Modes: one person's regimes as separate templates (decision engine 6.1).

What modes add over per-signal mixtures is JOINT structure. A mixture makes
each signal bimodal on its own, so an impostor who copies regime A's hold
times and regime B's rhythm is plausible signal by signal. No single mode of
the genuine user has that combination, so modes reject it.
"""

import math

from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.modes import fit_modes
from fidus_lab.segment import segment_trace
from fidus_lab.synth import ModalTypist, Typist


def L(ms):
    return math.log(ms * 1000)


# Two regimes, well separated on both measured signals (hold, down-to-down).
A = dict(hold_mu=L(60), hold_sigma=0.15, gap_mu=L(390), gap_sigma=0.15)
B = dict(hold_mu=L(180), hold_sigma=0.15, gap_mu=L(80), gap_sigma=0.15)
# A's holds with B's rhythm: plausible per signal, impossible jointly.
CROSS = dict(hold_mu=L(60), hold_sigma=0.15, gap_mu=L(200), gap_sigma=0.15)


def modal_segs(n, seed):
    m = ModalTypist(A, B, seed=seed)
    return [next(segment_trace(m.segment(i, 40))) for i in range(n)]


def smooth(p, n, seed0):
    return [next(segment_trace(Typist(seed=seed0 + s, **p).type_segment(40))) for s in range(n)]


def test_fit_modes_recovers_both_regimes():
    modes = fit_modes(modal_segs(12, seed=100))
    assert len(modes) == 2
    holds = sorted(m.hold[1].mu for m in modes)
    assert holds[0] < L(100) < holds[1]


def test_modes_keep_a_two_keyboard_user_quiet():
    modes = fit_modes(modal_segs(12, seed=100))
    alarms = 0
    for s in range(20):
        eng = IdentityEngine(genuine=modes[0], modes=modes)
        if any(eng.step(seg).alarmed for seg in modal_segs(8, seed=2000 + s * 10)):
            alarms += 1
    assert alarms == 0


def test_cross_impostor_passes_mixtures_but_not_modes():
    enrol = modal_segs(12, seed=100)
    single = KeystrokeTemplate.fit(enrol)
    modes = fit_modes(enrol)

    def detected(make):
        hits = 0
        for s in range(20):
            eng = make()
            if any(eng.step(seg).alarmed for seg in smooth(CROSS, 10, 7000 + s * 10)):
                hits += 1
        return hits / 20

    # Per-signal mixtures accept the cross: every signal is plausible alone.
    assert detected(lambda: IdentityEngine(genuine=single)) < 0.2
    # Joint modes reject it: no mode has that combination.
    assert detected(lambda: IdentityEngine(genuine=modes[0], modes=modes)) > 0.9


def test_single_regime_user_yields_one_mode():
    segs = smooth(A, 10, seed0=300)
    assert len(fit_modes(segs)) == 1
