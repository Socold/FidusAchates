# Usage-aware identity: global templates versus one set per usage

**What this is.** I type differently when I write and when I play. Until now
the engine learnt both as modes of one global model and scored each window
against the best-matching mode. It now knows which kind of application each
window was typed in (the focus category, content-free) and, once a usage holds
enough of my data, scores the window against that usage's templates only,
with modes inside each usage. This artifact measures what that buys, on
synthetic typists, same enrolment and seeds for both engines.

Reproduce: `PYTHONPATH=lab python3 research/results/2026-10-21-usage-aware/run.py`.

## Setup

Enrolment: 40 windows of me writing in an office application, 40 of me playing
in a game, and 20 of me typing in the game's chat as I write. The global model
recovers 2 modes; the usage-aware model fits 1 for office and 2 for game.
30 sessions of 15 windows per case. No impostor population: both engines use
the wide fallback reference.

## Results

Share of sessions with at least one alarm (false alarms for "me", detection
otherwise), and the median window of the first alarm:

| Case | Global | Usage-aware |
|---|---|---|
| Me writing | 0 % | 0 % |
| Me playing | 0 % | 0 % |
| Me chatting in a game | 0 % | 0 % |
| Someone writing with my playing rhythm | **0 %** | **100 %, window 1** |
| Someone between my two rhythms, writing | 100 %, window 1 | 100 %, window 1 |
| Cross impostor (holds longer than mine, gaps shorter), writing | **3 %, window 6** | **100 %, window 1** |

## Reading

- The gain is exactly the case modes cannot cover: an impostor who matches
  one of my usages, but in the other one. The global engine lets them borrow
  the mode where their mismatch is mild; the usage-aware one does not offer
  that mode.
- The cross impostor shows the same thing less obviously. Measured
  down-to-down latency is hold plus gap, so their long holds and short gaps
  land close to my playing rhythm on that signal; against my writing
  template alone they are far.
- Modes inside a usage are needed. A first version with a single template
  per usage alarmed on me typing in a game's chat; with modes per usage it no
  longer does.

## Limits

- Synthetic, and the two usages are well separated here by construction. On
  real data the gain depends on how different my usages really are, which the
  live daemon will tell after a few days per usage.
- A usage needs 30 windows, 1500 keystrokes (and 3000 pointer moves for the
  pointer template) before it gets its own templates; until then its windows
  are judged by the global ones, as before.
- It is only as good as the category. A game the extension does not recognise
  falls into "other", and a browser covers very different activities.
