# ADR-0012 - Shortcuts are recorded as classes, never as keys

- **Status**: accepted
- **Date**: 2026-10

## Context

Which shortcuts I use, and how often, is a habit (catalogue A16): Ctrl+Z against the Edit menu, Ctrl+Shift+T to bring a tab back, Super+Tab against Alt+Tab. It is worth measuring. But the recorder's guarantee is structural: a `Record` has no field able to hold a key code (FR-3), so a shortcut cannot be stored as "Ctrl + the key at position 44".

Two facts shape the answer:

- Key codes are positional and shortcuts are bound to keysyms. On AZERTY, Undo is Ctrl plus the key at QWERTY's W position. A shortcut cannot be named without the layout.
- On AZERTY, AltGr (right Alt) types characters (`@`, `#`, `{`). Counting it as a shortcut modifier would turn ordinary typing into "shortcuts" and, worse, into a channel that says which character was typed.

## Decision

The reducer keeps the held state of Shift, Ctrl, left Alt and Super (booleans only) and, on a key-down while Ctrl, left Alt or Super is held, maps the combination to one of 27 **shortcut classes** (copy, paste, undo, switch application, close tab, word move...), anything not in the list being `Other`. The class is the only thing that leaves the reducer; it rides in a spare byte of the key-down record, so older traces stay valid.

- The layout is a recorder argument (`--layout qwerty|azerty`), set at install from the GNOME input sources.
- Right Alt never counts. Shift alone never makes a shortcut; it only qualifies one (Ctrl+Shift+T).
- The list is closed and coarse on purpose: a class says what the combination does, never which key it was.

## Consequences

- A16 is measurable with the content-free guarantee intact: a property test sweeps every key code under both layouts and checks the record carries only classes.
- A mislabelled layout gives wrong names, not leaked content: the classes would still be consistent per person, only their labels would be off.
- Shortcuts typed through a remapper or a virtual keyboard are classed like any other key-down, and their provenance is still flagged by the Attribution channel.
