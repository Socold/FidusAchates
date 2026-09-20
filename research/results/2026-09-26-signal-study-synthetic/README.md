# Signal study on synthetic typists

**What this is.** A validation of the signal-study machinery (work package 4),
not a statement about which real signals matter. Two synthetic typists provide
genuine and impostor feature tables; the code ranks each candidate feature by
discriminating power and greedy-selects a subset. **No real person, no real
corpus.**

## Method

- Features: `fidus_lab.signals.features`, nine keystroke and timing features.
- Discriminating power: d-prime (standardised mean difference) between genuine
  and impostor values, per feature.
- Selection: `greedy_select`, forward selection on fused separability.
- 80 genuine and 80 impostor segments, ~40 keystrokes each, seeded.

## Result (`metrics.json`)

The timing means (down-down, typing speed, flight, hold) rank highest (d-prime
5 to 8); their spreads rank moderate; the correction rate scores exactly 0,
correctly flagged useless because neither synthetic typist ever corrects.

Greedy selection keeps a **single** feature here. That is the right behaviour on
this data, not a bug: all nine features are derived from the same two log-normal
parameters, so they are almost perfectly correlated, and once the strongest is
in, the rest add nothing. It demonstrates that the selection handles redundancy,
which per-feature ranking alone does not (the parsimony goal, design review B6).

## Limits

- **Synthetic and redundant.** Real signals are partly independent, so real
  selection would keep several, not one. The single-feature result is an
  artefact of the generator, and must not be read as "one signal is enough".
- **The features here are a subset.** Pointer (family B), context (family C) and
  the richer timing signals are not exercised, for lack of pointer-rich and
  multi-application traces.
- **d-prime assumes roughly unimodal features.** A bimodal feature (a user with
  two modes) would need the hierarchical treatment, out of scope here.

The value is that when real traces and corpora arrive, the ranking and selection
that turn the catalogue into a kept-signal list are already tested.
