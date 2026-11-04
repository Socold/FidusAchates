# fidus-tray

The FidusAchates indicator for **Windows** (notification area) and **macOS**
(menu bar). On Linux the GNOME Shell extension in `shell-extension/` already
provides the indicator; this crate is the cross-platform equivalent for the other
two systems, built with `tray-icon`, which covers both.

It is a **viewer over the daemon**, like the GNOME extension: it shows the state,
offers the Monitoring switch, and opens the console. It reads no input, holds no
biometric data, and uses no network.

## Status

Reference skeleton (WP10, see [../../docs/11-PORTING-WINDOWS-MACOS.md](../../docs/11-PORTING-WINDOWS-MACOS.md)).
It is excluded from the root workspace so the offline Linux recorder build stays
dependency-free. Finish and build it on each target.

## Build (on the target)

```sh
cd crates/fidus-tray
cargo add tray-icon muda tao   # pin the current versions Cargo can fetch
cargo build --release
```

The installers reference it: `scripts/install-windows.ps1` and
`scripts/install-macos.sh` note where it belongs once built.

## The daemon contract

The indicator and the daemon talk through three files in the runtime directory
(`$XDG_RUNTIME_DIR/fidusachates` on Linux and macOS, `%LOCALAPPDATA%\FidusAchates`
on Windows):

| File | Written by | Meaning |
|---|---|---|
| `state` | daemon | one word: `calm`, `watching`, or `alarm` |
| `console-link` | daemon | the one-time console URL (already exists today) |
| `control` | indicator | `pause` or `resume` for the Monitoring switch |

`console-link` already exists. `state` and `control` are the small addition the
daemon needs for this indicator; the GNOME path uses D-Bus for the same purpose.
Implement them in `lab/fidus_lab/daemon.py` next to the existing console-link
publishing and the Monitoring handling, so all three indicators share one
behaviour.

## What it must not become

A viewer, never a second recorder. It must not read input, must not persist
anything, and must not open the network. Measure its footprint against NFR-1 to
NFR-4, as the agent is measured.
