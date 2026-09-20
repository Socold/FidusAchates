# Remedies for the close-impostor failure: measured

**What this is.** The off-model validation
([2026-09-20-off-model-validation](../2026-09-20-off-model-validation/README.md))
found that a close impostor was never caught against a bimodal genuine user with
no impostor population enrolled. Two remedies named there are now built. This
artifact measures what each one buys, on the same generators and seeds.

## Remedy 1: a two-component mixture per signal

For bimodality **within** a segment (the `HostileTypist`: fast and slow holds
mixed key by key). A single log-normal fitted to two regimes inflates its sigma
and swallows anyone near the centre; a mixture keeps the density low in the
valley. Two things had to change together:

- the genuine model: `fit_best` picks a mixture when it wins on BIC and its
  components are separated. Heavy-tail outliers are trimmed first; without
  that, a few four-fold values were absorbed into one component and hid the
  bimodality behind an inflated sigma (the separation guard then rejected it).
- the no-population reference: it used to be three times the **envelope**
  sigma, which for a bimodal signal is inflated by the distance between the
  regimes. It was so wide that every value near the user scored as genuine,
  and -157 dB of hold "evidence" drowned +28 dB from the digraphs. It is now
  scaled from the within-regime (pooled component) spread.

| Metric | Before | After |
|---|---|---|
| False alarm rate, off-model genuine user | 0.0 | 0.0 |
| Distinct impostor detected | 100 % | 100 % |
| **Close impostor detected** | **0 %** | **47 % (median delay 6 segments)** |

Half recovered. The rest is the intrinsic overlap between a close impostor and
a user whose slow regime sits where the impostor types: no unimodal reference
will separate what the data itself does not.

## Remedy 2: modes, one template per regime

For bimodality **across** segments (the `ModalTypist`: a segment is entirely on
the laptop keyboard or entirely on the external one). Enrolment groups
segments into regimes (`fit_modes`, agglomeration on per-segment templates),
fits one template per regime, and the engine scores a segment against its
best-matching mode.

What modes add over per-signal mixtures is **joint structure**. A mixture makes
each signal bimodal on its own, so an impostor who copies regime A's hold times
and regime B's rhythm is plausible signal by signal. No single mode of the
genuine user has that combination.

| Engine | False alarms (two-keyboard user) | Cross impostor detected |
|---|---|---|
| Single template, per-signal mixtures | 0.0 | **0 %** |
| Modes, joint templates (2 recovered) | 0.0 | **100 %, delay 1 segment** |

Two things learned while building this, both recorded so they are not
re-learned:

- the measured signals are not independent of each other (down-to-down latency
  is hold plus gap), so a "cross" impostor has to be built on the **measured**
  signals, not on the generator's parameters; a first attempt was trivially
  detected for the wrong reason;
- modes only help when the regimes are well separated on every signal
  involved. With regimes 1.2 sigma apart on one signal, the impostor borrows
  the mode where its mismatch is mild, and the best-matching rule lets it in.
  That is a property of the data, not a bug, and it bounds what modes can do.

## Limits

Still synthetic. The 47 % on the close impostor is the number to beat with a
real enrolled impostor population, which remains the strongest remedy and is
gated on same-machine impostor sessions.
