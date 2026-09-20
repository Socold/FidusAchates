# Synthetic validation of the decision engine

**What this is.** A validation of the machinery, not a performance claim. Two
synthetic typists (log-normal hold and gap times) stand in for a genuine user
and an impostor; the Identity engine is enrolled on the genuine one and run over
held-out sessions of both. It checks that the parts fit together and behave as
the design predicts. **No real person, no real corpus.**

## Method

- Generator: `fidus_lab.synth.Typist`, seeded, deterministic.
- Genuine: hold ~ logN(11.50, 0.30), gap ~ logN(11.55, 0.33) (log-microseconds).
- Impostor: hold ~ logN(11.66, 0.32), gap ~ logN(11.74, 0.36). Deliberately
  close, so the per-segment task is non-trivial.
- Engine: keystroke expert (per-key-class hold, per-digraph-class latency,
  log-normal), logistic fusion, CUSUM (h = 25 dB), prior -10 dB.
- Enrolment on 8 sessions; evaluation on 40 genuine and 40 impostor sessions,
  8 segments each, ~40 keystrokes per segment. A fresh engine per session.
- Config and seeds are in the bench code; two runs give identical numbers.

## Result (`metrics.json`)

| Metric | Value |
|---|---|
| EER per segment | ~0.9 % |
| ANIA (segments before detection) | ~1.1 |
| ANGA (genuine segments before a false alarm) | none in 320 |
| Median TTD | 1 segment |

The point it illustrates: even a small per-segment error rate gives near-immediate
sequential detection with no false alarms, because the CUSUM accumulates the
evidence of ~40 keystrokes per segment. This is the state-of-the-art insight (a
10 % single-decision EER becomes excellent once decisions are accumulated),
reproduced on data we control.

## Limits

- **Synthetic, and easier than reality.** Real typists overlap far more than two
  clean log-normals, real timing has structure these draws lack (bursts, pauses,
  corrections), and a real impostor is not a fixed distribution. These numbers
  must not be read as expected performance.
- **A segment here is ~40 keystrokes.** ANIA of ~1 segment means "within tens of
  keystrokes", which is favourable and a consequence of the segment size, not a
  claim about wall-clock speed.
- **The impostor reference is another synthetic typist**, not a real population,
  so the likelihood ratios are optimistic.
- **No hardware effects, no modes, no fatigue.** The signal study and the
  same-machine case study (AC-1b) are where honest numbers will come from.

This artifact exists so that when a real trace or a public corpus is dropped in,
the harness that produces the numbers is already tested.
