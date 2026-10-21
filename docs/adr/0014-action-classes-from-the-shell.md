# ADR-0014 - Action sensitivity from a shell hook that only sends classes

- **Status**: accepted
- **Date**: 2026-10

## Context

The malice policy (ADR-0011) turns unsanctioned automation from a tag into an alert only in a sensitive context, and that sensitivity has been a stub returning "low" since it was named (FR-47). Work package 9 needs a real source: command classes (C09) and elevation requests (C10), content-free. The recorder sees keys, not commands, and must not learn to reconstruct them; reading other processes' command lines would need far more than the `input` group.

## Decision

- A small bash hook, `contrib/shell/fidus-actions.bash`, sourced from my `~/.bashrc`, runs before each command line (through `PS0`). It classifies each simple command **inside my shell** into one of ten classes (read, files, vcs, network, package, containers, elevation, destructive, credentials, other) and appends only `time class` to `$XDG_RUNTIME_DIR/fidusachates/actions` (mode 0600, in RAM). The command name, its arguments and its paths never leave the shell. "Destructive" is decided from flags the hook reads and then forgets (recursive `rm`, `dd of=`, `find -delete`, forced push, hard reset...).
- The daemon tails that file, places each line on the recorder's monotonic clock, and attaches the actions to the window they fall in (up to two seconds after its last event, since a window closes after an idle gap). Elevation, destructive and credential actions make a window HIGH; network, package and container actions MEDIUM; the rest LOW.
- Only the sensitivity provider changed: `decide` and the engine are untouched (criterion 9.3). The offline replay keeps the stub, since a recorded trace carries no actions.
- The console shows the sensitivity and the classes that lifted it next to the reasons of a window.

## Consequences

- Any process running as me can append to the file. A forged line can only raise sensitivity, so it can cause a false alert on unsanctioned automation, never hide one.
- Only my interactive bash is seen. A takeover that runs commands in its own shell, a graphical elevation prompt, or zsh are not covered; the Identity and Attribution channels still see the input. A polkit and journal source for graphical elevation is the obvious next one.
- The classes are coarse on purpose: the table is short enough to read in the hook, and a wrong class costs a tag or an alert, not data.
