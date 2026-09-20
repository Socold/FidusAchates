# 02 - Technical architecture

> Follows from [00-ANALYSIS.md](00-ANALYSIS.md) and [01-REQUIREMENTS.md](01-REQUIREMENTS.md).

---

## 1. Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  USER MACHINE (no outbound network)                                  │
│                                                                      │
│  /dev/input/event*                                                   │
│         │ evdev (input group, no root)                               │
│         ▼                                                            │
│  ┌──────────────────┐   D-Bus    ┌─────────────────────────────┐     │
│  │  fidus-agent     │◄──────────►│  fidus-shell-ext            │     │
│  │  (Rust)          │            │  (GNOME Shell, JS)          │     │
│  │                  │            │                             │     │
│  │ 1. Capture       │  context   │  • focused app category     │     │
│  │ 2. Hot buffer    │◄───────────│  • red square overlay       │     │
│  │ 3. Extraction    │  overlay   │  • locked / idle state      │     │
│  │ 4. Experts       │───────────►│                             │     │
│  │ 5. LLR fusion    │            └─────────────────────────────┘     │
│  │ 6. SPRT          │                                                │
│  │ 7. Profiles      │                                                │
│  └────────┬─────────┘                                                │
│           │ UNIX socket (0600)                                       │
│     ┌─────┴──────┬───────────────┐                                   │
│     ▼            ▼               ▼                                   │
│ ┌────────┐  ┌──────────┐  ┌────────────┐                             │
│ │ SQLite │  │ fidus-   │  │ fidus-cli  │                             │
│ │ (WAL,  │  │ console  │  │            │                             │
│ │ encryp-│  │ 127.0.0.1│  │ pause      │                             │
│ │ ted)   │  │ + token  │  │ purge      │                             │
│ └───┬────┘  │ SSE      │  │ export     │                             │
│     │       └──────────┘  └────────────┘                             │
│     │ trace export (signals, never content)                          │
│     ▼                                                                │
│ ┌──────────────────────────────────────────┐                         │
│ │ fidus-lab (offline, Python)              │                         │
│ │ deterministic replay, evaluation bench,  │                         │
│ │ public corpora, DET/ROC curves           │                         │
│ └──────────────────────────────────────────┘                         │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Components

### 2.1 `fidus-agent` (Rust)

The heart of the system. A single process, no root, started by a `systemd --user` unit.

**Why Rust**: the dominant requirement is NFR-1 to NFR-4 (under 1 % CPU, under 40 MB, latency under 250 ms) for a process that runs permanently. No garbage collector, predictable memory footprint, direct `evdev` access, and compilation to a single binary with no run-time dependency. See [ADR-0001](adr/0001-agent-language-rust.md).

Internally organised in stages, each isolated behind a trait:

| Stage | Role | Trait |
|---|---|---|
| 1. Capture | `evdev` reading, normalisation, provenance tagging | `Source` |
| 2. Hot buffer | In-memory ring, 10 s at most, never persisted | |
| 3. Extraction | Streaming signal computation, Welford aggregates | `Extractor` |
| 4. Experts | One calibrated score per modality | `Expert` |
| 5. Fusion | Weighted sum of LLRs | |
| 6. Decision | SPRT, hysteresis, levels | |
| 7. Profiles | Online clustering, revisions | |

A new expert is added by implementing `Expert` and registering it: the core is not modified (FR-12).

### 2.2 `fidus-shell-ext` (GNOME Shell extension, JavaScript)

A **required** component, not an optional one, for two reasons established in the analysis (T4): under GNOME Wayland, neither the active-window context nor a permanent overlay is reachable from an ordinary process.

Two functions, and nothing else:

1. **Context**: publishes on D-Bus the **category** of the foreground application and a stable opaque identifier, never the title nor the binary name (FR-5).
2. **Overlay**: shows the red square at the top right, without focus and without intercepting events (FR-60 to FR-62).

The extension is deliberately tiny and readable in one sitting: it is the most privileged component in the chain on the interface side, it must be auditable in a few minutes.

### 2.3 `fidus-console` (local server plus web interface)

HTTP server embedded in the agent or a separate light process, bound to `127.0.0.1`, protected by a token regenerated at every start (SR-2).

Real-time delivery through **Server-Sent Events** rather than WebSocket: the stream is one-way, SSE reconnects by itself, and it costs less (NFR-5).

Interface with no heavy framework, no CDN, no remote font. Target: under 300 KB transferred (NFR-7). Charts in SVG computed client-side from the stream, no bulky charting library.

### 2.4 `fidus-cli`

Commands: `status`, `pause`, `resume`, `purge`, `export`, `profiles`, `doctor` (prerequisite diagnostics: `input` group, extension installed, Wayland session).

### 2.5 `fidus-lab` (Python, offline only)

Separate from the agent, never run continuously. Deterministic trace replay (FR-71), evaluation bench (FR-72), ingestion of public corpora (FR-73), curve production.

This decoupling is a structuring choice: **model experimentation happens offline, in Python, on frozen traces**, and the retained model is then ported into the agent. This avoids weighing the agent down with a learning environment while keeping a fast research loop.

## 3. Storage

**SQLite in WAL mode**, a single file, encrypted at rest (PR-4).

Schema in strata of decreasing retention:

| Table | Content | Retention |
|---|---|---|
| `window_vectors` | Signal vectors per activity window | 7 days |
| `aggregates` | Incremental aggregates per profile, mode and signal (n, mean, M2, approximate quantiles) | 90 days |
| `templates` | Templates: frozen anchor and current version | Lifetime of the profile |
| `decisions` | Decision events with contribution vector | 90 days |
| `profile_revisions` | History of merges and splits with statistical justification | Permanent (negligible volume) |
| `health` | Resource metrics | 7 days |

**No raw-event table.** This is a property of the schema, not a purge policy: what does not exist cannot leak.

Quantiles are maintained with a t-digest or a P² estimator so as to stay in bounded memory (NFR-2, NFR-3).

## 4. Data flow

```
evdev ──► normalisation ──► hot buffer (10 s)
                                 │
                 ┌───────────────┼───────────────┬──────────────┐
                 ▼               ▼               ▼              ▼
          Typing expert    Mouse expert   Context expert  Automation expert
                 │               │               │              │
            calibrated      calibrated      calibrated     calibrated
              score           score           score          score
                 │               │               │              │
                 └──► LLR ◄──────┴───────────────┴──────────────┘
                        │  weighting by quality and reliability
                        ▼
                   Σ weighted LLRs  ──► SPRT (2 thresholds, decay)
                        │                       │
                        ▼                       ▼
                 contributions (dB)       level L0..L4
                        │                       │
                        └────► console ◄────────┘
                                  └──► overlay if P(impostor) > 0.50
```

## 5. Portability

Stage 1 (`Source`) is the only system-specific one. The rest is portable as is.

| Target | Capture | Application context | Overlay | WP |
|---|---|---|---|---|
| Linux Wayland (GNOME) | `evdev` | GNOME Shell extension | GNOME Shell extension | 1 to 6 |
| Linux X11 | `evdev` or XInput2 | XLib | `override-redirect` window | 8 |
| Windows | low-level `SetWindowsHookEx` or Raw Input | Win32 | layered window | 8 |
| macOS | `CGEventTap` (accessibility permission required) | Accessibility API | screen-level `NSWindow` | 8 |
| Android and iOS | in-app SDK only (cf. T6) | inside the application | inside the application | 9 |

On Windows, detecting synthetic provenance is made easier by the `LLKHF_INJECTED` flag; on Linux, by identifying the `uinput` device. Both feed the same signal.

## 6. Deployment on the test machine

- Hardened `systemd --user` unit: `NoNewPrivileges`, `PrivateNetwork=yes` for the capture process, `ProtectSystem=strict`, `ProtectHome=read-only` outside the data directory, `SystemCallFilter=@system-service`, `MemoryMax` aligned on NFR-2 (SR-3).
- `PrivateNetwork=yes` on the capture process makes NFR-9 structural: **it cannot exfiltrate, even if compromised**.
- Data in `~/.local/share/fidusachates/`, configuration in `~/.config/fidusachates/`.
- GNOME Shell extension installed by script, enabled explicitly by the user.

## 7. Execution model and footprint

The tool is meant to run permanently in the background. Its real cost is therefore not measured under load but **at rest**, the state in which it spends almost all of its time.

| Component | At rest | Active |
|---|---|---|
| `fidus-agent` | Blocked on `epoll`, 0 % CPU, no wake-up | Under 1 % on average (NFR-1) |
| `fidus-shell-ext` | Reacts to a focus-change signal the Shell already emits | Negligible |
| `fidus-console` | **Does not exist**: started by socket activation on first access | Under 2 % (NFR-5) |
| `fidus-lab` | Does not exist: run on demand, offline | |

Design consequences, not to be lost sight of across work packages:

- **No polling loop, anywhere.** A timer, even a slow one, keeps the processor out of its deep sleep states and is paid for in battery life on a laptop (INS-1, INS-4).
- **Maintenance is triggered by event thresholds**, never by the clock, capped at one run every 5 minutes (INS-3).
- **The agent reads in parallel with the display server, it does not sit in the input path.** It can therefore neither block nor slow down input, even if it crashes. This property is structural and must be preserved by every change.
- **The GNOME Shell extension is optional at start-up**: without it the agent runs in degraded mode (signal family C and the overlay are lost, the latter replaced by a desktop notification). Installation must never fail for lack of the extension (INS-25).

Permissions, in full:

| Permission | When | Revocation |
|---|---|---|
| Membership of the `input` group | Once, at installation | `sudo gpasswd -d $USER input` |

No other, at any time: no root at run time, no setuid, no capability, no kernel module, no system service, no network access, no accessibility permission. See [ADR-0006](adr/0006-least-privilege-installation.md).

## 8. Architecture decisions

| ADR | Subject |
|---|---|
| [0001](adr/0001-agent-language-rust.md) | Rust for the agent, Python for the offline lab |
| [0002](adr/0002-noncommercial-licence.md) | PolyForm Noncommercial rather than an OSI licence |
| [0003](adr/0003-evdev-and-gnome-extension.md) | evdev plus GNOME Shell extension under Wayland |
| [0004](adr/0004-fusion-llr-sprt.md) | LLR fusion and Wald sequential decision |
| [0005](adr/0005-hashed-digraphs.md) | Salted hashed digraphs as the default trade-off |
| [0006](adr/0006-least-privilege-installation.md) | Least privilege, rootless installation, event-driven execution |
