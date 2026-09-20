# FidusAchates

**Implicit continuous authentication through behavioural biometrics, local and explainable.**

> *Fidus Achates*: the faithful companion of Aeneas. The one who walks alongside, who recognises, and who warns.

FidusAchates learns the way a person uses a device (typing rhythm, pointer gestures, sequence of applications, temporal rhythm), then continuously assesses two distinct questions:

1. **Is it still the same person?**
2. **Is it still a human?** (automaton, AI agent, HID injection, remote takeover)

All of it **without ever recording what is typed**, **with no network access at all**, and **explaining every decision**.

---

## Read this before installing

**This tool reads `/dev/input`. It therefore technically has the capabilities of a keylogger.** The project is designed never to use them that way, and that constraint is verified by blocking tests in continuous integration, but the power exists. Install it only if you are prepared to read the code, or to trust someone who has.

**Known limit, which cannot be worked around under Wayland:** there is no reliable way to detect that an input field is a password field. Protection rests on an application blocklist, immediate manual suspension, and the fact that in the default configuration no key code is kept in clear. See [docs/05-PRIVACY.md](docs/05-PRIVACY.md).

**Never observe another person without their explicit prior consent.** A behavioural template is biometric data in the sense of the GDPR (art. 4-14), falling under article 9. The conditions to meet before any use involving a third party are listed in [docs/05-PRIVACY.md](docs/05-PRIVACY.md) section 4.3.

---

## Status

**Design.** The reference documentation is stable. Implementation starts with work package 1.

| WP | Purpose | Status |
|---|---|---|
| 0 | Analysis, specifications, architecture, licence | done |
| 1 | evdev agent, keystroke dynamics, minimal console | to do |
| 2 | Pointer dynamics, LLR fusion, explainability | to do |
| 3 | Calibration | to do |
| 4 | Multiple profiles and revision | to do |
| 5 | Detection of non-human input (complete) | to do |
| 6 | GNOME Shell extension and overlay | to do |
| 7 | Research bench and public corpora | to do |
| 8 | Porting to Windows, macOS, X11 | to do |
| 9 | Mobile SDK | to do |

Detailed roadmap with acceptance criteria: [docs/06-ROADMAP.md](docs/06-ROADMAP.md).

## Documentation

| Document | Content |
|---|---|
| [00 - Analysis](docs/00-ANALYSIS.md) | Problem restated, tensions, sourced state of the art, threat model |
| [01 - Requirements](docs/01-REQUIREMENTS.md) | Numbered, verifiable requirements (FR, NFR, INS, PR, SR), acceptance criteria |
| [02 - Architecture](docs/02-ARCHITECTURE.md) | Components, flows, storage, portability |
| [03 - Decision engine](docs/03-DECISION-ENGINE.md) | LLR fusion, SPRT, levels, calibration, counting users |
| [04 - Signal catalogue](docs/04-SIGNAL-CATALOGUE.md) | 90 signals in 7 families, with cost, discriminating power and forgery difficulty |
| [05 - Privacy](docs/05-PRIVACY.md) | Processing register, legal qualification, ethics, risk of misuse |
| [06 - Roadmap](docs/06-ROADMAP.md) | Work packages and acceptance criteria |
| [07 - Design review](docs/07-DESIGN-REVIEW.md) | Critical re-reading of the design: errors found, decisions to reopen, gaps |
| [ADR](docs/adr/) | Architecture decisions and the alternatives ruled out |

## Design principles

**Content-free.** No typed content, window title, URL, file name or clipboard is captured. A blocking test in continuous integration types canary words and checks that none ends up in the database.

**Identity-free.** No civil identifier, account or serial number. Profiles are opaque labels such as `profile-a1b2`.

**Local-first, structurally.** The capture process runs under `PrivateNetwork=yes`: it has no network access to give, even if compromised. No telemetry, no CDN, no remote font.

**Explainable by construction.** The engine adds log-likelihood ratios expressed in decibans. The contribution of each signal to the decision is therefore **exact**, not estimated. The displayed explanation is the formula itself, read term by term.

**Observes, does not act.** The tool locks nothing, blocks nothing, logs nobody out. It flags.

## How it works, in short

```
Each signal contributes evidence, measured in decibans:

   e = 10 · log10 [ P(observation | genuine) / P(observation | impostor) ]

Evidence adds up, weighted by reliability and quality,
with old evidence gradually forgotten.

Wald's sequential test settles as soon as the cumulative evidence crosses
a threshold derived from the target error rates, hence as early as possible.
```

Two cumulative evidences are maintained separately, never blended:

| Channel | Question | Enrolment | Detects |
|---|---|---|---|
| **Identity** | Same person? | Required | Human takeover |
| **Humanity** | Human? | **None** | `ydotool`, BadUSB, IP KVM, RDP, AI agent |

The Humanity channel is the best value-to-risk ratio in the project: it detects the most concrete threats, it works from the first second, and **it stores no personal template**.

## Calibration

To the question "how long does it take for the tool to recognise me?", the project does not answer with an arbitrary duration. The end of enrolment is triggered by four measured convergence criteria (volume, template stability, performance self-estimated by temporal cross-validation with a confidence interval, contextual coverage), and the system produces the performance versus volume curve, which gives the real value for this machine and this user. Details in [docs/03-DECISION-ENGINE.md](docs/03-DECISION-ENGINE.md) section 5.

## Counting users

Clustering is done without knowing the number of people in advance, and it **revises itself**: two profiles judged indistinguishable are merged, with the statistical justification kept and displayed.

```
D+3   3 profiles
D+9   merge c3d4 ← e5f6
      Hellinger distance 0.08 < threshold 0.15
      likelihood ratio 1 component / 2 components = 4.2
      temporal interleaving 0.71 (the two regimes alternate in 14 sessions)
      conclusion: same person, two modes (internal keyboard / external keyboard)
D+9   2 profiles (credible interval 2 to 3)
```

The distinction between **mode** (one individual has several regimes) and **identity** is central: without it, the system systematically counts too many users.

## Footprint, installation and permissions

The tool is made to be installed once and forgotten. Its cost is measured **at rest**, the state in which it spends almost all of its time.

**Execution.** The agent is event-driven: it stays blocked on `epoll` waiting on the input descriptors. With no typing and no movement it does not run at all, and does not wake the processor. No polling loop, anywhere. The console does not exist until it is opened: it is started by socket activation.

| | At rest | Active |
|---|---|---|
| CPU | 0 % | under 1 % on average |
| Resident memory | under 40 MB | under 40 MB |
| Storage | under 2 MB per day of heavy use | |
| Binary | under 8 MB, installed footprint under 15 MB | |

**Permissions requested, in full:**

| Permission | When | Revocation |
|---|---|---|
| Membership of the `input` group | Once only, at installation | `sudo gpasswd -d $USER input` |

Nothing else, at any time: **no root at run time**, no setuid, no capability, no kernel module, no system service (`systemd --user` only), no network access, no accessibility permission, no browser extension, no system configuration file modified.

That single permission is nonetheless a strong privilege: it gives access to every input of the session. It is incompressible for global capture under Wayland. The project does not present it as harmless, it reduces it to the strict minimum and compensates with auditable sources and structural network isolation (`PrivateNetwork=yes`: the capture process has no network access to give, even if compromised). See [ADR-0006](docs/adr/0006-least-privilege-installation.md).

**Installation.** One command, prebuilt binary, no toolchain required, under 60 seconds to the first processed event. Complete uninstallation in one command, data purge included.

The GNOME Shell extension is **optional**: without it the agent works in degraded mode (application context and overlay are lost, the latter replaced by a desktop notification). Installation never fails for lack of the extension.

**Prerequisites (from work package 1)**

- Linux, Wayland or X11 session (developed on Fedora / GNOME / Wayland)
- Membership of the `input` group
- Optional: GNOME Shell, for application context and the overlay
- To contribute code: stable Rust; for `fidus-lab`, Python 3.12 or later, offline only

## Out of scope

Explicitly excluded, and refused in review: content recording, telemetry, productivity or presence measurement, coercive action on the machine, face recognition, audio or video capture, geolocation, substitute IME keyboard, Android accessibility service, centralised console, fleet deployment.

These items are not "planned for later": they are outside the project.

## Licence

**PolyForm Noncommercial 1.0.0.** Reading, modifying, redistributing and using the project are permitted for **research, study and teaching**. **Commercial use is prohibited.** All commercial rights are reserved to the author, who keeps the option of relicensing later.

The term "open source" in the sense of the Open Source Initiative does not apply, a field-of-use restriction being incompatible with criterion 6 of the OSI definition. The project therefore describes itself as **source-available** and as an **open research project**. See [ADR-0002](docs/adr/0002-noncommercial-licence.md).

## Sources and prior work

The project builds on a documented, sourced state of the art in [docs/00-ANALYSIS.md](docs/00-ANALYSIS.md) section 3: reference corpora (CMU, Balabit, SapiMouse, HMOG, Clarkson II), work on HID injection detection, literature on biometric fusion and sequential decision, overview of open and commercial UEBA tools, and standards ISO/IEC 19795, 24745, 30107 as well as NIST SP 800-63B.
