# ADR-0007 - CUSUM change detection and logistic-regression fusion

- **Status**: accepted
- **Date**: 2026-09
- **Supersedes**: the sequential-decision part of [ADR-0004](0004-fusion-llr-sprt.md)

## Context

ADR-0004 chose additive log-likelihood fusion, which stands, and paired it with Wald's SPRT plus exponential forgetting and a single global damping factor `λ`. The design review (A1, A2, B3) found three faults:

1. The evidence sign was inconsistent between the definition and the thresholds, and the displayed probability silently assumed a prior that was never stated.
2. An SPRT with forgetting is no longer Wald's test. The error-rate guarantees are lost, and the cumulative evidence becomes **bounded**: a weak impostor can never reach the threshold, however long he stays.
3. One scalar cannot correct correlations that differ from one group of signals to another.

## Decision

**Evidence is evidence for the impostor hypothesis.** `e_i = 10·log10[P(x|impostor)/P(x|genuine)]`. Up means suspicious, everywhere.

**The prior is explicit.** `posterior_dB = prior_dB + S`, initial prior -10 dB. The displayed probability is an aid to reading; alarms are driven by run-length thresholds, specified separately.

**Accumulation by CUSUM.** `S_t = max(0, S_{t-1} + E_t)`, alarm at `S_t ≥ h`.

**Fusion by linear logistic regression** over the experts' LLRs: `E = b + Σ w_i·q_i·e_i`, weights learned on development data.

## Rationale

The SPRT answers "which hypothesis has held since the start?". The real question is "has the user changed at an unknown moment?". That is change detection, and CUSUM is its optimal procedure: shortest detection delay for a given false alarm rate.

- The reflecting barrier at zero replaces the half-life. One parameter that is hard to tune disappears, and hours of genuine use cannot be spent as credit by a later impostor.
- The threshold `h` is set from the **average run length to false alarm**, which is the ANGA metric; the detection delay is ANIA. The engine and the evaluation protocol now use the same quantities.
- Logistic-regression fusion is the standard way to combine and calibrate several detectors' LLRs. Redundant experts receive small weights, so correlation is handled where it occurs.

Both choices are **linear in the per-signal evidence**, so the contribution of each signal to `S` remains exact. The explainability argument of ADR-0004 is untouched, which is why that ADR is amended and not withdrawn.

## Consequences

- CUSUM has no "conclude genuine" outcome. The adaptation admission filter, which relied on it, becomes: `S = 0` over several consecutive windows **and** clearly negative window evidence.
- `S` only moves on input. Clearing an alert when an impostor walks away needs events: session lock and idle, both delivered by logind, so the agent still never polls.
- The fusion weights need labelled development data. On public corpora that is available; on my machine the impostor side is thin, which is one more reason the Identity channel is calibrated on corpora first.
- The level table in 03 is computed from the formula, and a unit test recomputes it. It was wrong once because it was written by hand.
