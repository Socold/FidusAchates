# ADR-0013 - A live daemon in the research build, before the Rust port

- **Status**: accepted
- **Date**: 2026-10

## Context

Until now the engine only replayed recorded traces, so nothing ran while I worked and the indicator only lit up in demonstrations. Choosing signals on real data (work package 4) and measuring how long the model needs to know me both need weeks of my own activity, scored as it happens. The production engine is the Rust port of work package 7, which waits for exactly those measurements.

## Decision

Run the research build live:

- The recorder (`research-trace` build) streams its reduced records to stdout, flushed after each batch; it stays the only process reading `/dev/input`, confined and without network.
- A Python daemon reads the stream, keeps one reduced trace per day and the focus categories from the shell extension, scores each window with the lab engine, and drives the console and the top-bar indicator. It refits the templates from the stored days (every five minutes while learning, every half hour after) and recomputes the learning curves every three hours or on request.
- A systemd user service starts it with the graphical session; one command stops and disables it.
- Retention is 30 days, applied daily, guest sessions included.
- The indicator shows "learning" until all four enrolment criteria are met; it never turns red on a model that is still learning.
- Guest sessions (someone else at my desk, with their logged consent) are stored apart, never enrol as me, and become the impostor population and the real detection numbers.

## Consequences

- Reduced traces now persist continuously on my machine, which the privacy register records: plain files readable by me only, in my data directory, deleted after 30 days. They hold no key code; they do hold my behavioural data and other people's for guest sessions.
- The Python daemon is not the footprint target (NFR-2): it is the measuring instrument. The footprint budget applies to the Rust agent of work package 7.
- Learning curves are only as honest as their impostors: without guest sessions they use impostors simulated from my own held-out data, and the console says so next to every number.
