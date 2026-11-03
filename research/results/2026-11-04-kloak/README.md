# kloak on the CMU keystroke benchmark

**What this is.** A measurement of how much kloak, the keystroke anonymiser,
degrades identification and verification on CMU, and whether an observer can
undo it. The write-up, with the reasoning, is
[research/articles/2026-11-04-kloak.md](../../articles/2026-11-04-kloak.md).
This folder holds the numbers.

## Reproducing

The corpus is the one of
[2026-10-21-public-corpora](../2026-10-21-public-corpora/README.md), kept under
`.cache/corpora/` and not redistributed.

```
cd lab
python3 -m fidus_lab.kloak_eval \
  --cmu ../.cache/corpora/cmu/DSL-StrongPasswordData.csv \
  --out ../research/results/2026-11-04-kloak
```

Deterministic (seed 20261104); a few minutes, most of it in the keystroke
expert (under a minute with `--no-expert`). Two runs gave identical `metrics.json`. The model is
`fidus_lab.kloak`, the protocols `fidus_lab.kloak_eval`, both tested on
synthetic rows in `tests/test_kloak.py`.

## Model

`fidus_lab.kloak.obfuscate_times` is the schedule of `kloak.c` (Whonix tree,
September 2026; the original `main.c` applies the same rule to key events): each event is released at
`now + U{lower, D}` with `lower = min(max(prev_release - now, 0), D)`, on an
integer millisecond clock. Each CMU repetition is rebuilt as 22 key events
(down and up of 11 keys, overlaps kept), passed through the schedule, and read
back as H, DD and UD columns. Each repetition gets its own draw.

## Results

Scaled Manhattan, Killourhy and Maxion split at k = 1. Mean EER over the 51
subjects; identification is closed-set rank 1 over 51 templates (chance 2 %).

| Max delay D | Lag mean / p95 | EER, profile taken before kloak | Identification, same | EER, kloak-aware | Identification, same |
|---|---|---|---|---|---|
| none | 0 | 0.0961 | 48.3 % | 0.0960 | 48.2 % |
| 25 ms | 12 / 24 ms | 0.1050 | 37.6 % | 0.1093 | 42.2 % |
| 50 ms | 25 / 48 ms | 0.1156 | 24.2 % | 0.1199 | 33.7 % |
| 100 ms (default) | 53 / 96 ms | 0.1662 | 12.8 % | 0.1520 | 21.9 % |
| 200 ms | 122 / 194 ms | 0.2264 | 7.1 % | 0.1845 | 14.7 % |

Kloak-aware observer, features averaged over k consecutive repetitions (one
repetition is 11 keys):

| D | k = 1 | k = 5 | k = 10 | k = 20 |
|---|---|---|---|---|
| none | 0.0960 / 48.2 % | 0.0717 / 64.7 % | 0.0611 / 69.5 % | 0.0476 / 74.7 % |
| 25 ms | 0.1093 / 42.2 % | 0.0733 / 63.3 % | 0.0629 / 69.1 % | 0.0458 / 75.1 % |
| 50 ms | 0.1199 / 33.7 % | 0.0841 / 58.5 % | 0.0651 / 66.5 % | 0.0502 / 73.5 % |
| 100 ms | 0.1520 / 21.9 % | 0.1134 / 48.5 % | 0.0899 / 58.0 % | 0.0619 / 68.4 % |
| 200 ms | 0.1845 / 14.7 % | 0.1580 / 33.0 % | 0.1305 / 42.6 % | 0.0982 / 52.0 % |

(EER / identification.) The clean row is the same protocol with no kloak.

What the schedule does to the columns, over the whole corpus (ms):

| D | H: shift / added sd | DD: shift / added sd | UD: shift / added sd |
|---|---|---|---|
| 25 | -0.05 / 10.6 | -0.05 / 10.6 | 0.01 / 10.4 |
| 50 | -0.28 / 20.7 | -0.04 / 20.7 | 0.27 / 19.9 |
| 100 | 0.19 / 38.9 | 0.04 / 40.4 | -0.10 / 37.6 |
| 200 | 7.84 / 60.9 | 0.74 / 73.1 | -6.85 / 64.9 |

For scale, the between-repetition sd of a clean column averages 29 ms for
holds and 186 to 189 ms for latencies. Two independent uniform delays on
[0, D] give an interval noise of sd D / sqrt(6), 40.8 ms at D = 100: measured
40.4 on DD. The bias only appears at 200 ms, where the order constraint clamps
short intervals.

The engine's own keystroke expert, one repetition per segment, wide fallback
reference (`public_eval.cmu_keystroke_expert` on the two views):

| D | Profile taken before kloak | Kloak-aware |
|---|---|---|
| none | 0.1291 | 0.1289 |
| 25 ms | 0.1516 | 0.1445 |
| 50 ms | 0.1870 | 0.1671 |
| 100 ms | 0.2636 | 0.2331 |
| 200 ms | 0.3101 | 0.2917 |

## Caveats

- CMU is one fixed password typed 400 times. Averaging k repetitions averages
  the same 31 features; in free text the same number of keystrokes spreads over
  many more digraphs, so k repetitions here stand for more than 11k keystrokes
  of free text for a per-digraph observer, and for fewer for one that pools by
  class, as the keystroke expert does.
- This is a model of the schedule, not the binary. It leaves out the event
  loop's own latency and the compositor; both add jitter of their own, far
  below the delays studied.
- Impostor samples are each subject's first repetitions, as in the published
  protocol, so they include the learning phase of the password.
- Scaled Manhattan is a weak detector by current standards. A stronger
  classifier would recover more, not less, so the averaging results are a
  floor for the observer.
