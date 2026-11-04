# ADR-0015 - Signing releases and verifying legitimacy, in the open

- **Status**: proposed
- **Date**: 2026-11

## Context

FidusAchates reads `/dev/input` and so has the capabilities of a keylogger. The
whole project rests on being trusted, and trust needs a way to check, not a
promise. A user, an administrator, or a security tool acting for them must be able
to answer one question with certainty: *is this binary the genuine FidusAchates,
or a fork, a tampered build, or something wearing the name?*

This is the opposite of hiding. The project refuses to evade EDR or antivirus
(see [docs/10-SECURITY-REVIEW.md](../10-SECURITY-REVIEW.md) section 8); the way a
tool with dangerous power earns its place on a machine is by being **identifiable
and verifiable**, so it can be allowlisted by identity rather than guessed at.

Two properties are wanted, and they are not the same:

1. **The distributed file is genuine.** The archive or binary that was downloaded
   is bit-for-bit what the project released.
2. **The release is publicly accountable.** The fact that this exact artifact was
   published, and when, is recorded somewhere append-only, so a swapped file
   cannot be passed off as having "always been the release" and a verifier can
   check it online if it wants to.

A third property, that the **running process** is unmodified, is not in reach of a
file signature and is dealt with separately (OS code signing, WP10).

## Decision

Three layers, each with a stated limit. The agent itself stays offline; only
verification may reach the network, and only when asked.

### Layer 1 - Offline signature on every artifact (baseline)

Every released artifact is signed with a detached Ed25519 signature, using
`minisign` (small, single-key, no PKI, verifiable offline). The project publishes
one public key, in the repository and in the release notes. `scripts/verify-release.sh`
verifies an artifact against that key with no network access.

- **Proves**: the file is exactly what the holder of the project signing key
  released.
- **Does not prove**: that the signing key has not itself been compromised, nor
  anything about the running process. Key custody is addressed below.
- **Signing key custody**: generated and kept offline, never in the repository,
  never on CI. Releases are signed on a machine that is not the build server. The
  public key is the only half that ships.

### Layer 2 - Public transparency for online checking (optional, network)

In addition, the hash and signature of each release are recorded in a public
append-only log, so the claim "this artifact was published by the project on this
date" can be verified **online** and cannot be rewritten after the fact. Two ways,
in order of preference:

- **Sigstore (cosign + the Rekor transparency log)**: sign in CI with a workflow
  identity, and the signature is entered in a public log anyone can query. A
  verifier with network access confirms both the signature and its log entry. This
  is the "verify online that it is legitimate" path the project wanted to study.
- **A plain signed manifest** in the repository (`SHA256SUMS` plus its minisign
  signature), as the minimum that works with no third party.

- **Proves**: the artifact was published by the project and has an auditable,
  timestamped record; a later swap is detectable.
- **Does not prove**: more than layer 1 about the running process. It adds
  accountability, not runtime integrity.
- **Note**: this is the one place the project touches the network, and only in the
  verifier and the release workflow, never in the agent.

### Layer 3 - OS code signing for runtime legitimacy (with WP10)

On the platforms that support it, the installed program is signed so the operating
system vouches for it at launch: Authenticode on Windows, Developer ID plus
notarization on macOS. This is what lets EDR and antivirus recognise the publisher
instead of flagging a behavioural tool as malware, and it is the closest thing to
"this *process* is the genuine tool". It is tracked with the porting work
([docs/11-PORTING-WINDOWS-MACOS.md](../11-PORTING-WINDOWS-MACOS.md)); on Linux it
is left to the distribution packager.

## What a verifier should state, and never overstate

`verify-release.sh` prints exactly what it checked. The honest claims are:

- "This file matches the project signature" (layer 1), and if asked,
- "and its publication is recorded in the transparency log" (layer 2).

It must never print or imply "this machine is clean" or "the running tool is
unmodified". A signature is about a file; runtime integrity is a different problem
with a different, OS-level answer.

## Consequences

- Releases gain a one-line verification anyone can run offline, and an online
  audit trail for those who want it. The tool becomes allowlistable by identity,
  which is the point.
- The project takes on key custody: an offline signing key, a published public
  key, and a rotation procedure (publish the new key signed by the old, overlap
  one release). Losing the key means a key rotation, not a silent re-sign.
- CI learns to produce `SHA256SUMS` and signatures as release assets. The signing
  secret for layer 1 never enters CI; layer 2's Sigstore identity is CI-scoped and
  holds no long-lived secret.
- None of this changes the agent. It stays offline and unaware of any of it; a
  user who never verifies loses nothing they had before, and a user who does gains
  a real check.
