#!/bin/sh
# Install the live path for the current user on macOS. Mirrors install-user.sh.
#
# STATUS (WP10, see docs/11-PORTING-WINDOWS-MACOS.md): the macOS capture Source
# (CGEventTap) and the menu-bar indicator are not finished yet. This script
# installs everything that is ready, builds the recorder if it can, and prints
# the steps that need a real Mac. Finish it on a Mac.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

PY=$(command -v python3 || true)
[ -n "$PY" ] || { echo "install-macos: python3 not found" >&2; exit 1; }

# Layout decides which key a letter shortcut is on (ADR-0012). Default qwerty;
# override with: LAYOUT=azerty ./scripts/install-macos.sh
LAYOUT=${LAYOUT:-qwerty}

# Build the recorder natively. This fails until the macOS capture Source lands
# (the agent is evdev-only today), so the failure is expected and not fatal here.
if command -v cargo >/dev/null 2>&1; then
	echo "building the recorder (expected to fail until the macOS capture lands, WP10)..."
	if cargo build --release --features research-trace; then
		install -d "$HOME/.local/bin"
		install -m 0755 target/release/fidus-agent "$HOME/.local/bin/fidus-agent"
		echo "recorder installed in ~/.local/bin"
	else
		echo "recorder build failed (expected until WP10 macOS capture)." >&2
	fi
else
	echo "install-macos: cargo not found; install Rust (https://rustup.rs) to build the recorder." >&2
fi

# The menu-bar indicator (crates/fidus-tray) is not built here yet; see docs/11.

# launchd user agent: runs the daemon at login.
PLIST="$HOME/Library/LaunchAgents/io.github.socold.fidusachates.plist"
mkdir -p "$(dirname "$PLIST")"
sed -e "s|@PY@|$PY|" \
    -e "s|@AGENT@|$HOME/.local/bin/fidus-agent|" \
    -e "s|@LAYOUT@|$LAYOUT|" \
    -e "s|@LAB@|$ROOT/lab|" \
    contrib/launchd/io.github.socold.fidusachates.plist.in > "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST" 2>/dev/null || true
echo "installed the launchd agent (layout $LAYOUT)."

cat <<EOF

ONE MANUAL STEP, required on macOS:
  Grant Input Monitoring to the recorder:
    System Settings > Privacy & Security > Input Monitoring > enable fidus-agent
  macOS prompts the first time it reads input; until then no events arrive.

NOT YET FINISHED (WP10, docs/11-PORTING-WINDOWS-MACOS.md):
  - the macOS capture Source (CGEventTap) in fidus-agent
  - the menu-bar indicator (crates/fidus-tray)

Stop everything with: launchctl unload "$PLIST"
EOF
