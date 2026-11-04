#!/bin/sh
# Verify that a FidusAchates release artifact is genuine (ADR-0015).
#
# Layer 1 (default, offline): check a detached minisign signature against the
# project public key. No network.
#
#   scripts/verify-release.sh fidusachates-<ver>.tar.gz
#   scripts/verify-release.sh fidusachates-<ver>.tar.gz fidusachates-<ver>.tar.gz.minisig
#
# Layer 2 (optional, network): also confirm the artifact is recorded in the
# public Sigstore transparency log, with --online.
#
#   scripts/verify-release.sh --online fidusachates-<ver>.tar.gz
#
# This script tells you whether the FILE is the genuine release. It says nothing
# about whether the running process on this machine is unmodified: that is a
# different problem with an OS-level answer (code signing, see ADR-0015 layer 3).
set -eu

# The project's minisign public key. Published here, in the release notes, and in
# the repository so the two can be compared. Signing key is kept offline and is
# NEVER in this repository. Replace the placeholder below with the real key once
# generated (minisign -G), and keep it identical across these locations.
PUBKEY='RWR_REPLACE_WITH_THE_REAL_MINISIGN_PUBLIC_KEY'

ONLINE=0
if [ "${1:-}" = "--online" ]; then
	ONLINE=1
	shift
fi

ARTIFACT="${1:-}"
SIG="${2:-${ARTIFACT}.minisig}"

die() { printf 'verify-release: %s\n' "$1" >&2; exit 2; }

[ -n "$ARTIFACT" ] || die "usage: verify-release.sh [--online] <artifact> [signature]"
[ -f "$ARTIFACT" ] || die "no such file: $ARTIFACT"
[ -f "$SIG" ] || die "signature not found: $SIG (pass it as the second argument)"

case "$PUBKEY" in
	RWR_REPLACE_*)
		die "no public key set in this script yet; see ADR-0015 and paste the real minisign key" ;;
esac

# --- Layer 1: offline signature ------------------------------------------------

command -v minisign >/dev/null 2>&1 || die "minisign is not installed (https://jedisct1.github.io/minisign/)"

printf 'Checking offline signature with the project key...\n'
if minisign -V -P "$PUBKEY" -m "$ARTIFACT" -x "$SIG"; then
	printf 'OK: %s matches the project signature.\n' "$ARTIFACT"
else
	die "SIGNATURE DOES NOT MATCH. Do not trust this file."
fi

# --- Layer 2: online transparency (optional) -----------------------------------

if [ "$ONLINE" -eq 1 ]; then
	if ! command -v cosign >/dev/null 2>&1; then
		die "--online needs cosign (https://docs.sigstore.dev); the offline check above already passed"
	fi
	printf 'Checking the public transparency log...\n'
	# The release publishes <artifact>.sigstore.json (a cosign bundle). Verify it
	# against the project's release workflow identity. Adjust the identity values
	# to the real ones when the signing workflow exists (ADR-0015 layer 2).
	BUNDLE="${ARTIFACT}.sigstore.json"
	[ -f "$BUNDLE" ] || die "no Sigstore bundle found: $BUNDLE"
	if cosign verify-blob \
		--bundle "$BUNDLE" \
		--certificate-identity-regexp '^https://github\.com/Socold/FidusAchates/' \
		--certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
		"$ARTIFACT"; then
		printf 'OK: publication is recorded in the public transparency log.\n'
	else
		die "transparency-log check failed"
	fi
fi

printf '\nVerified: this FILE is the genuine release.\n'
printf 'This does not prove the running process on a machine is unmodified.\n'
