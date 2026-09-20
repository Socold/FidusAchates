# 03 - Decision engine, confidence and calibration

> Covers requirements FR-20 to FR-46 of the [requirements](01-REQUIREMENTS.md).

---

## 1. Guiding principle

A single decision is weak. The state of the art gives an EER of the order of 3 % to 10 % for a one-off decision, depending on the modality. The system therefore **never** tries to settle on one observation: it **accumulates evidence** and raises an alarm as soon as the accumulated evidence crosses a threshold set from a target false alarm rate.

Three properties are wanted at once, and a single formulation delivers all three:

1. **Speed**: detect a takeover with the shortest possible delay, at a fixed false alarm rate.
2. **Cross-checking**: combine heterogeneous signals on a common scale.
3. **Explainability**: know exactly what moved the decision.

The formulation that satisfies all three is a **sum of log-likelihood ratios**, accumulated by a **CUSUM** change detector. Cross-checking becomes an addition, and the explanation is that addition read term by term.

An earlier version of this document used Wald's SPRT with exponential forgetting and an inconsistent evidence sign. Both were wrong; see [07-DESIGN-REVIEW.md](07-DESIGN-REVIEW.md) A1 and A2, and [ADR-0007](adr/0007-cusum-and-logistic-fusion.md).

## 2. Unit of evidence: the deciban

Evidence is always evidence **for the impostor hypothesis**. For each signal `i` observed at value `x_i`:

```
e_i = 10 · log10 [ P(x_i | impostor) / P(x_i | genuine) ]      (in decibans)
```

- `e_i > 0`: the observation points to someone, or something, other than the legitimate user.
- `e_i < 0`: it supports the legitimate user.
- `e_i = 0`: the signal contributes nothing.

One convention, used everywhere: **up means suspicious**. Thresholds, levels, the console gauge and the overlay all follow it.

The deciban is an additive and readable unit: "this typing burst contributed 12 dB of evidence against the legitimate user" is a sentence with a precise meaning, displayable as is in the console (FR-53).

### 2.1 Fusion

Evidence over a window is a **linear logistic-regression fusion** of the experts' LLRs:

```
E = b + Σ_i  w_i · q_i · e_i
```

- `w_i`: weight of the signal, **learned** on development data by logistic regression over the experts' outputs. Redundant signals end up with small weights, which is how correlation between signals is handled: per signal, not with one global damping factor.
- `b`: offset learned at the same time; together with the weights it calibrates the fused score.
- `q_i`: **quality** of the current observation, in `[0, 1]` (enough observations, acceptable estimator variance). Zero if the evidence is too thin (FR-11): the signal then does not vote at all.

The fusion is linear, so the contribution `w_i · q_i · e_i` of each signal is **exact**. That is the property the whole explainability argument rests on (ADR-0004), and it is untouched.

### 2.2 Displayed probability

A posterior probability needs a prior, and the prior is stated, not hidden:

```
posterior_dB = prior_dB + S
P(impostor)  = 1 / (1 + 10^(-posterior_dB / 10))
```

where `S` is the accumulated evidence of section 4. The initial prior is **-10 dB** (about one chance in eleven that a given stretch of activity is not mine), to be revised in the calibration work package. With it, `P = 0.50` is reached at `S = 10 dB` and `P = 0.99` at `S = 30 dB`.

The displayed probability is an **aid to reading**. Alarms are not triggered by it but by the run-length thresholds of section 4; the two are specified separately on purpose.

## 3. Reference densities

Each signal needs two densities: under the genuine hypothesis and under the impostor hypothesis.

- **Genuine**: estimated during enrolment, with robust statistics (median, median absolute deviation) rather than mean and standard deviation, to withstand outliers.
- **Latencies are modelled on a log scale.** Hold times, flight times and pointing times are right-skewed, close to log-normal. A Gaussian on the raw scale gives wrong likelihood ratios in the tails, which is exactly where the evidence is. Default model: Gaussian on the robustly standardised **log** value, or a two-component mixture when the distribution is clearly bimodal (a sign of a second **mode**, cf. section 6).
- **Impostor**: two sources, in order of preference:
  1. The other profiles observed **on the same machine**, when there are any.
  2. A wide non-informative model centred on the genuine one.

Public corpora are **not** an impostor reference for my machine: they were recorded on other hardware, and hardware differences dominate differences between people (design review B4). They serve within-corpus experiments only.

**Calibration is mandatory.** Raw expert scores are not probabilities. Each expert goes through calibration, validated with a reliability diagram (FR-30). Without this step the addition is wrong and the explanation misleading.

## 4. Sequential detection

### 4.1 Why CUSUM

The question is not "which of two hypotheses has held since the start?" but "has the user changed at some **unknown moment**?". That is change detection. The CUSUM statistic is optimal for it: it minimises the detection delay for a given rate of false alarms.

```
S_t = max(0, S_{t-1} + E_t)          alarm when S_t ≥ h
```

Each window's fused evidence `E_t` is added; the statistic never goes below zero.

What the reflecting barrier at zero buys:

- A long, clean morning cannot be "spent" by an impostor in the afternoon: genuine evidence does not pile up as credit.
- No half-life to tune. Forgetting is replaced by the barrier.
- `S_t` is still a plain sum of per-signal contributions since it last left zero, so the explanation stays exact.

### 4.2 Thresholds from run lengths

Thresholds are set from **average run lengths**, which are my primary metrics:

| Quantity | Meaning | Metric |
|---|---|---|
| `ARL0` | Mean time between false alarms under genuine use | ANGA |
| `ARL1` | Mean detection delay once an impostor is present | ANIA, TTD |

`h` is chosen so that the measured `ARL0` meets the false alarm budget (AC-4: fewer than one per 8 hours of use). The expected delay is then roughly `h` divided by the mean evidence per window under the impostor hypothesis. Both are **measured by replay** on recorded traces, not derived from a formula.

### 4.3 Levels

Levels are bands of the CUSUM statistic. With the initial prior of -10 dB:

| Level | Statistic `S` | P(impostor) | Meaning | Effect |
|---|---|---|---|---|
| **L0** | `S = 0` | 0.09 (the prior) | Conforming | None |
| **L1** | `0 < S < 5 dB` | 0.09 to 0.24 | Nominal fluctuation | None |
| **L2** | `5 ≤ S < 10 dB` | 0.24 to 0.50 | Weak signal | Logged, visible in the console |
| **L3** | `10 ≤ S < h` | 0.50 and above | Doubt | **Red overlay** (FR-60) |
| **L4** | `S ≥ h` | | Alarm | Alert, full decision event, statistic reset |

The probabilities in this table are computed from the formula of section 2.2, and a unit test recomputes them: the table can no longer drift from the formula. `h` is calibrated; a plausible starting value is 25 dB.

**Hysteresis** (FR-62): going down a level requires dropping 3 dB below the rising threshold.

**Clearing without a timer.** `S` only changes when there is input. If an impostor walks away, nothing would ever clear the overlay. The statistic is therefore reset on **session lock** and after **idle** beyond a set duration, both delivered as logind events, so the agent still never polls (INS-1).

### 4.4 Two separate channels

In line with FR-35, the system maintains **two distinct CUSUM statistics**, never blended:

| Channel | Question | Enrolment needed | False alarm budget |
|---|---|---|---|
| **Identity** | Is it the same person? | Yes | 1 per 8 h of use |
| **Humanity** | Is it a human? | No | 1 per 30 days of use |

The Humanity channel is much stricter on false alarms because it concludes that a compromise has happened, which is a heavier claim. It is also the fastest: an injection typically produces several tens of decibans within seconds.

The display combines both without adding them: the `P(impostor)` used for the overlay is the maximum of the two, and the console always states which channel is responsible.

### 4.5 Deterministic indicators

Some facts need no statistics: a remote-desktop session is active, or the shell reports window activity while no hardware input arrives (design review A3). They are reported as **indicators** alongside the Humanity channel, with their own log entries, and can raise the overlay by themselves.

## 5. Calibration: when is the model ready?

My starting question: from what duration of use do I have enough data to recognise someone reliably?

**Answer: `X` is not a duration, it is a statistical condition, and its value in hours depends on the machine and the user.** The system measures `X` instead of postulating it.

### 5.1 The four convergence criteria (FR-21)

The enrolment phase ends when all four criteria are satisfied simultaneously. Each is shown as a percentage in the console.

| Criterion | Definition | Proposed initial value |
|---|---|---|
| **C1 - Volume** | Minimum observations per modality | 10,000 keystrokes, 5,000 pointing events, 300 pointings with a target (for Fitts), 8 sessions, 5 distinct days |
| **C2 - Stability** | The template no longer moves: Jensen-Shannon divergence between the template at `t` and at `t-Δ` below threshold, over 3 consecutive windows | JS < 0.02 over 3 windows of 24 h |
| **C3 - Performance** | Self-consistency by temporal cross-validation: the template trained on the first `k` sessions must accept the next one. Measured as the false alarm rate on held-out genuine sessions at the operating threshold | Within the AC-4 budget on 3 consecutive held-out sessions |
| **C4 - Coverage** | Contextual diversity: number of application categories, time slots, input devices | ≥ 4 categories, ≥ 3 time slots, all usual devices |

C3 is the decisive criterion. It deliberately measures only what can be measured honestly on one machine: that the model **keeps recognising me** on sessions it has not seen. It says nothing about rejecting impostors; an EER estimated against foreign hardware would be flattering and false (design review B4). Impostor rejection is measured separately, with real same-machine sessions, in the evaluation protocol. C1 prevents computing C3 on too little data, C2 guarantees that a transient regime has not been frozen, C4 that a single context has not been learned.

### 5.2 The convergence curve (FR-22)

The system produces and displays the curve of **held-out false alarm rate versus enrolment volume**, recomputed at each step. It gives:

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

1. **Admission filter**: a window feeds the update only if the statistic has stayed at `S = 0` over the last several windows **and** its own fused evidence is clearly negative.
2. **Bounded rate**: the template cannot move by more than a fixed fraction per 24-hour period, whatever the amount of data.
3. **Frozen anchor**: the enrolment template is kept intact. A dedicated expert continuously compares the current template to the anchor; cumulative drift beyond a threshold triggers a drift alert, not a silent adjustment.

### 5.5 Re-assurance: telling the system "it is me"

A new keyboard, an injured hand or a new desk can make the legitimate user look foreign for good. Without a way out, the tool gets uninstalled.

The way out is **re-assurance through real system authentication** (the platform's own password or biometric prompt). On success, the current regime is labelled as a new **mode** of the authenticated identity and starts its own enrolment.

It must be real authentication. A plain "it's me" button would be precisely the poisoning vector of threat M10: the impostor would press it.

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

All values below are **starting hypotheses to be calibrated**, not justified constants. They are gathered in a single versioned configuration file, so that every experiment is reproducible.

| Parameter | Initial value | Calibrated in |
|---|---|---|
| `prior_db` | -10 dB | WP 6 |
| `cusum_h_identity` | 25 dB, then set from `ARL0` = 8 h of use | WP 5 |
| `cusum_h_humanity` | set from `ARL0` = 30 days of use | WP 3 |
| `fusion_weights` | learned by logistic regression | WP 5 |
| `overlay_threshold` | P = 0.50, i.e. `S` = 10 dB at the initial prior | Fixed by the need |
| `hysteresis` | 3 dB | WP 3 |
| `idle_reset` | 10 min | WP 3 |
| `typing_window` | 50 keystrokes or 60 s | WP 4 |
| `mouse_window` | 30 gestures or 60 s | WP 4 |
| `hellinger_merge_threshold` | 0.15 | WP 8 |
| `max_adaptation_rate` | 2 % of the template per 24 h | WP 6 |
