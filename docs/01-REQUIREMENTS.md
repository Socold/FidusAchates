# 01 - Requirements

**Project**: FidusAchates
**Version**: 0.1
**Nature**: research project, source-available, commercial use reserved

> Read [00-ANALYSIS.md](00-ANALYSIS.md) first: it justifies the trade-offs below.

---

## 1. Purpose

FidusAchates is a local agent for **implicit continuous authentication** through behavioural biometrics. It learns the way a person uses a device, then continuously assesses the probability that the person at the controls is still the same one, and flags takeovers by another human or by an automaton.

**Purpose**: research in defensive security, detection of session hijacking and of non-human driving.

**Non-purpose, binding**: the tool is not meant to monitor productivity, the content of work, communications or location. Any feature heading that way is out of scope and must be refused in code review.

## 2. Glossary

| Term | Definition |
|---|---|
| **Template** | Statistical model of a profile's behaviour. Never raw data. |
| **Profile** | Opaque label for a set of behaviours attributed to one presumed person. |
| **Mode** | Sub-regime of a profile (external keyboard, trackpad, night session). A profile has several modes. |
| **Expert** | Module producing a score for one modality (typing, mouse, context, automation). |
| **LLR** | Log-likelihood ratio. The unit of evidence of the decision engine. |
| **Deciban (dB)** | Unit of evidence, `10·log10` of the likelihood ratio. |
| **EER** | Equal error rate (FAR = FRR). Standard comparison metric. |
| **ANIA** | Average number of impostor actions before detection. |
| **ANGA** | Average number of genuine actions before a false alarm. |
| **TTD** | Time to detection. |
| **Window** | Block of activity over which an expert produces a score (duration or event count). |

## 3. Use cases

| ID | Use case | Priority |
|---|---|---|
| UC-1 | The machine is left unlocked and a third party uses it. The tool detects it and shows it. | Must |
| UC-2 | An automaton or AI agent drives the keyboard and mouse. The tool detects it without prior enrolment. | Must |
| UC-3 | Open a local console to understand in real time what moves the confidence. | Must |
| UC-4 | Know how many distinct people have used the machine. | Must |
| UC-5 | Replay a past trace to compare two versions of the model. | Must |
| UC-6 | Measure the amount of use needed for the model to be reliable on this machine. | Must |
| UC-7 | Pause collection and purge the data. | Must |
| UC-8 | A remote session (RDP, VNC, RAT) takes over the machine. | Should |
| UC-9 | The tool runs on Windows or macOS. | Could (WP 8) |
| UC-10 | A mobile application embeds the SDK and assesses its own user. | Could (WP 9) |

---

## 4. Functional requirements (FR)

### 4.1 Collection

| ID | Requirement | Verification |
|---|---|---|
| **FR-1** | The agent captures keyboard and pointer events at the `evdev` level without root, through membership of the `input` group. | The agent starts and produces events under a non-root account. |
| **FR-2** | For each event the agent records: monotonic timestamp in microseconds, type, key or button **class**, source device identifier, and a virtual (`uinput`) or hardware provenance flag. | Unit test on a synthetic trace; an event injected by `ydotool` is flagged virtual. |
| **FR-3** | Depending on the configured granularity (P0, P1, P2, cf. 00-ANALYSIS T2), the agent keeps or drops the **salted hash** of the digraph. The salt is volatile and regenerated at every start. | Database inspection: no keycode in clear at P0 and P1; the salt is absent from disk. |
| **FR-4** | No typed content, window title, URL, file name or clipboard content is captured. | Automated test: grep the database for a corpus of canary words typed during collection; zero hits. This test is blocking in CI. |
| **FR-5** | Application context is reduced to a **category** (browser, terminal, office, development, communication, media, other) and a stable opaque identifier, obtained through the GNOME Shell extension. | The log never contains an executable name or a window title. |
| **FR-6** | The agent applies a blocklist of applications for which all capture is suspended. | No capture while a listed application is in use. |
| **FR-7** | A global shortcut and a CLI command suspend collection immediately, and a command purges the data. | Suspension takes effect in under a second and is visible in the console. |
| **FR-8** | Raw events are never persisted: only incremental aggregates and window vectors are. The in-memory ring buffer never exceeds 10 seconds of activity. | Code review plus integration test on buffer size. |

### 4.2 Signal extraction

| ID | Requirement | Verification |
|---|---|---|
| **FR-10** | The agent computes the signals of the [signal catalogue](04-SIGNAL-CATALOGUE.md), by family, as a stream and without a second pass. | Each signal has a unit test with a reference vector. |
| **FR-11** | Each signal exposes a **quality measure** (number of observations, estimator variance) so that it can be weighted or ignored when evidence is too thin. | A signal computed on fewer than N observations has zero weight in the fusion. |
| **FR-12** | Adding a new signal or a new expert requires no change to the fusion engine. | A sample expert is added in a test without touching the core. |

### 4.3 Learning and calibration

| ID | Requirement | Verification |
|---|---|---|
| **FR-20** | The life cycle has four explicit phases: **Bootstrap**, **Enrolment**, **Operational**, **Adaptation**. The current phase is shown in the console. | Transition observable over a multi-day collection. |
| **FR-21** | Leaving enrolment is not triggered by an arbitrary duration but by **four cumulative convergence criteria** C1 to C4 (volume, template stability, self-estimated performance, contextual coverage), defined in [03-DECISION-ENGINE.md](03-DECISION-ENGINE.md) section 5. | The console shows the progress of each criterion as a percentage; the transition happens only at 100 % of all four. |
| **FR-22** | The system produces a **"estimated performance versus enrolment volume" curve** specific to the machine, and derives from it the volume `X` actually needed, with a confidence interval. | The curve is exportable and reproducible by replay. |
| **FR-23** | In the adaptation phase, only windows classified with high confidence feed the template update, and the adaptation rate is bounded per period. | Attack test M10: an active impostor does not drift the template beyond a measured threshold. |
| **FR-24** | The initial enrolment template is kept frozen and serves as a reference anchor. | Anchor versus current template comparison available in the console. |

### 4.4 Decision and confidence

| ID | Requirement | Verification |
|---|---|---|
| **FR-30** | Each expert produces a score **calibrated** as a probability, converted to an LLR. | Reliability diagram: calibration gap below the set threshold. |
| **FR-31** | Fusion is a **weighted sum of LLRs**, hence exactly decomposable into per-signal contributions. | The sum of displayed contributions equals the total LLR, up to numerical error. |
| **FR-32** | The decision follows a **Wald SPRT** with two thresholds derived from the target error rates, with exponential decay of old evidence. | Simulation: observed error rates match the target rates. |
| **FR-33** | At any time the system exposes `P(impostor)` in `[0,1]` and a **level** L0 to L4. | Value readable through the local API and the console. |
| **FR-34** | Detection of non-human input (Q3) works **without enrolment** and is an independent expert. | On a blank machine, a `ydotool` injection is detected from the first burst. |
| **FR-35** | In its alerts the system distinguishes "different behaviour" (another human) from "non-human behaviour" (automaton), and does not blend them into a single score. | Two separate outputs, two separate thresholds. |
| **FR-36** | Every level change produces a timestamped **decision event**, keeping the contribution vector that led to the decision. | The log allows the decision to be reconstructed by replay. |

### 4.5 Estimating the number of users

| ID | Requirement | Verification |
|---|---|---|
| **FR-40** | The system groups activity windows into profiles without knowing their number in advance. | On a two-person trace, two profiles emerge. |
| **FR-41** | The system **revises** its partitions: two profiles judged indistinguishable are merged, a heterogeneous profile is split. | Test scenario: three initial profiles converge to two; the merge is logged. |
| **FR-42** | The system distinguishes **mode** from **identity**: the regimes of one person are attached to a single profile. | Scenario: the same person on internal then external keyboard remains one profile. |
| **FR-43** | The full revision history is kept and browsable, with the statistical reason for each merge or split. | The console shows the timeline "D+3: 3 profiles; D+9: merge #2 and #3, Hellinger distance 0.08 below threshold 0.15". |
| **FR-44** | The number of profiles is presented with an **uncertainty** and not as a certain integer. | Display of the form "2 profiles (credible interval 2 to 3)". |

### 4.6 Administration console

| ID | Requirement | Verification |
|---|---|---|
| **FR-50** | Web console served locally, bound to `127.0.0.1` only, protected by a token. | `ss -lntp` shows no listener on an external interface. |
| **FR-51** | Real-time updates through a pushed stream (SSE), with no reload and no polling. | Perceived latency under 500 ms between the action and its effect on screen. |
| **FR-52** | **Live** view: confidence gauge, cumulative LLR curve, stream of decision events, automation indicators. | Visual review plus end-to-end test. |
| **FR-53** | **Explanation** view: waterfall chart of contributions in decibans over the current window, and a natural-language sentence for the five dominant pieces of evidence. | Every alert comes with a readable "why". |
| **FR-54** | **Profiles** view: detected profiles, modes, revision timeline, inter-profile separability matrix. | Covers FR-43 and FR-44. |
| **FR-55** | **Model** view: enrolment progress (C1 to C4), estimated EER with confidence interval, DET and ROC curves, performance versus volume curve. | Covers FR-21 and FR-22. |
| **FR-56** | **Teaching** view: explanation of how each expert works, learned distributions, and an interactive simulator to vary a signal and watch the effect on the LLR. | Makes the identification logic understandable. |
| **FR-57** | **Health and privacy** view: CPU and memory consumption, event throughput, stored volume, active granularity level, collection state, purge button. | Covers NFR and PR. |
| **FR-58** | All displayed data can be exported as JSON and CSV. | Export verified on each view. |

### 4.7 On-screen feedback

| ID | Requirement | Verification |
|---|---|---|
| **FR-60** | In `research` mode, a red square indicator appears **at the top right of the screen** as soon as `P(impostor) > 0.50`, showing the confidence percentage. | Manual test with injected foreign behaviour. |
| **FR-61** | The indicator is drawn by the GNOME Shell extension, above all windows, without stealing focus or intercepting clicks. | Normal use is not disturbed. |
| **FR-62** | Intensity or opacity follows the score, and the indicator disappears below the threshold with hysteresis to avoid flicker. | No more than one transition per guard period. |
| **FR-63** | `silent` mode disables all visual feedback and only logs. | Nothing on screen in `silent` mode. |

### 4.8 Replay and research

| ID | Requirement | Verification |
|---|---|---|
| **FR-70** | Signal traces (never content) can be exported in a documented, versioned format. | Schema published in `research/`. |
| **FR-71** | The complete engine can be **replayed offline** on a trace, deterministically. | Two runs on the same trace produce bit-identical output. |
| **FR-72** | An evaluation bench computes FAR, FRR, EER, ANIA, ANGA and TTD on an annotated trace. | Reproducible results, published in `research/`. |
| **FR-73** | The bench can ingest the public corpora (CMU, Balabit, SapiMouse) for comparison with the state of the art. | At least one comparable result published. |

---

## 5. Non-functional requirements (NFR)

| ID | Requirement | Threshold | Verification |
|---|---|---|---|
| **NFR-1** | Agent CPU consumption, averaged over an hour of heavy use | < 1 % of one core | Continuous measurement, displayed and logged |
| **NFR-2** | Agent resident memory | < 40 MB | Same |
| **NFR-3** | Storage growth | < 2 MB per day of heavy use | Same |
| **NFR-4** | Latency between an event and the score update | < 250 ms at the 95th percentile | Internal instrumentation |
| **NFR-5** | Console consumption, tab open continuously | < 2 % CPU, < 150 MB | Browser measurement |
| **NFR-6** | Agent start-up | < 500 ms to the first processed event | Measured at start |
| **NFR-7** | Weight of front-end assets | < 300 KB transferred, no CDN dependency | CI check |
| **NFR-8** | The agent loses no event under load: when saturated, it degrades its sampling rate rather than blocking user input | No perceptible typing latency | Load test |
| **NFR-9** | No network dependency in the agent | Zero outbound socket | Blocking integration test in CI, and dependency audit |
| **NFR-10** | The project builds and runs offline | Successful build with no network access once dependencies are fetched | Test in an isolated container |

## 6. Installation, execution and permissions (INS)

Three requirements are grouped here because they constrain one another: the tool must be **light**, run **in the background** without anyone having to think about it, and **not ask for privileges**.

### 6.1 Execution model

The agent is **event-driven**, never polling: it stays blocked on `epoll` waiting on the `evdev` descriptors. With no typing and no movement, it does not run at all. That is the property that makes permanent background operation credible.

| ID | Requirement | Threshold | Verification |
|---|---|---|---|
| **INS-1** | No polling loop: the process is blocked waiting for events | 0 CPU wake-ups per second at rest | `powertop`, or `/proc/<pid>/schedstat` over 5 min with no input |
| **INS-2** | CPU consumption at rest, after 60 s with no input at all | 0.0 % measurable | Continuous measurement |
| **INS-3** | Maintenance tasks (aggregation, purge, profile recomputation) are triggered by event thresholds and not by the clock, capped at one run every 5 minutes | | Instrumentation |
| **INS-4** | No maintenance task when the machine is on low battery, suspended or in power saving | | Test on a laptop |
| **INS-5** | The console consumes nothing until it is opened: started by socket activation | 0 resident process | `systemctl --user status` |
| **INS-6** | The agent never delays or prevents session logout or shutdown | Clean stop in under 2 s | Test |
| **INS-7** | When the system saturates, the agent lowers its sampling rate. It never delays an input event on its way to the destination application | No perceptible typing latency | Load test |

**Architectural property to preserve at all costs**: the agent **reads** `/dev/input` in parallel with the display server, it does not sit in the input path. By construction it can therefore neither block nor slow down input, **even if it crashes**. Any change that would break this property is to be refused.

### 6.2 Permissions requested

Principle: **a single privileged operation, once, at installation, reversible in one command.**

| Permission | When | Why | Revocation |
|---|---|---|---|
| Membership of the `input` group | Installation, once | Read `/dev/input/event*` without root | `sudo gpasswd -d $USER input` |

Nothing else is requested, at any time.

| ID | Requirement | Verification |
|---|---|---|
| **INS-10** | No root privilege at start-up or during execution | `ps` confirms execution under the user account |
| **INS-11** | No setuid binary, no `CAP_*` capability, no kernel module, no system patch | Package audit |
| **INS-12** | No system service: `systemd --user` only | No unit dropped in `/etc/systemd/system` |
| **INS-13** | No write access outside `~/.local/share/fidusachates` and `~/.config/fidusachates` | `ProtectSystem=strict` plus test |
| **INS-14** | No network access, structurally impossible | `PrivateNetwork=yes` on the capture process |
| **INS-15** | No accessibility permission, no browser extension, no camera, microphone, location or intrusive system notification access | Audit |
| **INS-16** | The installer lists the requested permissions **before** requesting them, and takes none without explicit agreement | Test of the installation flow |
| **INS-17** | Any future additional permission is a change to the requirements, not an implementation decision | Review |

**Tension named and owned.** The `input` group is a strong privilege: it gives access to every input of the session, hence the ability to build a keylogger. It is **incompressible** for global capture under Wayland, and there is no less privileged alternative that keeps the scope of the project. The project does not play this down: it reduces the privilege to the strict minimum (once, no root at run time, reversible), and compensates with auditable sources and structural network isolation. See [ADR-0006](adr/0006-least-privilege-installation.md).

### 6.3 Installation and footprint

| ID | Requirement | Threshold | Verification |
|---|---|---|---|
| **INS-20** | One-command installation, with no toolchain on the user's machine | Prebuilt binary provided | Test on a blank machine |
| **INS-21** | No run-time dependency beyond the system C library | `ldd` lists only libc and its direct dependencies | CI check |
| **INS-22** | Agent binary size | < 8 MB | CI |
| **INS-23** | Total installed disk footprint, excluding data | < 15 MB | CI |
| **INS-24** | Time from the install command to the first processed event | < 60 s | Timed test |
| **INS-25** | **Degraded mode**: the agent works without the GNOME Shell extension. Signal family C and the overlay are lost, the latter replaced by a standard desktop notification. Installation must never fail for lack of the extension | Test with no extension installed |
| **INS-26** | Complete uninstallation in one command, data purge included, removal from the `input` group offered | No residue on the file system |
| **INS-27** | The tool modifies no system configuration file, no shell profile, no global `PATH` | File system comparison before and after |
| **INS-28** | Automatic start at session login through `systemd --user`, can be disabled in one command | Test |

## 7. Privacy and compliance requirements (PR)

| ID | Requirement | Verification |
|---|---|---|
| **PR-1** | Content-free: no typed, displayed or copied content is captured. | Blocking test FR-4. |
| **PR-2** | Identity-free: no civil identifier, account, address, serial number. Profiles are opaque labels. | Database schema audit. |
| **PR-3** | Local-first: no outbound network, no telemetry, no third-party service. | NFR-9. |
| **PR-4** | The template and the database are encrypted at rest, the key being kept in the system keyring. | Database unreadable outside the user session. |
| **PR-5** | Complete purge in one command, and bounded default retention (90 days of aggregates, 7 days of detailed vectors). | Verification after expiry. |
| **PR-6** | Every piece of collected data is documented in a public register in the repository: what, why, how long, where. | [05-PRIVACY.md](05-PRIVACY.md) kept up to date, checked in review. |
| **PR-7** | Consent is explicit at first start, with a plain-language explanation of what is captured and what is not. | First launch blocked until consent is given. |
| **PR-8** | The project provides a DPIA template and the list of conditions to meet before any use involving a third party. | Document present in `docs/`. |
| **PR-9** | The tool refuses by design to produce productivity, presence or content metrics. | Code review: any such request is refused and traced. |
| **PR-10** | Irreversibility and unlinkability of templates, in the spirit of ISO/IEC 24745. | Documentation of the protection scheme, and inversion test. |

## 8. Security requirements of the product (SR)

A tool that reads `/dev/input` is a high-value target. These requirements protect it.

| ID | Requirement | Verification |
|---|---|---|
| **SR-1** | Minimal attack surface: no network port, IPC over a UNIX socket with permissions restricted to the user account. | Audit. |
| **SR-2** | The console requires a token, regenerated at every start, never persisted in clear. | Access refused without the token. |
| **SR-3** | Privilege separation: the capture process only captures, and has neither network access nor write access to the rest of the file system. Documented `systemd` hardening. | `systemd` unit with `ProtectSystem`, `PrivateNetwork`, `NoNewPrivileges`, `SystemCallFilter`. |
| **SR-4** | Dependencies are minimal, pinned, and audited automatically. | CI audit, blocking on a known high-severity vulnerability. |
| **SR-5** | The build is reproducible and the release signed. | Verifiable checksum. |
| **SR-6** | Detection and logging of agent service interruptions (threat M11). | A service stop leaves a timestamped trace. |
| **SR-7** | Resistance to template poisoning (threat M10): see FR-23 and FR-24. | Attack scenario in the evaluation bench. |
| **SR-8** | No secret, key or token in the repository. Automatic scan on every commit. | CI check. |

---

## 9. Overall acceptance criteria

The project is considered to reach its research goal when the following six conditions are simultaneously verified and published in `research/`:

| ID | Criterion | v1 target |
|---|---|---|
| **AC-1** | EER of the fused decision over a 60-second activity window, uninformed human impostor | < 5 % |
| **AC-2** | Median time to detection for a human impostor (UC-1) | < 90 seconds of activity |
| **AC-3** | Time to detection for automated input (UC-2, no enrolment) | < 10 seconds of activity |
| **AC-4** | False alarms in normal legitimate use | < 1 per 8 hours of use |
| **AC-5** | Estimate of the number of users, on a controlled trace with 2 or 3 people | Exact after 5 days, revisions logged |
| **AC-6** | Budgets NFR-1 to NFR-4 met continuously | 100 % of the time over 7 days |

These targets are working hypotheses drawn from the state of the art (EER of 2.9 % to 10 % depending on the modality for an isolated decision, improved by sequential accumulation). They will be revised after work package 3 with the real measurements from the machine, and every revision will be justified and dated.

## 10. Out of scope

Explicitly excluded, and to be refused in review:

- Recording typed content, window titles, URLs, the clipboard, screenshots.
- Any form of telemetry, upload to a server, synchronisation between machines.
- Measuring productivity, presence time, attendance.
- Automatic session blocking, locking, logout or any coercive action. The tool observes and flags; it does not act on the machine. A possible response action would be a separate decision, to be specified in its own right.
- Face recognition, audio capture, video capture, geolocation.
- Substitute IME keyboard and Android accessibility service (cf. 00-ANALYSIS T6).
- Bypassing the iOS or Android sandbox.
- Fleet deployment, multi-machine management, centralised console.

## 11. Deliverables

| WP | Deliverable | Reference |
|---|---|---|
| 0 | Repository, licence, analysis, requirements, evaluation protocol | this document |
| 1 to 9 | See the roadmap and its per-package acceptance criteria | [06-ROADMAP.md](06-ROADMAP.md) |

## 12. Licence and legal status

The project is published as **source-available** under **PolyForm Noncommercial 1.0.0**: reading, modifying, redistributing and using it for research and teaching are permitted; **commercial use is prohibited**. Commercial rights are fully reserved to the author, who may later publish a version under another licence.

The term "open source" in the sense of the Open Source Initiative does not apply, since a field-of-use restriction is incompatible with criterion 6 of the OSI definition. The repository therefore uses "source-available" or "open research". See [ADR-0002](adr/0002-noncommercial-licence.md).
