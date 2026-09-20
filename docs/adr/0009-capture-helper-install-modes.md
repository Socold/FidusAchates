# ADR-0009 - Two installation modes: `input` group or dedicated capture helper

- **Status**: accepted
- **Date**: 2026-09
- **Amends**: [ADR-0006](0006-least-privilege-installation.md)

## Context

ADR-0006 adds the user to the `input` group and calls it the least privilege available. The design review (B1) found that it looked at the wrong thing. Group membership makes `/dev/input` readable by **every process running as that user**: a browser exploit, a malicious package script, anything. The default model gives device access to the compositor alone. I was removing a system-wide protection against keyloggers in order to install a security tool.

ADR-0006 dismissed the alternative because "the created group would have exactly the same rights". The rights are the same; **the holder is not**.

The review also noted (A6) that network isolation rested on a unit-file directive that is not available everywhere.

## Decision

Two installation modes.

**Simple.** The user joins the `input` group. One privileged command, reversible. Documented as acceptable on a personal research machine, with the exposure stated before installation.

**Hardened**, recommended everywhere else. A minimal **capture helper** runs as a system service under a dedicated unprivileged account that is the only member of the device group. It opens the devices, reduces events to classes and timings, and forwards them over a UNIX socket after checking the peer's credentials. The user never joins `input`; no other process of the session gains anything.

In both modes, network isolation is **self-applied**: `no_new_privs`, a seccomp filter denying network sockets, and a start-up self-test that refuses to run if a network socket can be opened. `PrivateNetwork=yes` remains as a second layer.

## Rationale

The helper is the recorder's capture stage and nothing else, so it costs little code, and it is the part that would have to be audited in any case. Privacy reduction happens inside it: what crosses the socket already contains no keycode.

On my own machine the account was already in `input`, so simple mode adds no exposure there. That is a fact about one machine, and the reason I did not see the problem sooner.

## Consequences

- INS-12 is rewritten: hardened mode installs exactly one system service.
- Hardened mode needs root once, at installation, and an uninstaller that removes the account and the unit.
- The helper and the agent share the capture code; the helper is built from the same crate with a different entry point. Work package 7.
- The installer must explain the difference in plain language **before** asking anything (INS-16).
