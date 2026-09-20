# ADR-0001 - Rust for the agent, Python for the offline lab

- **Status**: accepted
- **Date**: 2024-11

## Context

The dominant requirement is NFR-1 to NFR-4: under 1 % CPU, under 40 MB resident memory, latency under 250 ms, for a process that runs permanently and handles every input event. In parallel, research on the models calls for a fast iteration loop, which Rust does not give.

## Options

1. **All Python**: fast iteration, complete scientific ecosystem, but the memory footprint of an interpreter plus NumPy is incompatible with NFR-2, and latency is unpredictable because of the garbage collector.
2. **All Rust**: meets the NFRs, but experimenting on models is slow and painful.
3. **All Go**: a good compromise, but garbage collector and footprint above Rust, and less direct `evdev` access.
4. **Rust for the agent, Python for the offline lab.**

## Decision

Option 4.

The agent (`fidus-agent`) is written in Rust: single binary, no garbage collector, predictable footprint, direct `evdev` access, simple `systemd` hardening.

The lab (`fidus-lab`) is written in Python and **never runs continuously**. It works on frozen traces exported by the agent. The boundary between the two is the **trace format**, documented and versioned (FR-70).

## Consequences

- A model validated in `fidus-lab` has to be **ported** into the agent, which is a real and recurring cost.
- That cost is accepted, and it is softened by the deterministic replay requirement (FR-71): the port is verified by comparing the agent's output and the lab's on the same trace. Any divergence is a defect.
- Rust is not installed on the test machine. It is a prerequisite of work package 1.
