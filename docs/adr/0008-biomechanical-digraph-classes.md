# ADR-0008 - Biomechanical digraph classes as the default granularity

- **Status**: accepted, to be confirmed by measurement in work package 4
- **Date**: 2026-09
- **Supersedes**: [ADR-0005](0005-hashed-digraphs.md)

## Context

ADR-0005 kept per-digraph statistics under a hash salted with a value regenerated at every start. The design review (A4) showed it cannot work:

- A hash that changes every session cannot accumulate statistics across sessions. A stable one makes the rotation pointless. The ADR wrote around this instead of solving it.
- A table of per-hash counts is open to **frequency analysis**: the most frequent digraphs of a language are well known and can be identified by rank, with no knowledge of the salt.

## Decision

Default level **P1**: each key pair is mapped, in memory, at capture time, to a **biomechanical class**, and only the class is kept.

| Class family | Examples |
|---|---|
| Hand relation | same hand, alternating hands |
| Finger relation | same finger, adjacent fingers, distant fingers |
| Row movement | same row, one row up or down, two rows |
| Special | modifier involved, space involved, correction involved, repeated key |

`evdev` key codes identify **physical positions**, independent of the layout printed on the keys, which is exactly what a motor class needs.

Hashed digraphs remain as opt-in level **P1h**, with a per-installation secret held in the system keyring and an honest description of the frequency attack.

## Rationale

What makes a digraph latency personal is the motor pattern: how fast this hand alternates, how this person handles a same-finger jump. The letters are incidental. About twenty motor classes carry essentially no information about what was typed, need no salt, and accumulate across sessions without any reconciliation step.

It is also a better fit for short windows: twenty classes fill up with observations quickly, where several hundred digraphs mostly stay empty over 60 seconds.

## Consequences

- Some discriminating power is certainly lost against true digraphs. How much is an **open question**, to be measured on a public corpus where key identity is available (roadmap 4.2). If the loss is too large, this decision is reopened.
- The class table is part of the privacy boundary: it lives in `fidus-core`, is unit-tested, and the record type written to disk has no field able to hold a keycode.
- The "content-free" test gets stronger. It is no longer a search for canary words but a **property**: two different texts with the same class structure and the same timings must produce byte-identical output.
