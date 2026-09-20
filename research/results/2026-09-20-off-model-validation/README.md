# Off-model validation: the engine on data built to break its assumptions

**What this is.** Every earlier validation used log-normal typists, the very
model the engine assumes, so the engine "worked" on data made for it. Here the
genuine user is a `HostileTypist`: bimodal hold times, bursty gaps with long
pauses, a share of corrections, heavy-tail outliers. The impostor reference is
the wide fallback (no impostor population enrolled), which is the situation on
a real machine before any second person has been recorded.

## Method

- Enrolment: 10 hostile segments (~40 keystrokes each).
- False alarms: 60 genuine sessions of 6 segments, a fresh engine each.
- Detection: 60 impostor sessions of 10 segments, two impostors: one clearly
  distinct (log-normal, far centre) and one **close** to the hostile user's
  centre.
- Engine: keystroke expert, CUSUM h = 25 dB, prior -10 dB. Seeded.

## Result (`metrics.json`)

| Metric | Value |
|---|---|
| False alarm rate, off-model genuine data | 0.0 (0 of 60 sessions) |
| Distinct impostor detected | 100 %, median delay 1 segment |
| **Close impostor detected** | **0 % (0 of 60)** |

## What it says, plainly

The engine does not misfire on a user who violates its model: the log-normal
fit on bimodal data is wide, and a wide model forgives its own user. That is
the good news and it was not guaranteed.

The same width is the bad news. **A close impostor is never caught.** Two
mechanisms compound:

1. A bimodal genuine user inflates the fitted sigma, so the acceptance region
   swallows anyone near the centre.
2. With no impostor population, the wide fallback reference (three times the
   genuine sigma) barely disagrees with the genuine model near its centre, so
   the evidence there is close to zero whoever is typing.

This is a limit of the current model, not of the data: it was invisible to
every earlier test because the synthetic typists were unimodal and the
impostors were far.

## What follows from it

- The design already names the remedy for (1): a two-component mixture when a
  distribution is clearly bimodal, and modes (decision engine section 3 and
  6). Neither is implemented in the keystroke expert yet.
- (2) is the strongest argument yet for an enrolled impostor population (the
  same-machine impostor sessions of the evaluation protocol): the wide
  fallback is a stopgap, and this measures how much it costs.
- A close-impostor scenario with a bimodal genuine user is now a standing
  test case (`test_hostile.py`), so any future gain has to show up here.

## Limits

Still synthetic. A real bimodal user and a real close impostor may differ in
kind, not just in degree. The value is that the failure is now measured and
reproducible instead of assumed away.
