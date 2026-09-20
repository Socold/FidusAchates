# ADR-0003 - evdev and a GNOME Shell extension under Wayland

- **Status**: accepted
- **Date**: 2024-11, decision taken 2021-03

## Context

Test machine: Fedora, GNOME, **Wayland** session. Wayland deliberately isolates applications from one another: none can observe input meant for the others, know the active window, or draw itself above everything.

Three needs run into that isolation: global input capture (FR-1), application context (FR-5) and the on-screen overlay (FR-60).

## Facts verified on the machine

- The user belongs to the `input` group, so `/dev/input/event*` is readable **without root**.
- No standard D-Bus interface exposes the active window under GNOME Wayland.
- `gtk-layer-shell` is not supported by Mutter: an ordinary window cannot be kept above everything.

## Decision

1. **Capture**: direct reading of `/dev/input/event*` through `evdev`, rootless, relying on membership of the `input` group.
2. **Context and overlay**: a minimal **GNOME Shell extension**, which publishes over D-Bus only the category of the focused application and draws the overlay. It is **required**, not optional.

## Consequences

- Membership of the `input` group becomes an installation prerequisite, checked by `fidus-cli doctor`.
- **Reading `/dev/input` grants the capabilities of a keylogger.** That requires: published sources, reproducible build, structural network isolation of the capture process (`PrivateNetwork=yes`), and up-front documentation of that power in the README.
- The GNOME Shell extension is the most privileged component on the interface side. It must stay short enough to be audited in one sitting, and never expose a window title or an executable name.
- `evdev` has no notion of an input field: **detecting password fields is impossible**. Imperfectly compensated by the application blocklist (FR-6) and manual suspension (FR-7). A documented limit, not a hidden one.
- Porting to X11, Windows and macOS only touches the `Source` stage of the agent.
