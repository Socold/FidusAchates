# 03 - Decision engine, confidence and calibration

> Covers requirements FR-20 to FR-44 of the [requirements](01-REQUIREMENTS.md).

---

## 1. Guiding principle

A single decision is weak. The state of the art gives an EER of the order of 3 % to 10 % for a one-off decision, depending on the modality. The system therefore **never** tries to settle on one observation: it **accumulates evidence** and settles as soon as the accumulated evidence crosses a threshold matching the target error rates.

Three properties are wanted at once, and a single formulation delivers all three:

1. **Speed**: decide with the minimum number of observations, at a fixed error rate.
2. **Cross-checking**: combine heterogeneous signals on a common scale.
3. **Explainability**: know exactly what moved the decision.

The formulation that satisfies all three is the **cumulative log-likelihood ratio**, assessed by a **sequential probability ratio test** (Wald's SPRT). Cross-checking becomes an addition, and the explanation is that addition read term by term.

## 2. Unit of evidence: the deciban

For each signal `i` observed at value `x_i`, the evidence contributed is defined as:

```
e_i = 10 · log10 [ P(x_i | genuine) / P(x_i | impostor) ]      (in decibans)
```

- `e_i > 0`: the observation supports the legitimate user.
- `e_i < 0`: it contradicts them.
- `e_i = 0`: the signal contributes nothing.

The deciban is an additive and readable unit: "this typing burst contributed 12 dB of evidence against the legitimate user" is a sentence with a precise meaning, displayable as is in the console (FR-53).

Total evidence over a window is:

```
E = Σ_i  w_i · q_i · e_i
```

- `w_i`: **reliability** of the signal, learned and bounded. Initialised at `1 - 2·EER_i` then re-estimated.
- `q_i`: **quality** of the current observation (enough observations, acceptable estimator variance). Zero if the evidence is too thin (FR-11).

The displayed probability follows directly from the cumulative evidence:

```
P(impostor) = 1 / (1 + 10^(E_cumulative / 10))
```

## 3. Reference densities

Each signal needs two densities: under the genuine hypothesis and under the impostor hypothesis.

- **Genuine**: estimated during enrolment, with robust statistics (median, median absolute deviation) rather than mean and standard deviation, to withstand outliers. Default model: Gaussian on the robustly standardised value, or a two-component mixture when the distribution is clearly bimodal (a sign of a second **mode**, cf. section 6).
- **Impostor**: three sources, in order of preference:
  1. The other profiles observed on the machine, when there are any.
  2. A reference population drawn from the public corpora (CMU, Balabit, SapiMouse), shipped with the project.
  3. A wide non-informative model, as a last resort.

**Calibration is mandatory.** Raw expert scores are not probabilities. Each expert goes through calibration (Platt logistic regression, or isotonic if the data allows), validated with a reliability diagram (FR-30). Without this step the addition of LLRs is wrong and the explanation misleading.

**Independence assumption: owned and corrected.** Adding LLRs assumes conditional independence of the signals, which does not hold (typing speed and digraph latency are correlated). Two corrections:

- Grouping strongly correlated signals into a single expert that produces one multivariate LLR.
- Applying a damping factor `0 < λ ≤ 1` to the sum, estimated empirically so that observed error rates match nominal ones. This is exactly the correction used in naive Bayes fusion, and it has to be measured, not guessed.

## 4. Sequential decision

### 4.1 Wald thresholds

For targets `α` (false alarm) and `β` (missed detection):

```
upper threshold  A = 10 · log10 ( (1-β) / α )       → conclude "impostor"
lower threshold  B = 10 · log10 ( β / (1-α) )       → conclude "genuine"
in between                                           → keep observing
```

With `α = 0.01` and `β = 0.05`, this gives `A ≈ 19.8 dB` and `B ≈ -19.9 dB`.

### 4.2 Forgetting

Evidence that is three hours old should not weigh as much as evidence from ten seconds ago. Cumulative evidence decays exponentially:

```
E_cumulative(t) = E_cumulative(t-1) · 2^(-Δt / T½)  +  E(t)
```

The half-life `T½` is a central parameter: too short and the system forgets and never concludes; too long and it stays stuck on a stale conclusion. Proposed initial value: **15 minutes of effective activity** (not wall-clock time, so that a lunch break does not wipe the history). To be calibrated in work package 3.

### 4.3 Levels

| Level | Cumulative evidence | P(impostor) | Meaning | Effect |
|---|---|---|---|---|
| **L0** | `E < B` | < 0.01 | Conforming | None |
| **L1** | `B ≤ E < 5 dB` | 0.01 to 0.24 | Nominal | None |
| **L2** | `5 ≤ E < 10 dB` | 0.24 to 0.50 | Weak signal | Logged, visible in the console |
| **L3** | `10 ≤ E < A` | 0.50 to 0.99 | Doubt | **Red overlay** (FR-60), alert |
| **L4** | `E ≥ A` | > 0.99 | Impostor conclusion | Alert, full decision event |

The display threshold of the red square, 50 % confidence, therefore falls at the entry of level L3.

**Hysteresis** (FR-62): going down a level requires dropping 3 dB below the rising threshold, and a minimum of 20 seconds at the current level. Without it, the indicator flickers at the slightest noise.

### 4.4 Two separate channels

In line with FR-35, the system maintains **two distinct cumulative evidences**, never blended:

| Channel | Question | Enrolment needed | Thresholds |
|---|---|---|---|
| **Identity** | Is it the same person? | Yes | `α = 0.01`, `β = 0.05` |
| **Humanity** | Is it a human? | No | `α = 0.001`, `β = 0.05` |

The Humanity channel is stricter on false alarms because it concludes that a compromise has happened, which is a heavier claim. It is also the fastest: an HID injection typically produces several tens of decibans within seconds.

The display combines both without adding them: the `P(impostor)` used for the overlay is the maximum of the two probabilities, and the console always states which of the two channels is responsible.

## 5. Calibration: when is the model ready?

My starting question: from what duration of use do I have enough data to recognise someone reliably?

**Answer: `X` is not a duration, it is a statistical condition, and its value in hours depends on the machine and the user.** The system measures `X` instead of postulating it.

### 5.1 The four convergence criteria (FR-21)

The enrolment phase ends when all four criteria are satisfied simultaneously. Each is shown as a percentage in the console.

| Criterion | Definition | Proposed initial value |
|---|---|---|
| **C1 - Volume** | Minimum observations per modality | 10,000 keystrokes, 5,000 pointing events, 300 pointings with a target (for Fitts), 8 sessions, 5 distinct days |
| **C2 - Stability** | The template no longer moves: Jensen-Shannon divergence between the template at `t` and at `t-Δ` below threshold, over 3 consecutive windows | JS < 0.02 over 3 windows of 24 h |
| **C3 - Performance** | EER self-estimated by temporal cross-validation (training on the first `k` sessions, test on the next), against a reference impostor population, with a 95 % bootstrap confidence interval | Upper bound of the CI < 8 % |
| **C4 - Coverage** | Contextual diversity: number of application categories, time slots, input devices | ≥ 4 categories, ≥ 3 time slots, all usual devices |

C3 is the decisive criterion: it is the only one that directly measures what matters. C1 prevents computing it on too little data, C2 guarantees that a transient regime has not been frozen, C4 that a single context has not been learned.

### 5.2 The convergence curve (FR-22)

The system produces and displays the curve of **estimated EER versus enrolment volume**, recomputed at each step. It gives:

- the empirical `X` for this machine and this user (the volume beyond which the curve flattens);
- an estimate of the time remaining before the end of enrolment, at the observed rate of use;
- a publishable result, since the same curve can be computed on the public corpora for comparison.

### 5.3 Phases

| Phase | Entry | What the system does | Exit |
|---|---|---|---|
| **Bootstrap** | First start | Observes, decides nothing, shows no alert. Only the Humanity channel is active (it requires no enrolment). | After C1 at 30 % |
| **Enrolment** | End of bootstrap | Builds the template, displays C1 to C4 progress, decides with widened thresholds and signals that reliability is partial | All four criteria at 100 % |
| **Operational** | End of enrolment | Nominal decision, nominal thresholds, anchor template frozen | Permanent |
| **Adaptation** | Continuous, from Operational onwards | Updates the template only with windows classified with high confidence, bounded rate | Permanent |

### 5.4 Protection against poisoning (FR-23, FR-24, threat M10)

Continuous adaptation is a way in: a patient impostor can make the template drift towards his own behaviour.

Three safeguards:

1. **Admission filter**: only windows with `E ≤ B` (a clear "genuine" conclusion) feed the update.
2. **Bounded rate**: the template cannot move by more than a fixed fraction per 24-hour period, whatever the amount of data.
3. **Frozen anchor**: the enrolment template is kept intact. A dedicated expert continuously compares the current template to the anchor; cumulative drift beyond a threshold triggers a drift alert, not a silent adjustment.

## 6. Counting and revising profiles

### 6.1 Hierarchical model

The trap identified in the analysis (section 3.6) is that one person produces several regimes. The model therefore has two tiers:

```
Identity (presumed person)
   └── Mode (contextual regime: external keyboard, trackpad, late session)
          └── Template of the mode
```

A new, well-separated regime that is **temporally interleaved** with a known regime (fast alternation between the two within a single session) is a **mode** of the same identity, not a new person. A regime that occupies disjoint time ranges and never coexists with the other is a candidate for being a distinct identity. This temporal interleaving criterion is the main discriminant between "mode" and "person".

### 6.2 Clustering

Representation: each activity window produces a vector of normalised signals. Clustering operates on those vectors with a **Dirichlet process mixture** (number of components unbounded a priori), or with an online approximation (BIRCH-style incremental aggregation, followed by a periodically recomputed Bayesian Gaussian mixture).

### 6.3 Revision (FR-41, FR-43)

This is the behaviour I want: start by believing in several users, then understand through cross-checking that there are fewer.

At regular intervals the system tests each pair of profiles:

- **Merge** if the distance between the two templates (Hellinger or Bhattacharyya) falls below a threshold **and** the likelihood ratio favours the single-component model **and** the occurrences are temporally interleaved.
- **Split** if a profile becomes clearly bimodal on several independent signals **and** the two subsets are temporally disjoint.

Each revision produces a permanent entry in `profile_revisions`, with the quantified statistical reason, rendered in the console as a timeline:

```
D+3   3 profiles   (a1b2, c3d4, e5f6)
D+9   merge c3d4 ← e5f6
      reason: Hellinger distance 0.08 < threshold 0.15
              likelihood ratio 1 component / 2 components = 4.2
              temporal interleaving 0.71 (the two regimes alternate in 14 sessions)
      conclusion: same person, two modes (internal keyboard / external keyboard)
D+9   2 profiles   (a1b2, c3d4)
```

### 6.4 Uncertainty (FR-44)

The number of profiles is never displayed as a certain integer. The Dirichlet process mixture naturally provides a posterior distribution over the number of components, rendered as: **"2 profiles, credible interval 2 to 3"**.

## 7. Explainability (FR-53, FR-56)

Explainability is not an after-the-fact reconstruction: it is the direct reading of the fusion formula.

For every decision, the console renders:

1. **The waterfall**: bar chart of the contributions `w_i · q_i · e_i` sorted by absolute value, whose sum is exactly the displayed evidence (FR-31).
2. **The five dominant pieces of evidence**, in natural language, generated from a sentence template per signal. Example: *"Mean digraph latency is 118 ms against a usual 164 ms (2.9 robust deviations below the reference): 7.2 dB against the legitimate user."*
3. **What pulled the other way**: the signals that supported the legitimate user, to avoid showing only the case for the prosecution.
4. **The responsible channel**: Identity or Humanity.
5. **The trajectory**: the cumulative evidence curve over the last hour, with the threshold crossing points.
6. **The simulator**: sliders to change the value of a signal and watch the evidence and the level move live. This is what makes the identification logic understandable rather than something to be put up with.

## 8. Parameters and initial values

All values below are **starting hypotheses to be calibrated in work package 3**, not justified constants. They are gathered in a single versioned configuration file, so that every experiment is reproducible.

| Parameter | Initial value | Calibrated in |
|---|---|---|
| `alpha_identity` | 0.01 | WP 3 |
| `beta_identity` | 0.05 | WP 3 |
| `alpha_humanity` | 0.001 | WP 5 |
| `evidence_half_life` | 15 min of effective activity | WP 3 |
| `damping_lambda` | 0.6 | WP 2, by measurement |
| `overlay_threshold` | P = 0.50 | Fixed by the need |
| `hysteresis` | 3 dB and 20 s | WP 6 |
| `typing_window` | 50 keystrokes or 60 s | WP 1 |
| `mouse_window` | 30 gestures or 60 s | WP 2 |
| `hellinger_merge_threshold` | 0.15 | WP 4 |
| `max_adaptation_rate` | 2 % of the template per 24 h | WP 3 |
