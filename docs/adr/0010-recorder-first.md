# ADR-0010 - Recorder first, signals in Python, reduced research trace

- **Status**: accepted
- **Date**: 2026-09
- **Amends**: [ADR-0001](0001-agent-language-rust.md)

## Context

ADR-0001 put the whole pipeline in Rust from the first work package. But which signals deserve to exist is the **output** of the signal study. Implementing, testing and optimising about a hundred extractors in Rust, to discard most of them, is the expensive order (design review B2).

The review also exposed a contradiction between two requirements. FR-8 forbade persisting events; FR-71 demanded replay. Replaying stored window vectors can re-run the fusion, but it cannot evaluate a **new signal**, which needs the events it would have been computed from.

## Decision

1. The Rust agent starts as a **recorder**: capture, privacy reduction, self-confinement, trace writing. Nothing else.
2. Feature extraction, experts, fusion and decision are built and measured **in Python**, offline, on recorded traces and public corpora.
3. Only what measurement has kept, about fifteen signals and the engine, is ported to Rust (work package 7), and verified by replay: same trace, same decisions, or it is a defect.
4. Persisting events is a **build-time feature**, `research-trace`, off by default and absent from release builds. It stores **reduced** events only: timestamp, event kind, key class, biomechanical class, pointer deltas, device index. Never a keycode.

## Rationale

The calendar is dominated by a 30-day legitimate-use trace. A recorder small enough to finish quickly lets that clock start on day one, while everything else is being built.

Keeping the component that reads `/dev/input` to a recorder also keeps it auditable: a few hundred lines, one dependency.

Making the trace a compile-time feature rather than a configuration switch means a release binary **does not contain** the code that writes events. That is a stronger statement than "it is disabled".

## Consequences

- FR-8 now applies to release builds, and the privacy register gains a line for the reduced trace, with its retention.
- The trace format becomes an interface between two languages. It is specified in `research/TRACE-FORMAT.md`, versioned, and the Rust writer and Python reader are tested against each other.
- Pointer deltas are recorded at full resolution. They reveal no content but are behavioural data in their own right, covered by the same qualification as the templates.
- The port in work package 7 is a real cost, accepted because it is spent only on what survived.
