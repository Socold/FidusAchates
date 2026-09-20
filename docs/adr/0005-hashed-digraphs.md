# ADR-0005 - Salted hashed digraphs as the default trade-off

- **Status**: accepted
- **Date**: 2024-11, decision taken 2022-06

## Context

Per-digraph latencies are among the most discriminating signals in keystroke dynamics. They presuppose knowing which keys were pressed. But keeping the identity of keys means building a keylogger, which PR-1 forbids.

## Options

1. **Key classes only**: no risk, but signal A05 is lost, one of the strongest.
2. **Keycodes in clear**: maximum performance, text reconstruction possible. Unacceptable in real use.
3. **Hashed digraphs with a volatile salt**: `HMAC(salt, code1 ‖ code2)` truncated to 32 bits, aggregated online.

## Decision

Option 3 by default (level P1), with option 1 available (P0) and option 2 reserved for dedicated test corpora (P2, permanent warning displayed).

The salt is regenerated at every agent start, kept **in memory only**, never written to disk.

## Rationale

The model needs statistics *per digraph*, not to know *which* digraph. Hashing keeps exactly the ability to group observations of the same key pair, while making the reverse dictionary unusable: with an unknown, non-persisted salt, a dictionary attack on what is nevertheless a small space (a few thousand plausible pairs) cannot be mounted offline from the database alone.

## Consequences

- **Rotating the salt breaks the continuity of per-digraph statistics from one session to the next.** The agent therefore keeps a lookup table in memory for the current session, and persists only aggregates that have already been reconciled. This is a real complexity to implement in work package 1.
- An attacker with access to the memory of the running process can recover the salt. This protection targets leakage of the database at rest, not an adversary who already controls the process.
- Truncation to 32 bits causes collisions. Over a few thousand digraphs actually observed, their effect on the statistics is negligible, but it must be **measured** in work package 3 and not assumed.
- Level P2 must never become the default, through oversight or development convenience. A configuration test checks this.
