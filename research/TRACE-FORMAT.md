# Reduced trace format

Version 1 (`FIDUSTR\x01`).

The trace is the interface between the Rust recorder and the Python lab
(ADR-0010). It is written only by builds with the `research-trace` feature, and
it contains **no key code and no character**: it can be decoded back to classes,
pointer deltas and timings, and to nothing else.

## Layout

```
magic:   8 bytes   "FIDUSTR" 0x01
records: N * 16 bytes
```

No header beyond the magic, no index, no trailer: the file is a flat stream of
fixed records, append-only, so a crash loses at most the last record.

## Record (16 bytes, little-endian)

| Offset | Size | Field | Meaning |
|---|---|---|---|
| 0 | 8 | `time` | monotonic microseconds since an arbitrary origin, never wall-clock |
| 8 | 2 | `device` | index into the session device table |
| 10 | 1 | `flags` | event kind in bits 0-6, provenance in bit 7 (1 = virtual) |
| 11 | 4 | `payload` | depends on the kind |
| 15 | 1 | padding | zero |

### Event kinds and payloads

| Kind | Value | Payload bytes |
|---|---|---|
| key down | 1 | `[key_class, digraph_class, 0, 0]` |
| key up | 2 | `[key_class, 0, 0, 0]` |
| motion | 3 | `[dx: i16, dy: i16]` |
| wheel | 4 | `[dx: i16, dy: i16]` (notches) |
| button down | 5 | `[button, 0, 0, 0]` |
| button up | 6 | `[button, 0, 0, 0]` |

`key_class` is one of the twelve values of `KeyClass` (letter, digit,
punctuation, space, enter, tab, correction, modifier, navigation, function,
keypad, other).

`digraph_class` packs the biomechanical relation (bits 0-2) and the row
distance (bits 3-4): see `fidus-core::biomech`. It is meaningful on key-down
only.

`button` is 0 left, 1 right, 2 middle, 3 other.

## What cannot be recovered

The exact key, hence the text; the wall-clock time; the window or application;
the pointer's absolute position (only relative deltas are stored). Pointer
deltas and typing rhythm are behavioural data, covered by the same biometric
qualification as the templates (see 05-PRIVACY.md).
