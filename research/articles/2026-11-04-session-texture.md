# Right on average, wrong in texture

*4 November 2026. Numbers and code: [research/results/2026-11-04-session](../results/2026-11-04-session/README.md).*

[The previous article](2026-11-04-stolen-rhythm.md) ended on a worrying line: a
forger holding my template is accepted 89 % of the time by my keystroke
expert, and one who merely watched me type 55 keys on a web page, 79 %. Those
forgeries were scored one repetition at a time. I left one question open: a
forger has to be right on average, but does it also have to be right in its
texture, over a whole session?

## What texture means here

Each repetition of the CMU password is 21 timings: how long each key is held,
and the gap from one key going down to the next. A template like mine stores,
for each timing, a centre and a spread. That is all the forgers of the last
article used, and it is all they needed to pass.

What a template of centres and spreads does not hold is how the timings move
together. When I type a repetition slowly, I am slow almost everywhere, not on
three keys at random. Some pairs are tied because the same finger or the same
hand does both. A forger drawing each timing on its own gets every one of them
right and the way they move together wrong.

So I fitted, for each of the 51 people, a model with the full covariance
between timings, next to one with the spreads alone. The texture of one
attempt is how much more likely it is under the first than under the second:
positive when the attempt carries the person's correlations. I also tracked a
second cue, how the overall speed of one attempt follows the previous one,
since a real sitting drifts.

## Results

Detection error (EER) between the victim's own later repetitions and the
forger's, over windows of consecutive attempts. 0.5 is a coin toss.

| Forger | 1 attempt | 10 attempts | 50 attempts |
|---|---|---|---|
| Template of centres and spreads (the last article's) | 0.20 | 0.05 | 0.01 |
| The victim's own spreads, drawn independently | 0.22 | 0.10 | 0.04 |
| Watched 5 repetitions | 0.33 | 0.27 | 0.22 |
| Watched 50 repetitions | 0.38 | 0.35 | 0.35 |
| Holds the full covariance | 0.48 | 0.61 | 0.66 |

Three things come out.

**The forgery that beat me one attempt at a time is easy to catch over a
session.** The template forger is told apart one time in five on a single
attempt, and almost always (EER 0.01) over fifty. Its texture is flat, and
averaging only makes that clearer. Nothing in the template helps it: the
correlations simply are not there to steal.

**A forger who watched me is caught less well, and watching more does not
make it easier to catch.** Five observed repetitions are too few to estimate
21 by 21 correlations, so that forger falls back on spreads and is caught at
0.22 over fifty attempts. Fifty observed repetitions are enough to recover
part of the structure, and the error rises to 0.35. A page that times my keys
for long enough collects my texture along with my rhythm.

**A forger holding my full model is past this test entirely.** Above 0.5, the
forgery looks more like my model than I do a few days later: I drift from my
own training, a sample drawn from the model does not. Copying the speed drift as
well is trivial for such a forger, and the speed cue on its own never did
better than 0.28 against anyone.

## What it means for FidusAchates

- **Store the covariance, score the texture.** It costs 21 by 21 numbers per
  template and catches the forger the last article was worried about. It goes
  next to the keystroke expert as a session-level signal, read over a window
  rather than per attempt.
- **That same covariance is now the most valuable thing to steal.** A template
  with correlations is a better forging kit than one without. Sealing at rest
  (docs/10, section 2) was already required; this makes it the line that the
  texture defence depends on.
- **The speed drift is not worth a signal.** A real sitting drifts, but not
  enough to tell from independent draws, and a forger reproduces it in one line.
- **Provenance still carries the weight against the strongest forger.** Holding
  the full model, a forger is limited only by how it emits the timings. That is
  the case for the next experiment, a physical rig between the keyboard and the
  machine, which adds its own noise.

## Limits

CMU is one password, so the correlations are between the same eleven keys
every time. In free text they have to be pooled by digraph class, as the
keystroke expert already does for spreads, and how much of the texture
survives that pooling is not measured here. The genuine windows are CMU's last
two sessions, days after the four used for training, so day-to-day drift is
already in the numbers; months of it are not.
