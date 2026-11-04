# Seeing kloak, re-timing buffers, and a remote hop, on CMU

**What this is.** The follow-up to
[2026-11-04-kloak](../2026-11-04-kloak/README.md): whether kloak itself can be
detected, whether a buffer that re-times keys hides a typist and at what lag,
and what a remote-desktop hop does to the timing the recorder sees. Written up
in [research/articles/2026-11-04-hiding-for-real.md](../../articles/2026-11-04-hiding-for-real.md)
and [research/articles/2026-11-04-remote-hand.md](../../articles/2026-11-04-remote-hand.md).

## Reproducing

```
cd lab
python3 -m fidus_lab.input_paths_eval \
  --cmu ../.cache/corpora/cmu/DSL-StrongPasswordData.csv \
  --out ../research/results/2026-11-04-input-paths
```

Seeded, deterministic, a few minutes. The paths are `fidus_lab.input_paths`
(and `fidus_lab.kloak`), tested in `tests/test_input_paths.py`.

## 1. Can kloak be seen?

Detection EER, clean windows against kloaked ones, over the test halves of all
51 subjects. "Blind" detectors do not know the typist: share of holds under
30 ms, or standard deviation of the holds in the window. "Knows the typist" is
the scaled-Manhattan distance to that subject's clean template. Every
statistic is read in whichever direction it moves.

| D | Short holds, 1 rep | Hold spread, 1 rep | Short holds, 5 reps | Hold spread, 5 reps | Knows the typist, 1 rep |
|---|---|---|---|---|---|
| 25 ms | 0.479 | 0.431 | 0.445 | 0.417 | 0.385 |
| 50 ms | 0.394 | 0.288 | 0.280 | 0.237 | 0.234 |
| 100 ms | 0.202 | 0.110 | 0.091 | **0.047** | 0.092 |
| 200 ms | 0.112 | 0.045 | 0.015 | 0.011 | 0.041 |

The attribution channel labels none of the kloaked repetitions automation (no
clean one either).

## 2. Buffers that re-time the keys

`cadence_P`: key-downs released every P ms, holds 90 ms. `foreign_*`: gaps and
holds copied from a random repetition of a donor, the median-speed subject or
the slowest. A key is never released before it is typed; "leak" is the share
of key pairs where the typist was slower than the plan, so their own gap went
through. Identity is the kloak-aware observer of the previous study (trained
on the transformed corpus), EER / rank-1 identification (chance 2 %).

| Path | Lag mean / p95 / max | Leak | Labelled automation | k = 1 | k = 5 | k = 20 |
|---|---|---|---|---|---|---|
| none | 0 | | 0 % | 0.096 / 48.2 % | 0.072 / 64.7 % | 0.048 / 74.7 % |
| kloak 100 ms | 53 / 96 / 100 ms | | 0 % | 0.152 / 21.9 % | 0.113 / 48.5 % | 0.062 / 68.4 % |
| cadence 150 ms | 29 ms / 0.14 s / 0.48 s | 55 % | 6 % | 0.156 / 13.2 % | 0.174 / 18.3 % | 0.154 / 24.1 % |
| cadence 250 ms | 0.24 / 0.80 / 1.5 s | 20 % | 49 % | 0.163 / 6.8 % | 0.200 / 10.5 % | 0.208 / 13.7 % |
| cadence 400 ms | 0.84 / 2.1 / 3.0 s | 5 % | 82 % | 0.237 / 3.5 % | 0.263 / 5.1 % | 0.273 / 8.6 % |
| median donor | 0.19 / 0.79 / 2.7 s | 38 % | 0 % | 0.236 / 6.8 % | 0.251 / 10.1 % | 0.213 / 14.3 % |
| slowest donor | 1.4 / 4.1 / 13 s | 3 % | 0 % | 0.425 / 2.0 % | 0.473 / 2.5 % | 0.458 / 1.4 % |

A fixed cadence is trivially seen (constant holds: hold-spread EER 0.0). The
donor paths are seen too, through the donor's own hold spread (EER 0.07 and
0.05 over 5 repetitions): everyone behind the same donor shares one rhythm.

## 3. A remote hop

The sender batches events into 16 ms frames; each packet takes a log-normal
network delay (LAN 2 ± 1 ms, WAN 40 ± 10 ms, far 150 ± 40 ms) and arrives no
earlier than the previous one; a packet's events are injected 0.05 ms apart.
"Bursts" is the share of consecutive key events less than 1 ms apart.

| Hop | Lag mean / p95 | Detection, bursts, 1 / 5 reps | Hold spread, 5 reps | Knows the typist, 1 rep | Identity, profiled before, k = 1 | Identity, aware, k = 1 / 20 |
|---|---|---|---|---|---|---|
| LAN | 11 / 18 ms | 0.290 / 0.109 | 0.467 | 0.441 | 0.102 / 43.4 % | 0.102 / 45.6 %, 0.046 / 74.9 % |
| WAN | 49 / 69 ms | 0.242 / 0.077 | 0.329 | 0.305 | 0.114 / 31.3 % | 0.117 / 39.0 %, 0.048 / 75.3 % |
| far | 162 / 235 ms | 0.035 / 0.001 | 0.014 | 0.058 | 0.204 / 9.1 % | 0.171 / 18.7 %, 0.070 / 63.1 % |

Events per packet average 1.02 on this slow, fixed-text typing: bursts are
rare, but a human almost never produces two key events within a millisecond,
so a handful is enough.

## Caveats

- CMU is one password typed many times; leak shares depend on the typist's
  speed on it. Free text is faster on average, which helps buffers.
- The remote model is one ordered stream with independent per-packet delays;
  real stacks add retransmission, coalescing and their own frame clocks. The
  burst statistic depends on the receiver injecting a packet back to back,
  which is what X11 and `uinput` injectors do; under Wayland, remote input
  does not reach `evdev` at all (catalogue E11, E20, E21).
- The donor is a real CMU subject; a buffer shipped to many users would have
  to carry a generative model of a rhythm, not one person's recordings.
