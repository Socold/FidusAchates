# ADR-0004 - Log-likelihood fusion and Wald sequential decision

- **Status**: accepted; the sequential-decision part (SPRT with forgetting) and the global damping factor are **superseded by [ADR-0007](0007-cusum-and-logistic-fusion.md)**. The choice of additive log-likelihood fusion stands
- **Date**: 2024-11, decision taken 2020-02 and 2020-06

## Context

Three requirements have to be met at once: decide fast (FR-32), cross-check heterogeneous signals (FR-31), and explain the decision (FR-53, FR-56). The state of the art gives an EER of 3 % to 10 % for an isolated decision: a one-off decision is therefore not enough.

## Options

1. **Weighted composite score** (sum of normalised distances, fixed threshold): simple, but the scale has no probabilistic meaning, the weighting is arbitrary, and the explanation is an approximation.
2. **Monolithic classifier** (random forest, neural network on a concatenated vector): best possible raw performance, but explainability only approximate (SHAP, LIME), higher online cost, and adding a signal means full retraining.
3. **Log-likelihood fusion plus Wald SPRT.**

## Decision

Option 3.

Each expert produces a calibrated score, converted into a log-likelihood ratio expressed in decibans. Fusion is a weighted sum. The decision follows a two-threshold SPRT derived from the target error rates, with exponential decay of old evidence.

## Rationale

All three requirements are met by one and the same property:

- **Speed**: under its assumptions, the SPRT minimises the number of observations needed to reach fixed error rates. It is the formal answer to "detect as early as possible".
- **Cross-checking**: the LLR puts all signals on a common scale with a probabilistic meaning, which a sum of normalised distances does not.
- **Explainability**: since the sum is additive, the contribution of each signal is **exact**, not estimated. The explanation is not a surrogate model, it is the formula itself read term by term.

That last property is decisive: it makes explainability a consequence of the choice of engine, and not a bolted-on layer that might lie.

## Consequences

- **Calibration becomes mandatory** (FR-30). Without it the addition is wrong and the explanation misleading. This is the main cost of the decision.
- **The conditional independence assumption is violated** in practice. Two corrections: group correlated signals into a single multivariate expert, and apply an empirically measured damping factor (work package 2).
- Raw performance will probably be below that of a well-trained deep model. That is an accepted trade-off in favour of explainability and online cost. A deep model remains possible later **inside an expert**, provided it produces a calibrated score.
- Adding a signal requires no global retraining: it is one more term in the sum.
