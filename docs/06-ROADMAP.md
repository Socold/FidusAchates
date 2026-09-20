# 06 - Roadmap and acceptance criteria

> Each work package ends on a **verifiable** criterion, not an impression. A package is not closed until its criterion has been measured and recorded in `research/`.

---

## Overview

| WP | Title | Purpose | Depends on |
|---|---|---|---|
| **0** | Foundation | Repository, licence, specifications, evaluation protocol | |
| **1** | Capture and typing | evdev agent, keyboard signals, storage, minimal console, basic automaton detection | 0 |
| **2** | Pointer and fusion | Mouse signals, LLR, SPRT, explainability | 1 |
| **3** | Calibration | Convergence criteria, performance curve, parameter calibration | 2 |
| **4** | Multiple profiles | Clustering, revision, modes | 3 |
| **5** | Humanity channel | Complete detection of non-human input | 2 |
| **6** | On-screen feedback | GNOME Shell extension, overlay | 2 |
| **7** | Research bench | Replay, public corpora, publishable results | 3 |
| **8** | Porting | Windows, macOS, Linux X11 | 5 |
| **9** | Mobile | In-app SDK | 7 |

Critical path: 0 → 1 → 2 → 3 → 4. Packages 5 and 6 can run in parallel after package 2.

---

## WP 0 - Foundation

**Content**: repository, PolyForm Noncommercial 1.0.0 licence, documents 00 to 06, architecture decisions, evaluation protocol, basic continuous integration, contribution and review templates.

**Acceptance criterion**: documents 00 to 06 exist, are consistent with one another, and every requirement carries an explicit means of verification.

**Status**: done.

---

## WP 1 - Capture and keystroke dynamics

**Content**
- `fidus-agent`: rootless `evdev` reading, normalisation, provenance tagging (E01).
- Hot buffer bounded to 10 s, never persisted.
- Signals A01 to A05, A07, A08, A10, A23.
- Event loop on `epoll`, no polling. Maintenance triggered by event thresholds.
- One-command installer, uninstaller, `fidus-cli doctor` checking prerequisites.
- Signals E01, E03, E05 (Humanity channel, no enrolment).
- Encrypted SQLite schema, Welford aggregates, approximate quantiles.
- Salted digraph hashing, levels P0 and P1.
- `fidus-cli`: `status`, `pause`, `resume`, `purge`, `doctor`.
- Console: minimal Live view (gauge, event stream, health).
- Hardened `systemd --user` unit.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 1.1 | The agent runs 24 h with no memory leak and no lost event | RSS stable under 40 MB, zero lost events |
| 1.2 | NFR-1 to NFR-4 met over 24 h of real use | Health log |
| 1.3 | "Content-free" test blocking in CI | 200 canary words typed, zero hits in the database |
| 1.4 | A `ydotool` injection is flagged as virtual | Automated test |
| 1.5 | A `ydotool` burst triggers L3 on the Humanity channel in under 10 s, with no enrolment at all | End-to-end test |
| 1.6 | `purge` leaves no residue | File system check |
| 1.7 | INS-1 and INS-2: 0 % CPU and no wake-up after 60 s with no input | `powertop` over 5 min |
| 1.8 | INS-10 to INS-14: no privilege at run time, no system service, no network access possible | Audit of the unit and the process |
| 1.9 | INS-20 to INS-24: one-command installation on a blank machine, under 60 s, binary under 8 MB | Test in a blank container |
| 1.10 | INS-26 and INS-27: uninstallation with no residue, no system file modified | Before and after comparison |

---

## WP 2 - Pointer, fusion and explainability

**Content**
- Signals B01 to B11, B13, B21, and E08.
- Expert calibration (Platt), reliability diagrams.
- Weighted LLR fusion, measurement of the damping factor.
- Two-threshold SPRT, exponential decay, hysteresis, levels L0 to L4.
- Two separate channels (Identity, Humanity).
- Console: Explanation view (waterfall in decibans, five dominant pieces of evidence, trajectory).

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 2.1 | The sum of displayed contributions equals the total evidence | Gap under 0.01 dB |
| 2.2 | The experts are calibrated | Expected calibration error under 0.05 |
| 2.3 | Simulated error rates match the targets | Gap under 20 % relative on `α` and `β` |
| 2.4 | The `(a,b)` pair of Fitts's law (B06) is estimated stably | Inter-session coefficient of variation under 15 % |
| 2.5 | Every alert produces a readable natural-language explanation | Review of 20 real alerts |

---

## WP 3 - Calibration

**Content**
- Four life-cycle phases, automatic transitions.
- Criteria C1 to C4, progress display.
- Performance versus volume curve, estimate of the `X` specific to the machine.
- Temporal cross-validation, bootstrap, confidence intervals.
- Calibration of the parameters of [03-DECISION-ENGINE.md](03-DECISION-ENGINE.md) section 8, by measurement.
- Measurement of the real discriminating power of each signal, and removal of the null ones.
- Anti-poisoning protection (admission filter, bounded rate, frozen anchor, signal F06).

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 3.1 | The performance versus volume curve is produced and reproducible by replay | Two identical runs |
| 3.2 | The empirical `X` of the machine is published with its confidence interval | Recorded in `research/` |
| 3.3 | AC-1 met: EER under 5 % over a 60 s window against a human impostor | Evaluation protocol |
| 3.4 | AC-4 met: fewer than one false alarm per 8 h of legitimate use | Measured over 7 days |
| 3.5 | The table of real discriminating power replaces the hypotheses of the catalogue | [04-SIGNAL-CATALOGUE.md](04-SIGNAL-CATALOGUE.md) updated |
| 3.6 | Scenario M10: an impostor active 2 h a day for 7 days does not drift the template beyond the threshold | Attack test |

---

## WP 4 - Multiple profiles

**Content**
- Session vector, clustering with an unbounded number of components.
- Identity / mode hierarchy, temporal interleaving criterion (F04).
- Revision by merge and split, with statistical justification.
- Permanent revision history.
- Number of profiles with uncertainty.
- Signals C01 to C08, D01 to D05, F01 to F03.
- Console: Profiles view.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 4.1 | AC-5 met: on a controlled trace with 2 or 3 people, the count is exact after 5 days | Evaluation protocol |
| 4.2 | The same person on two distinct devices remains a single profile, with two modes | Dedicated scenario |
| 4.3 | At least one retrospective merge is observed and readably justified | Timeline in the console |
| 4.4 | The number of profiles is always presented with its credible interval | Interface review |

---

## WP 5 - Complete Humanity channel

**Content**: signals E02, E04, E06, E07, E09 to E18, and F05. Dedicated attack bench.

**Attack bench** (reproducible, scripted):
1. `ydotool` and local automation.
2. Hardware HID injection (Rubber Ducky type key).
3. Clipboard replay through an IP KVM.
4. Remote session, RDP then VNC.
5. **AI agent driving the machine** (perceive / act loop on keyboard and mouse).
6. Statistical forgery: generator trained on the aggregates of the template (threat M8).
7. Adaptive adversary: automaton that slows down and randomises its delays to get around E03 and E05.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 5.1 | AC-3 met: scenarios 1 to 3 detected in under 10 s with no enrolment | Attack bench |
| 5.2 | Scenarios 4 and 5 detected in under 60 s | Attack bench |
| 5.3 | Scenario 7 (adaptive adversary) is detected by non-temporal signals (E01, E07, E10, E13) | Attack bench |
| 5.4 | Zero false alarms from the Humanity channel over 7 days of normal human use | Measurement |
| 5.5 | Scenario 6 is documented with its success rate, including if it defeats the system | Honest publication in `research/` |

---

## WP 6 - GNOME Shell extension and on-screen feedback

**Content**
- GNOME Shell extension: application context by category over D-Bus, and overlay.
- Red square at the top right, threshold `P > 0.50`, percentage displayed, hysteresis.
- `research` and `silent` modes.
- Health and privacy view in the console.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 6.1 | The square appears in under 500 ms after the threshold is crossed | Measurement |
| 6.2 | The overlay never steals focus and intercepts no click | Documented manual test |
| 6.3 | No more than one display transition per guard period | Measured over 24 h |
| 6.4 | The extension never exposes a window title or an executable name over D-Bus | D-Bus inspection |
| 6.5 | `silent` mode displays nothing | Check |
| 6.6 | INS-25: with no extension installed, the agent starts and works in degraded mode, and installation does not fail | Test with no extension |

---

## WP 7 - Research bench

**Content**
- `fidus-lab`: deterministic replay, evaluation bench (FAR, FRR, EER, ANIA, ANGA, TTD), DET and ROC curves.
- Documented, versioned trace format.
- Ingestion of the CMU, Balabit and SapiMouse corpora.
- First results report compared with the state of the art.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 7.1 | Two replays of the same trace give a bit-identical result | Automated test |
| 7.2 | At least one result comparable with the state of the art is published on a public corpus | Report in `research/` |
| 7.3 | AC-6 verified over 7 consecutive days | Health log |
| 7.4 | The report also publishes the non-discriminating signals and the failures | Review |

---

## WP 8 - Porting

Windows (Raw Input, `LLKHF_INJECTED` flag), macOS (`CGEventTap`), Linux X11. Only the `Source` stage is rewritten.

**Acceptance criterion**: on each platform, criteria 1.1 to 1.5 of WP 1 are met, and a trace captured on one platform can be replayed by `fidus-lab` without adaptation.

---

## WP 9 - Mobile

SDK embeddable in an application, modalities G01 to G10. Scope limited to the inside of the host application (cf. 00-ANALYSIS T6).

**Acceptance criterion**: EER under 10 % over a 60 s session of touch interaction, with the same fusion engine and the same trace format as the desktop.

---

## What is not planned

In line with section 10 of the [requirements](01-REQUIREMENTS.md): centralised console, fleet deployment, coercive action on the machine, face recognition, audio or video capture, substitute IME keyboard, Android accessibility service.

These items are not "later": they are outside the project. Putting them on a roadmap, however distant, would be an invitation to build them.
