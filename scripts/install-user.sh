#!/bin/sh
# Install the live path for the current user, no root needed:
#   - the recorder (research-trace build, built in a container) in ~/.local/bin
#   - the GNOME Shell extension
#   - the systemd user service that runs the daemon at login
# Requires membership of the 'input' group (see docs/adr/0009).
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

if ! id -nG | tr ' ' '\n' | grep -qx input; then
    echo "install-user: you are not in the 'input' group; the recorder could not read devices" >&2
    exit 1
fi

# The layout decides which key a letter shortcut is on (ADR-0012).
LAYOUT=qwerty
if gsettings get org.gnome.desktop.input-sources sources 2>/dev/null | grep -q "'fr"; then
    LAYOUT=azerty
fi

echo "building the recorder (research-trace)..."
docker run --rm --network=none --user "$(id -u):$(id -g)" -e CARGO_HOME=/w/.cache/cargo \
    -v "$ROOT":/w:z -w /w rust:1-slim \
    cargo build --release --offline --features research-trace --target-dir /w/.cache/target
install -D -m 0755 .cache/target/release/fidus-agent "$HOME/.local/bin/fidus-agent"

EXT=fidusachates@socold.github.io
DEST="$HOME/.local/share/gnome-shell/extensions/$EXT"
mkdir -p "$DEST"
cp shell-extension/$EXT/* "$DEST/"

UNIT="$HOME/.config/systemd/user/fidusachates.service"
mkdir -p "$(dirname "$UNIT")"
sed -e "s|@LAB@|$ROOT/lab|" -e "s|@LAYOUT@|$LAYOUT|" \
    contrib/systemd/fidusachates.service.in > "$UNIT"
systemctl --user daemon-reload
systemctl --user enable --now fidusachates.service

echo "installed: recorder, extension, service (layout $LAYOUT)."
echo "a new or updated extension is picked up after logging out and back in on Wayland."
echo "stop everything with: systemctl --user disable --now fidusachates.service"
