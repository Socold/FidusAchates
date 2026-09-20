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

The decision logic of the whole project is built and tested in Python (the lab),
the recorder is built in Rust and measured on a real machine, and the two
interfaces (the GNOME red-square overlay and the local web console) exist. What
remains is mostly system porting, wiring on real data, and measurements gated on
real corpora.

| WP | Purpose | Status |
|---|---|---|
| 0 | Analysis, specifications, architecture, licence | done |
| 1 | Recorder: capture, privacy reduction, reduced trace, self-confinement | done, measured on the real machine |
| 2 | Lab: trace reader, replay, evaluation bench, corpus ingestion | done (real-corpus run gated on data) |
| 3 | Attribution channel, GNOME Shell extension, red overlay | logic and extension done; live wiring and attack bench remain |
| 4 | Signal study in Python, about fifteen signals retained | machinery done (real ranking gated on data) |
| 5 | Fusion, CUSUM, explainability, console | done (bimodal mixtures, per-signal explanation) |
| 6 | Enrolment, convergence criteria, anti-poisoning, modes | done (re-assurance remains) |
| 7 | Port of the retained signals to the Rust agent | to do (after signals are chosen on real data) |
| 8 | Multiple profiles and revision (counting users) | done |
| 9 | Action sensitivity wired into the malice policy | to do |
| 10 | Porting to Windows, macOS, X11, other compositors | to do |
| 11 | Mobile SDK | to do |

Detailed roadmap with acceptance criteria and per-package status:
[docs/06-ROADMAP.md](docs/06-ROADMAP.md).

## Running and testing it

The recorder builds in a container, so Rust is not needed on the host:

```bash
make docker-test          # build and test the Rust recorder, offline, in Docker
```

The lab (the decision engine, attribution, enrolment, profiles, console) is pure
Python, standard library only:

```bash
cd lab && python3 -m pytest        # the full lab test suite
```

Analyse a reduced trace end to end (segments, actor labels, decisions, outcomes):

```bash
python3 -m fidus_lab <trace.fidustr>
```

Serve the live console, which streams the analysis and drives the red overlay:

```bash
python3 -m fidus_lab.console_main <trace.fidustr> --open
```

The red square is a GNOME Shell extension. Install it, then **log out and back
in** (GNOME does not rescan the extensions directory live on Wayland) and enable
it:

```bash
cp -r shell-extension/fidusachates@socold.github.io ~/.local/share/gnome-shell/extensions/
# log out and back in
gnome-extensions enable fidusachates@socold.github.io
# show a 72% red square directly:
gdbus call --session -d org.fidusachates.Overlay -o /org/fidusachates/Overlay \
  -m org.fidusachates.Overlay.SetConfidence 72 Identity
```

A reduced trace is produced by a recorder built with the `research-trace`
feature: `fidus-agent record --trace out.fidustr`. See
[shell-extension/README.md](shell-extension/README.md) and
[research/TRACE-FORMAT.md](research/TRACE-FORMAT.md).

## Documentation

| Document | Content |
|---|---|
| [00 - Analysis](docs/00-ANALYSIS.md) | Problem restated, tensions, sourced state of the art, threat model |
| [01 - Requirements](docs/01-REQUIREMENTS.md) | Numbered, verifiable requirements (FR, NFR, INS, PR, SR), acceptance criteria |
| [02 - Architecture](docs/02-ARCHITECTURE.md) | Components, flows, storage, portability |
| [03 - Decision engine](docs/03-DECISION-ENGINE.md) | LLR fusion, CUSUM, levels, calibration, counting users |
| [04 - Signal catalogue](docs/04-SIGNAL-CATALOGUE.md) | About a hundred candidate signals in 7 families, of which about fifteen are meant to survive measurement |
| [05 - Privacy](docs/05-PRIVACY.md) | Processing register, legal qualification, ethics, risk of misuse |
| [06 - Roadmap](docs/06-ROADMAP.md) | Work packages and acceptance criteria |
| [07 - Design review](docs/07-DESIGN-REVIEW.md) | Critical re-reading of the design: errors found, decisions reopened, gaps |
| [08 - Code review](docs/08-CODE-REVIEW.md) | Critical re-reading of the code: confirmed bugs, weaknesses, and the fix and test for each |
| [Trace format](research/TRACE-FORMAT.md) | Binary format of the reduced research trace |
| [ADR](docs/adr/) | Architecture decisions and the alternatives ruled out |

Among the decisions, [ADR-0011](docs/adr/0011-attribution-not-malice.md) separates *attribution* (human or automated, sanctioned or not) from the judgment of *malice*.

## Code

| Path | What |
|---|---|
| [crates/fidus-core](crates/fidus-core) | Event model, privacy reduction and trace format (Rust, no dependency): the privacy boundary |
| [crates/fidus-agent](crates/fidus-agent) | The recorder: evdev capture, self-confinement, hot-plug (Rust, libc only) |
| [lab/fidus_lab](lab/fidus_lab) | Decision engine, attribution, enrolment, profiles, console (Python, offline) |
| [shell-extension](shell-extension) | GNOME Shell extension: the red overlay and content-free context |
| [research](research) | Trace format, evaluation protocol, results |

## Design principles

**Content-free.** No typed content, window title, URL, file name or clipboard is captured. A blocking test in continuous integration types canary words and checks that none ends up in the database.

**Identity-free.** No civil identifier, account or serial number. Profiles are opaque labels such as `profile-a1b2`.

**Local-first, structurally.** At start-up the agent installs a seccomp filter that denies network sockets, checks that opening one fails, and refuses to run otherwise. It has no network access to give, even if compromised, and does not rely on its unit file for that. No telemetry, no CDN, no remote font.

**Explainable by construction.** The engine adds log-likelihood ratios expressed in decibans. The contribution of each signal to the decision is therefore **exact**, not estimated. The displayed explanation is the formula itself, read term by term.

**Observes, does not act.** The tool locks nothing, blocks nothing, logs nobody out. It flags.

## How it works, in short

```
Each signal contributes evidence for the impostor hypothesis, in decibans:

   e = 10 · log10 [ P(observation | impostor) / P(observation | genuine) ]

Evidence adds up, with weights learned by logistic regression.

A CUSUM detector accumulates it:   S = max(0, S + E)

and raises an alarm when S crosses a threshold set from the false alarm
budget. It answers "has the user changed at some unknown moment?" with the
shortest possible delay, and genuine use never piles up as credit.
```

Two things are tracked separately, never blended:

| Channel | Question | Enrolment | Output |
|---|---|---|---|
| **Identity** | Same person? | Required | An alarm on takeover |
| **Attribution** | A human, or automation the user did or did not sanction? | **None** | A label, not an alarm |

The Attribution channel matters because **automated is not the same as hostile**. A developer's AI coding assistant, or a user's MCP tools, produce automation that is wanted: the tool labels it `automation_sanctioned` and stays quiet. Unknown automation is tagged too, and only becomes an alert when it coincides with identity divergence or a sensitive action (privilege elevation, credential rotation, mass deletion). The tool under-reacts rather than cry wolf on the people most likely to run it. See [ADR-0011](docs/adr/0011-attribution-not-malice.md).

## Calibration

To the question "how long does it take for the tool to recognise me?", the project does not answer with an arbitrary duration. The end of enrolment is triggered by four measured convergence criteria (volume, template stability, false alarm rate on held-out sessions, contextual coverage), and the system produces the convergence curve, which gives the real value for this machine and this user. Details in [docs/03-DECISION-ENGINE.md](docs/03-DECISION-ENGINE.md) section 5.

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

These are **budgets I hold the project to, not measurements**. They become measurements as work packages close, and the numbers will be published either way.

| Budget | At rest | Active |
|---|---|---|
| CPU | 0 %, no wake-up | under 1 % on average |
| Resident memory | under 40 MB | under 40 MB |
| Storage | | under 2 MB per day of heavy use |
| Binary | under 8 MB, installed footprint under 15 MB | |

**Permissions requested, in full.** Two installation modes, because the cheapest permission is not the safest one:

| Mode | Privileged step, once | Who can read `/dev/input` afterwards |
|---|---|---|
| **Simple** | You join the `input` group (`sudo gpasswd -d $USER input` reverts it) | **Every process running as you** |
| **Hardened** | A minimal capture helper is installed as a system service under a dedicated account | The helper only |

Simple mode is the lightest, and it removes a system-wide protection against keyloggers for your whole session. It is acceptable on a personal research machine and I say so plainly; anywhere else, use hardened mode. Nothing else is requested in either mode: **no root at run time**, no setuid, no capability, no kernel module, no network access, no accessibility permission, no browser extension. See [ADR-0009](docs/adr/0009-capture-helper-install-modes.md).

**Installation.** One command, prebuilt binary, no toolchain required, under 60 seconds to the first processed event. Complete uninstallation in one command, data purge included.

The GNOME Shell extension is **optional to install, not optional for coverage**: without it the agent works, but loses application context, the overlay, and all detection of remote-desktop sessions and portal-driven agents, whose input never reaches `evdev` under Wayland. Installation never fails for lack of the extension, and the console lists the blind spots.

**Prerequisites (from work package 1)**

- Linux, Wayland or X11 session (developed on Fedora / GNOME / Wayland)
- Membership of the `input` group
- Optional: GNOME Shell, for application context and the overlay
- To build: stable Rust, or Docker (`make docker-test` needs nothing else); for `fidus-lab`, Python 3.12 or later, offline only

## Out of scope

Explicitly excluded, and refused in review: content recording, telemetry, productivity or presence measurement, coercive action on the machine, face recognition, audio or video capture, geolocation, substitute IME keyboard, Android accessibility service, centralised console, fleet deployment.

These items are not "planned for later": they are outside the project.

## Licence

**PolyForm Noncommercial 1.0.0.** Reading, modifying, redistributing and using the project are permitted for **research, study and teaching**. **Commercial use is prohibited.** All commercial rights are reserved to the author, who keeps the option of relicensing later.

The term "open source" in the sense of the Open Source Initiative does not apply, a field-of-use restriction being incompatible with criterion 6 of the OSI definition. The project therefore describes itself as **source-available** and as an **open research project**. See [ADR-0002](docs/adr/0002-noncommercial-licence.md).

## Sources and prior work

The project builds on a documented, sourced state of the art in [docs/00-ANALYSIS.md](docs/00-ANALYSIS.md) section 3: reference corpora (CMU, Balabit, SapiMouse, HMOG, Clarkson II), work on HID injection detection, literature on biometric fusion and sequential decision, overview of open and commercial UEBA tools, and standards ISO/IEC 19795, 24745, 30107 as well as NIST SP 800-63B.
