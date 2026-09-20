# 06 - Roadmap and acceptance criteria

> Each work package ends on a **verifiable** criterion, not an impression. A package is not closed until its criterion has been measured and recorded in `research/`.
>
> Reordered after the [design review](07-DESIGN-REVIEW.md), section D. Three ideas drive the order: **record from day one** (the calendar is dominated by a 30-day trace), **make everything measurable before building on it**, and **spend Rust effort only on what measurement has kept**.

---

## Overview

| WP | Title | Purpose | Depends on |
|---|---|---|---|
| **0** | Foundation | Repository, licence, specifications, evaluation protocol | |
| **1** | Recorder | Minimal Rust capture, privacy reduction, reduced trace, self-confinement, CLI | 0 |
| **2** | Lab | Python trace reader, replay, evaluation bench, corpus ingestion | 1 |
| **3** | Attribution channel and overlay | Human/automation labelling, sanctioned-actor registry, deterministic indicators, GNOME Shell extension, red square | 1, 2 |
| **4** | Signal study | Every candidate signal, in Python, measured; about fifteen retained | 2 |
| **5** | Fusion and console | Logistic fusion, CUSUM, explainability, administration console | 4 |
| **6** | Enrolment | Convergence criteria, modes, re-assurance, anti-poisoning | 5 |
| **7** | Port to the agent | Retained signals and engine in Rust, resource budgets verified, installer | 6 |
| **8** | Multiple profiles | Clustering, revision, identity versus mode | 6 |
| **9** | Action sensitivity | Wire command-category sensitivity into the malice policy | 5, 8 |
| **10** | Porting | Windows, macOS, Linux X11, other compositors | 7 |
| **11** | Mobile | In-app SDK | 7 |

Critical path: 0 → 1 → 2 → 4 → 5 → 6 → 7. Package 3 runs in parallel as soon as 2 exists, and gives the first end-to-end result.

The `legit-long` trace (30 days) starts recording as soon as package 1 runs. Everything from package 4 onwards consumes it.

---

## WP 0 - Foundation

**Content**: repository, PolyForm Noncommercial 1.0.0 licence, documents 00 to 07, architecture decisions, evaluation protocol.

**Acceptance criterion**: the documents exist, are consistent with one another, and every requirement carries an explicit means of verification.

**Status**: done.

---

## WP 1 - Recorder

The only component that ever reads `/dev/input`. It must stay small enough to be read in one sitting.

**Content**
- `fidus-core`: event model, key classes, biomechanical digraph classes, trace format. No I/O, fully unit-tested.
- `fidus-agent`: device discovery, provenance tagging (hardware or virtual), hot-plug by `inotify`, event loop on `epoll`, no polling.
- Privacy reduction **at capture time**: a keycode never leaves the function that reads it.
- Reduced trace writer behind the `research-trace` build feature (FR-70).
- Self-confinement: `no_new_privs`, seccomp filter denying network sockets, start-up self-test (INS-14).
- Commands: `record`, `devices`, `doctor`.
- Dependencies: the C library binding and nothing else.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 1.1 | **Content-free, by property**: two different texts with the same class structure and the same timings produce byte-identical traces | Automated test, blocking |
| 1.2 | No keycode type appears in any persisted record | Compile-time: the record type has no such field; reviewed |
| 1.3 | The agent cannot open a network socket, even when started outside any sandbox | Automated test |
| 1.4 | 0 % CPU and no wake-up after 60 s with no input (INS-1, INS-2) | `powertop` over 5 min |
| 1.5 | The recorder runs 24 h with no memory growth and no lost event | RSS stable, sequence numbers contiguous |
| 1.6 | A virtual device is tagged virtual, a hardware one hardware | Test on sysfs path resolution, plus manual check |
| 1.7 | A trace written by the Rust recorder is read back identically by the Python reader | Cross-language test |
| 1.8 | Binary under 8 MB, no run-time dependency beyond libc (INS-21, INS-22) | CI |

**Status**: in progress.

---

## WP 2 - Lab

**Content**
- `fidus-lab` (Python, offline): trace reader, deterministic replay harness, evaluation bench (FAR, FRR, EER, ANIA, ANGA, TTD, run lengths), DET and ROC curves.
- Ingestion of the CMU, Balabit and SapiMouse corpora into the same event model.
- Result directory format of the evaluation protocol.

**Status**: reader, segmentation/replay, evaluation bench (FAR/EER/ANIA/ANGA/TTD) and CMU ingestion done and tested; a first synthetic-validation result is committed. Real-corpus run (2.2) gated on data.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 2.1 | Two replays of the same trace give a bit-identical result | Automated test |
| 2.2 | The scaled Manhattan baseline on CMU reproduces the published EER (about 0.096) | Within 0.01 |
| 2.3 | Run-length metrics are computed from a labelled trace | Test on a synthetic trace with a known change point |

---

## WP 3 - Attribution channel and overlay

**Status**: the attribution logic (WP3 brain) is in the lab; the GNOME Shell extension (`shell-extension/`) is written and installed, drawing the red square over D-Bus and exposing the focused application category and an activity tick. It needs a session relogin to activate (GNOME does not rescan live on Wayland). The deterministic indicators, the full E-signal set and the attack bench remain.

First end-to-end result: no enrolment needed, so the whole chain can be demonstrated within days of the recorder running.

**Content**
- Signals E01 to E14, E17 to E22, with the virtual-device allowlist (FR-38).
- Deterministic indicators (FR-37): remote session active, phantom activity, hot-plug then typing.
- Actor labelling (FR-34): human / automation_sanctioned / automation_unsanctioned / uncertain. Automation alone never alarms (FR-35b).
- Sanctioned-actor registry (FR-39): device patterns and time-boxed agent sessions, for AI assistants and MCP tools.
- Malice policy seam with a stubbed sensitivity (FR-47).
- GNOME Shell extension: application category and remote-session state over D-Bus, and the overlay.
- Red square at the top right, `research` and `silent` modes, clearing on lock and idle events.

**Attack bench** (reproducible, scripted):
1. Local automation through `uinput`.
2. Hardware HID injection.
3. Clipboard replay through an IP KVM.
4. Remote-desktop session.
5. Agent driving the desktop through the portal.
6. Adaptive adversary that slows down and randomises its delays.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 3.1 | AC-3: scenarios 1 to 3 detected in under 10 s with no enrolment | Attack bench |
| 3.2 | Scenarios 4 and 5 raised by a deterministic indicator, not by timing statistics | Attack bench |
| 3.3 | Scenario 6 detected by non-temporal signals | Attack bench |
| 3.3b | A declared agent session (an AI assistant or MCP tool driving input) is labelled `automation_sanctioned` and raises no overlay; the same automation outside a session is labelled `automation_unsanctioned` and is tagged, not alarmed | Scenario |
| 3.4 | Zero false alarms from the Attribution channel over 7 days of normal use, with a key remapper and a sanctioned agent running | Measurement |
| 3.5 | The overlay never steals focus, intercepts no click, and clears on lock | Documented manual test |
| 3.6 | The extension never exposes a window title or an executable name over D-Bus | D-Bus inspection |
| 3.7 | Without the extension the agent runs, and the console lists what it can no longer see (INS-25) | Test |

---

## WP 4 - Signal study

**Content**
- Every candidate of the [signal catalogue](04-SIGNAL-CATALOGUE.md), implemented **in Python**, on recorded traces and on the public corpora.
- Log-scale latency models; robust statistics.
- Measured discriminating power, stability across sessions, and sensitivity to hardware for each signal.
- Greedy forward selection on fused performance: about fifteen signals retained.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 4.1 | The catalogue's "Disc." hypotheses are replaced by measured values, failures included | Catalogue updated, results in `research/` |
| 4.2 | Biomechanical digraph classes are compared with true digraphs on a public corpus | Loss of discriminating power quantified; the default of ADR-0008 confirmed or reopened |
| 4.3 | Signals that mostly encode hardware are identified and barred from identity evidence | List published |
| 4.4 | The `(a,b)` pair of Fitts's law is stable across sessions | Coefficient of variation under 15 % |

---

## WP 5 - Fusion, CUSUM, explainability and console

**Status**: the web console (`fidus_lab.console`) is built and tested: a loopback HTTP server with a per-run token, Host/Origin validation (anti-rebinding), an SSE stream, and it drives the red overlay; a live runner replays a trace through it. The engine core (decibans, CUSUM, logistic fusion, a first keystroke expert, the Identity decision) is built in Python and validated end to end; explainability output and the console remain.

**Content**
- Expert calibration, reliability diagrams.
- Logistic-regression fusion over expert LLRs.
- CUSUM on the Identity channel, threshold set from run lengths measured by replay.
- Console: Live, Explanation, Model, Health and privacy views; annotation of alerts (FR-46); browser-side protections (SR-9, SR-10).

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 5.1 | The sum of displayed contributions equals the fused evidence | Gap under 0.01 dB |
| 5.2 | Experts are calibrated | Expected calibration error under 0.05 |
| 5.3 | The level table of 03 is recomputed from the formula by a test | Automated test |
| 5.4 | AC-1 on public corpora | Evaluation protocol |
| 5.5 | Rebinding and cross-site requests against the console are refused | Scripted test |

---

## WP 6 - Enrolment

**Status**: convergence criteria (C1, C2 via Jensen-Shannon stability, C4), phase transitions, and the anti-poisoning guards (admission filter, bounded update, anchor drift) are built and tested in Python. The C3 performance criterion reuses the bench; modes and system-authentication re-assurance remain.

**Content**
- Four life-cycle phases, criteria C1 to C4, held-out false alarm curve.
- Modes, and re-assurance through system authentication (FR-45).
- Anti-poisoning: admission filter, bounded rate, frozen anchor.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 6.1 | The convergence curve is produced and reproducible by replay | Two identical runs |
| 6.2 | AC-4: fewer than one false alarm per 8 h of legitimate use | 7 days, annotated |
| 6.3 | AC-1b: every same-machine impostor session detected | Per-session delays published |
| 6.4 | `legit-shift` scenario: new keyboard, re-assurance, a mode is created and alerts stop | Scenario |
| 6.5 | Threat M10: an impostor active 2 h a day for 7 days does not drift the template beyond the threshold | Attack test |

---

## WP 7 - Port to the agent

**Content**: the retained signals, the fusion and the CUSUM ported to Rust; encrypted aggregate storage; release build with no trace-writing code; both installation modes, including the capture helper; uninstaller.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 7.1 | The agent and the lab produce identical decisions on the same trace | Replay comparison, any divergence is a defect |
| 7.2 | AC-6: NFR-1 to NFR-4 met over 7 consecutive days | Health log |
| 7.3 | INS-20 to INS-28, in both installation modes | Tests on a blank machine |
| 7.4 | In hardened mode the user is not in the `input` group and the agent still works | Test |

---

## WP 8 - Multiple profiles

**Status**: clustering into profiles, the merge revision with logged statistical reasons, and the mode-versus-identity distinction via temporal interleaving are built and tested in Python (the two-distinct-people, one-person-many-regimes, and interleaved-two-devices cases pass). Live wiring and the Profiles view remain.

**Content**: session vectors, clustering with an unbounded number of components, identity versus mode with the temporal interleaving criterion, merge and split with logged statistical justification, Profiles view.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 8.1 | AC-5: exact count after 5 days on a controlled trace with 2 or 3 people | Evaluation protocol |
| 8.2 | The same person on two devices remains one profile with two modes | Scenario |
| 8.3 | At least one retrospective merge is observed and readably justified | Console timeline |
| 8.4 | The number of profiles is always shown with its credible interval | Interface review |

---

## WP 9 - Action sensitivity and the malice policy

Wire the stubbed sensitivity (FR-47) to the real command-category signals (C09, C10) and destructive-looking sequences, and let the policy lift or keep doubt on `automation_unsanctioned` accordingly (ADR-0011, decision engine 4.4b).

**Content**
- Sensitivity derived from command classes, elevation cadence, and mass-destructive patterns, all content-free.
- Policy: `automation_unsanctioned` in a sensitive context raises the overlay; in a benign context it stays a tag.
- Console: the sensitivity that lifted a doubt is shown in the explanation.

**Acceptance criteria**

| # | Criterion | Measure |
|---|---|---|
| 9.1 | Unsanctioned automation running a benign read-only sequence stays tagged, not alarmed | Scenario |
| 9.2 | Unsanctioned automation elevating privileges or mass-deleting raises the overlay | Attack bench |
| 9.3 | Wiring the real sensitivity changed no engine code, only the sensitivity provider | Diff review |

## WP 10 - Porting

Windows, macOS, Linux X11, and other Wayland compositors (layer-shell and foreign-toplevel replace the GNOME extension where available). Only the capture stage is rewritten.

**Acceptance criterion**: on each platform the criteria of WP 1 are met, and a trace captured there replays in `fidus-lab` without adaptation.

---

## WP 11 - Mobile

SDK embeddable in an application, modalities G01 to G10. Scope limited to the inside of the host application (cf. 00-ANALYSIS T6).

**Acceptance criterion**: AC-1 on a public touch corpus, with the same fusion engine and the same trace format as the desktop.

---

## Recurring costs to budget

- **GNOME Shell extension**: a major GNOME version every six months regularly breaks extensions. The extension stays minimal, supported Shell versions are pinned, and each GNOME release gets a check.

## What is not planned

In line with section 10 of the [requirements](01-REQUIREMENTS.md): centralised console, fleet deployment, coercive action on the machine, face recognition, audio or video capture, substitute IME keyboard, Android accessibility service.

These items are not "later": they are outside the project. Putting them on a roadmap, however distant, would be an invitation to build them.
