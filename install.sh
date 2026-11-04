#!/bin/sh
# One entry point for every system. Detects the OS and runs the matching
# installer, then opens the onboarding page once, on first install.
#
#   ./install.sh
#
# Windows is not covered here (no POSIX shell): run, in PowerShell,
#   scripts\install-windows.ps1
set -eu

ROOT=$(cd "$(dirname "$0")" && pwd)
OS=$(uname -s 2>/dev/null || echo unknown)

DATA="${XDG_DATA_HOME:-$HOME/.local/share}/fidusachates"
ONBOARD="$ROOT/contrib/onboarding/onboarding.html"

# Open the onboarding page once, the first time the tool is installed. The
# marker lives next to the data, so a reinstall does not reopen it.
open_onboarding() {
	marker="$DATA/.onboarded"
	[ -f "$marker" ] && return 0
	mkdir -p "$DATA"
	case "$1" in
		Linux)  command -v xdg-open >/dev/null 2>&1 && xdg-open "$ONBOARD" >/dev/null 2>&1 || true ;;
		Darwin) open "$ONBOARD" >/dev/null 2>&1 || true ;;
	esac
	: > "$marker"
	echo "opened the onboarding page ($ONBOARD)"
}

case "$OS" in
	Linux)
		echo "detected Linux; installing the user (GNOME) path."
		sh "$ROOT/scripts/install-user.sh"
		open_onboarding Linux
		;;
	Darwin)
		echo "detected macOS; installing the user path."
		sh "$ROOT/scripts/install-macos.sh"
		open_onboarding Darwin
		;;
	*)
		echo "install: unrecognised system '$OS'." >&2
		echo "On Windows, run in PowerShell:  scripts\\install-windows.ps1" >&2
		exit 1
		;;
esac
