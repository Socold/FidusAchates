# 11 - Porting to Windows and macOS (WP10)

> Written on 2026-11-04. This is the design that unblocks the port, not a report
> that it works. I build and measure on Linux; I cannot validate Windows or macOS
> capture from here, so every per-platform claim below is a plan with an
> acceptance test, and the status of each stays "to do" until it is met on real
> hardware. The acceptance criterion for the whole package is unchanged from
> [06-ROADMAP.md](06-ROADMAP.md): on each platform the WP1 criteria are met, and a
> trace captured there replays in `fidus-lab` without adaptation.

---

## 1. What ports and what does not

Only the **capture stage** is platform-specific. Everything downstream is already
platform-independent and must stay that way:

- `fidus-core` (event model, privacy reduction, trace format) has no I/O and is
  fully unit-tested. It does not change.
- The hot buffer, extraction, experts, fusion, decision and profiles are computed
  on the reduced event stream, not on raw OS events. They do not change.
- The lab reads the trace format, which is the contract. If a Windows or macOS
  capture emits the same `fidustr`, the entire engine and every result apply
  unchanged.

The seam is the `Source` trait ([02-ARCHITECTURE.md](02-ARCHITECTURE.md) section
2.1). A port is a new `Source` implementation that produces `Record`s, nothing
more. The rule that makes this safe: **the key code is mapped to a class and
dropped inside the platform layer**, before a `Record` exists, exactly as the
Linux `evdev` source does. No platform layer ever hands a key code upward.

## 2. Capture per platform

### Windows

- **API**: Raw Input (`RegisterRawInputDevices`, `WM_INPUT`) on a hidden
  message-only window. Keyboard gives virtual-key codes with make/break and a
  high-resolution timestamp; mouse gives relative motion for pointer deltas.
- **Why Raw Input, not a hook**: a global `WH_KEYBOARD_LL` hook is the classic
  keylogger shape, is heavier, and is more likely to be flagged. Raw Input needs
  no special privilege and no global hook, and still sees the timing the engine
  needs. Prefer it.
- **Mapping**: virtual-key code to `KeyClass`, compute hold and gap timings, then
  drop the code. Pointer deltas from `RAWMOUSE` relative movement.
- **Secure input**: input to the UAC secure desktop and the lock screen does not
  reach a normal-session Raw Input consumer, which gives the lock-screen and
  elevation drop for free rather than needing a filter. Password fields inside
  ordinary windows are unknowable, as under Wayland: same answer, the application
  blocklist and the manual Monitoring switch.

### macOS

- **API**: a listen-only `CGEventTap` (`kCGEventTapOptionListenOnly`) at the
  session level, for `keyDown`/`keyUp`/`flagsChanged` and mouse-moved events.
  Listen-only cannot modify or drop events into the system, which matches the
  "never coercive" rule (no locking, no blocking) by construction.
- **Permission**: the user must grant **Input Monitoring** (and, for some tap
  placements, Accessibility) through TCC, in System Settings, where the tool is
  listed by name and the grant is revocable. This is consent made explicit and
  visible, which is the posture the project wants, not an obstacle to work around.
- **Mapping**: keycode to `KeyClass`, compute timings, drop the code. Pointer
  deltas from `mouseMoved` deltaX/deltaY.
- **Secure input, a real privacy win**: when an application calls
  `EnableSecureEventInput` (password fields do), the OS stops delivering those
  keystrokes to event taps. Password entry is therefore invisible to the capture
  by the operating system's own design, a stronger guarantee than the Linux
  filter. Document it and rely on it; keep the filter as the fallback for the
  cases it does not cover.

## 3. Privacy reduction parity

The drop rules in `fidus-core` are platform-independent and reused as is. What is
platform-specific is *detecting the moments to drop*:

- Lock screen and elevation: free on Windows (secure desktop) and largely free on
  macOS (secure input mode), versus the explicit GNOME-signalled filter on Linux.
- Password fields in ordinary windows: unknowable on all three; the blocklist plus
  the manual switch is the answer everywhere.

Net effect: the two new platforms reduce *more* by default than Linux does, not
less. The content-free and lockdown tests
(`crates/fidus-agent/tests/content_free.rs`, `lockdown.rs`) must gain a
platform-tagged equivalent so the guarantee is enforced per OS, not assumed.

## 4. Self-confinement parity

The Linux agent denies itself network with a seccomp filter and proves the denial
at start-up. That exact trick does not port. The equivalent guarantees:

- **Windows**: run in a Job Object / restricted token; declare no network use and
  back it with a Windows Firewall rule in the installer; consider an AppContainer
  profile with no network capability. The structural "the process forbids itself
  sockets" property is weaker here and should be stated honestly rather than
  claimed as identical.
- **macOS**: the App Sandbox with the hardened runtime and **no** network
  entitlement. A sandboxed process without `com.apple.security.network.client`
  cannot open outbound sockets, which is close to the Linux property and is
  externally checkable in the signed entitlements.

Wherever the self-denial is weaker than on Linux, say so in `05-PRIVACY.md` per
platform; do not let the Linux guarantee stand in for the others.

## 5. Footprint parity

NFR-1 to NFR-4 (under 1 % CPU, under 40 MB, latency under 250 ms) apply unchanged.
Raw Input and `CGEventTap` are event-driven and cheap, and the hot buffer is the
same ring as on Linux, so the budget is realistic, but it is a claim until
measured on each platform with the same method as WP1.

## 6. Code signing and being allowlistable

A behavioural tool that is not signed will be flagged, and should be. The port is
not functional in the sense that matters until it is signed:

- **Windows**: Authenticode-sign the binary and installer.
- **macOS**: Developer ID signature plus notarization, with the hardened runtime
  and the Input Monitoring usage declared.

This is layer 3 of [ADR-0015](adr/0015-release-signing-and-verification.md): the OS
vouches for the publisher at launch, so EDR and antivirus recognise the tool
instead of guessing. It is the intended way to coexist with security software, and
it is the opposite of evasion.

## 7. Staged plan

Each step lands behind `#[cfg(target_os = ...)]` so Linux keeps building and
testing throughout.

1. **Extract the `Source` seam cleanly** (if not already isolated) and add a
   no-op platform stub per OS that compiles. *Acceptance: `cargo build` on each
   target; Linux tests unchanged.*
2. **Windows Raw Input keyboard capture** to `Record`s, code dropped in the layer.
   *Acceptance: a captured trace replays in `fidus-lab`; content-free test passes
   on Windows.*
3. **Windows pointer deltas**, then the footprint measurement. *Acceptance:
   NFR-1..4 on a real machine.*
4. **macOS `CGEventTap` keyboard capture**, same drop discipline. *Acceptance: as
   step 2, on macOS; confirm secure-input suppression empirically.*
5. **macOS pointer deltas and footprint.** *Acceptance: as step 3.*
6. **Signing and notarization** in the release flow (ADR-0015 layer 3).
   *Acceptance: the signed artifact launches without a publisher warning and is
   allowlistable by identity.*
7. **Per-platform privacy and confinement notes** added to `05-PRIVACY.md`, with
   the honest differences from Linux.

## 8. Status

In place in the repository:

- **OS-detecting install** (`install.sh`): runs the Linux installer on Linux, the
  macOS installer on Darwin, and points to the PowerShell installer on Windows.
- **macOS installer** (`scripts/install-macos.sh`) with a launchd user agent
  (`contrib/launchd/`), and **Windows installer** (`scripts/install-windows.ps1`)
  with a logon scheduled task. Both build the recorder if a toolchain is present
  (expected to fail until the capture Source below exists), set the daemon to run
  at login, and print the manual permission step.
- **First-install onboarding** (`contrib/onboarding/onboarding.html`), opened once
  by the installer on each platform.
- **Indicator** (`crates/fidus-tray/`): a cross-platform reference for the Windows
  notification area and the macOS menu bar, excluded from the offline workspace,
  with its daemon contract specified.

Not done, and needing the target hardware to write and validate:

1. **The capture Source per OS** in `fidus-agent` (Raw Input on Windows,
   `CGEventTap` on macOS), with the key code dropped inside the layer. This is the
   one piece that makes the recorder build and run off Linux. The agent is
   evdev-only today and has no `Source` trait yet; extracting that seam is the
   first coding task on the target.
2. **The `state` and `control` files** in `daemon.py` that the indicator reads and
   writes (section in `crates/fidus-tray/README.md`).
3. **Finishing the indicator** against `tray-icon`, and **signing/notarization**
   (ADR-0015 layer 3).

Everything in the first list is verifiable on Linux (shell syntax, HTML, valid
manifests); nothing in the second can be compiled or validated from a Linux host,
and it is left for a session on Windows and macOS rather than asserted from here.
