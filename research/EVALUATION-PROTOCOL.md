# Evaluation protocol

> Single reference for every published measurement. A figure quoted without reference to this protocol is not admissible.

---

## 1. Metrics

### 1.1 Classical metrics (ISO/IEC 19795)

| Metric | Definition |
|---|---|
| **FAR** | False acceptance rate: share of impostor windows classified as genuine |
| **FRR** | False rejection rate: share of genuine windows classified as impostor |
| **EER** | Point where FAR equals FRR. Used to compare, never to tune the system in operation |
| **DET curve** | FRR against FAR, on a normal deviate scale |

**Always state the decision unit**: a 60 s activity window, or a cumulative decision. An EER per window and an EER after accumulation are not comparable, and confusing the two is the main source of flattering and false figures in the literature.

### 1.2 Metrics specific to continuous authentication

| Metric | Definition | Why |
|---|---|---|
| **ANIA** | Average number of impostor actions before detection | Measures the real cost of an intrusion |
| **ANGA** | Average number of genuine actions before a false alarm | Measures the real nuisance to the user |
| **TTD** | Time to detection: median, 95th percentile | Answers "very quickly" |
| **Daily false alarm rate** | Number of alerts at L3 or above per 8 h of legitimate use | Acceptability metric |

ANIA and ANGA are the **primary** metrics of the project. FAR, FRR and EER are secondary metrics, kept to allow comparison with the state of the art.

### 1.3 Calibration metrics

| Metric | Threshold |
|---|---|
| Expected calibration error (ECE) | < 0.05 |
| Reliability diagram | Published for each expert |

An uncalibrated system can have an excellent EER and displayed probabilities that mean nothing. Since the console **displays** a probability to the user, calibration is a first-rank requirement, not a refinement.

### 1.4 Clustering metrics

| Metric | Definition |
|---|---|
| Accuracy of the number of profiles | Gap between the estimated number and ground truth, over time |
| Adjusted Rand index | Quality of the assignment of windows to profiles |
| Convergence delay | Time before the number of profiles stabilises |
| Number of revisions | Merges and splits before stabilisation |

### 1.5 Resource metrics

Mean and 95th percentile CPU, resident memory, storage growth per day, decision latency at the 95th percentile. Measured continuously, published with every performance result: **a performance gain obtained by exceeding the NFR budgets is not a gain.**

## 2. Datasets

### 2.1 Public corpora (comparison with the state of the art)

| Corpus | Modality | Use |
|---|---|---|
| CMU Keystroke Dynamics (Killourhy and Maxion) | Typing, fixed text | Reference yardstick, EER ≈ 0.096 for the scaled Manhattan distance |
| Clarkson II, Buffalo | Typing, free text | Closer to the real case |
| Balabit Mouse Dynamics Challenge | Pointer | Yardstick, 2025-2026 state of the art at EER ≈ 2.87 % |
| SapiMouse | Pointer | Second yardstick, EER ≈ 3.14 % |
| HMOG, Touchalytics | Touch and inertial | Work package 9 |

The corpora are not redistributed in the repository: `fidus-lab` provides ingestion scripts and the access conditions.

**Public corpora are used for within-corpus experiments only.** They were recorded on other keyboards, mice and capture stacks, and hardware differences dominate differences between people. Using them as an impostor population against my own machine would measure "my keyboard versus theirs" and yield an excellent, meaningless figure.

### 2.2 Own collection

| Trace | Content | Use |
|---|---|---|
| `legit-long` | 30 days of normal legitimate use, a single user | Calibration, false alarm rate |
| `multi-user` | Controlled, annotated sessions, 2 to 3 consenting people | Validation of profile counting |
| `impostor-naive` | Consenting third party using the machine with no instruction | Threat M6 |
| `impostor-trained` | Consenting third party who has observed the user and tries to imitate them | Threat M7 |
| `modes` | Same person, different devices and contexts | Validation of the mode / identity distinction |
| `attack-bench` | Six scripted attack scenarios (see WP 3) | Humanity channel |
| `legit-shift` | The legitimate user changing: new keyboard, other hand, late-night fatigue | Modes, re-assurance, false alarms |

Any trace involving a third party requires their prior written consent, in line with [docs/05-PRIVACY.md](../docs/05-PRIVACY.md) section 4.3.

## 3. Methodological rules

0. **Two tiers of evidence, never mixed.** *Statistical claims* (EER, DET curves, confidence intervals) come from public corpora, where the number of subjects supports them. *My own machine is a case study*: per-session detection delays, false alarm counts from annotated alerts, run lengths. With two or three recruited impostors, a bootstrap over subjects spans tens of points, so no EER is claimed from it.
1. **Temporal cross-validation only.** Training on the first `k` sessions, test on the next. Random cross-validation would mix past and future and produce optimistic, false figures.
2. **No leakage of the impostor population.** Profiles used as the impostor reference during training are never those of the test.
3. **Confidence intervals are mandatory.** 95 % bootstrap, over subjects and not over windows (the windows of one subject are not independent). **An EER quoted without a confidence interval is rejected.**
4. **Reproducibility.** Every measurement is produced by replaying a frozen trace, with a fixed seed, and two runs must give a bit-identical result.
5. **Versioned configuration.** The parameter file used accompanies every published result.
6. **Publishing failures.** Signals measured as non-discriminating, undetected attack scenarios and regressions are published just like successes. A catalogue containing only successes would be a biased catalogue.
7. **No tuning on the test set.** Parameters are tuned on a separate development set.

## 4. Format of results

Each campaign produces, in `research/results/YYYY-MM-DD-<name>/`:

```
config.toml          exact parameters used
trace.meta.json      trace identifier, volume, period, annotation
metrics.json         all metrics, with confidence intervals
det.svg  roc.svg     curves
per-signal.csv       measured discriminating power of each signal
resources.json       consumption observed during the campaign
README.md            conditions, deviations from the protocol, limits, conclusions
```

The campaign `README.md` must include a non-empty **Limits** section. A campaign with no identified limits signals an incomplete analysis, not a perfect result.

## 5. v1 targets

Reminder of the overall acceptance criteria of the [requirements](../docs/01-REQUIREMENTS.md) section 9:

| ID | Target |
|---|---|
| AC-1 | Public corpora: fused EER per window within 2 points of the published state of the art, with confidence interval |
| AC-1b | My machine: every same-machine impostor session detected, delay reported per session, no EER claimed |
| AC-2 | Median TTD under 90 s for a human impostor |
| AC-3 | TTD under 10 s for automated input, with no enrolment |
| AC-4 | Fewer than one false alarm per 8 h of legitimate use |
| AC-5 | Exact user count after 5 days, on a controlled trace |
| AC-6 | Resource budgets met 100 % of the time over 7 days |

These targets are **working hypotheses** drawn from the state of the art. They will be revised with real measurements, and every revision will be justified, dated and kept.
