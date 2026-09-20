# ADR-0011 - Attribution is a tag, malice is a separate judgment

- **Status**: accepted
- **Date**: 2026-09

## Context

The design so far had a "Humanity channel" whose job was to answer "is this a human?" and which, on a "no", concluded that a compromise had happened. That conflates two different things.

Non-human input is not the same as hostile input. Two everyday cases make this plain:

- A developer using an **AI coding assistant**. Some assistants insert text through the editor's API, which never reaches `/dev/input` and shows up only as phantom activity (E20); others, and computer-use agents, do drive the keyboard and mouse, which is genuine synthetic input.
- A user running **MCP tools** (Model Context Protocol) or any sanctioned automation, which executes actions on their behalf: bursts of activity, application switching, sometimes synthetic input, all of it wanted.

Treating either as an intrusion would make the tool cry wolf on exactly the people most likely to run it. Yet the same mechanisms are what a hostile agent or a RAT uses. The signal that tells human from automated is real and worth having; what is wrong is jumping from "automated" straight to "alarm".

## Decision

Split what was one question into an **attribution** (a fact) and a **risk judgment** (a policy).

**1. Attribution produces a label, not a verdict.** For each segment of activity the engine assigns an actor label:

| Label | Meaning |
|---|---|
| `human` | Behaviour consistent with a person typing and pointing |
| `automation_sanctioned` | Automation the user has declared or that matches a sanctioned actor |
| `automation_unsanctioned` | Automation with no matching sanction |
| `uncertain` | Not enough evidence yet |

The label is always computed, always logged, always shown in the console. By itself it never raises the overlay.

**2. A sanctioned-actor registry.** The user can declare expected automation, the way the virtual-device allowlist (FR-38) already handles benign `uinput` devices, but richer: by device name pattern, or by an explicit, time-boxed "agent session" the user opens when they hand control to an assistant. Anything matching is labelled `automation_sanctioned`.

**3. Malice is a policy over (label, identity, action sensitivity).** An alert is raised only when:

- the **Identity** channel diverges (someone else), regardless of human or automated; or
- input is `automation_unsanctioned` **and** the context is sensitive.

`automation_sanctioned` on its own is never an alert. `automation_unsanctioned` on its own is *noted* (a tag in the console, a log line), not alarmed, until it coincides with identity divergence or a sensitive action.

**4. Action sensitivity is the future link, and it is named now.** "Sensitive context" will be derived from the command-category signals already in the catalogue (C09 command classes, C10 elevation cadence) plus destructive-looking sequences. Unsanctioned automation that only reads and navigates is low concern; unsanctioned automation that elevates privileges, rotates credentials or mass-deletes is what should lift or keep doubt. This correlation is its own work package; today the hooks (the label, the registry, the policy seam) are put in place so it can be added without reshaping the engine.

## Rationale

The honest primitive is attribution. Whether automation is welcome is not something behaviour can decide on its own: the same keystrokes are a blessing or an attack depending on who set them off. So the system reports what it can know (human or not, sanctioned or not) and leaves the leap to malice to an explicit, inspectable policy that also weighs identity and what the action touches.

This also fixes an asymmetry the old design hid: an AI assistant that types through an editor API produces *less* input than a human, not more, and would have looked like an idle machine with a busy screen. That is now a first-class case (phantom activity, labelled, not alarmed), not an oversight.

## Consequences

- The "Humanity channel" keeps its detector (human vs automated) but its output feeds attribution instead of driving an alarm directly. Section 4.4 of the decision engine is rewritten around labels and a policy.
- New requirements: the registry (FR-39), the per-segment label and its display (FR-34 amended, FR-35 amended), and the policy that automation alone does not alarm (FR-35b).
- The console gains an actor tag on every segment and a way to sanction an actor after the fact ("this was my agent").
- A privacy note: labelling needs no content. It uses provenance, timing, phantom-activity, and the coarse application category already collected. Sanctioning an actor stores at most a device-name pattern or a session marker, never what the agent did.
- Until the command-correlation work package lands, `automation_unsanctioned` in a sensitive context falls back to being tagged and logged, not alarmed. The tool under-reacts rather than over-reacts, which is the right default for a research build that must not cry wolf.
