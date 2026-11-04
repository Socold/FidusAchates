# Forging a typist from a stolen or observed rhythm, on CMU

**What this is.** How often a forger is accepted by the CMU baseline and by the
engine's keystroke expert, depending on what the forger holds: nothing, the
stolen template, or n of the victim's repetitions captured with or without
kloak. Written up in
[research/articles/2026-11-04-stolen-rhythm.md](../../articles/2026-11-04-stolen-rhythm.md).

## Reproducing

```
cd lab
python3 -m fidus_lab.mimicry_eval \
  --cmu ../.cache/corpora/cmu/DSL-StrongPasswordData.csv \
  --out ../research/results/2026-11-04-mimicry
```

Seeded, deterministic, a few minutes. Code in `fidus_lab.mimicry_eval`,
tested in `tests/test_input_paths.py`.

## Protocol

Per subject (51 victims), the verifier is fitted on the first 200 repetitions
and its threshold set at the subject's EER point against the published
zero-effort impostors. 200 forged attempts per victim and per forger are
scored at that threshold. Scaled Manhattan forgeries draw each H and DD from
the template's mean plus Laplace noise of the template's mean absolute
deviation (UD rebuilt as DD - H); keystroke-expert forgeries draw each hold
and latency from the stolen template's log-normal for its class. Observed
repetitions come from the victim's test half, through kloak at 100 ms for the
`kloak` rows. The deflated forger keeps the means seen through kloak and
removes kloak's variance (D^2 / 6 on H and DD) from the spread.

## Results

Mean share of forged attempts accepted (victims for which more than half are
accepted, out of 51).

| Forger | Scaled Manhattan | Keystroke expert |
|---|---|---|
| Zero effort (the published impostors) | 0.096 (0) | 0.129 (0) |
| Stolen template, centre replayed | 1.000 (51) | |
| Stolen template, sampled | 0.960 (51) | 0.890 (51) |
| Observed 5 repetitions | 0.910 (50) | 0.789 (47) |
| Observed 20 repetitions | 0.926 (50) | 0.782 (45) |
| Observed 50 repetitions | 0.939 (51) | 0.795 (48) |
| Observed 5 through kloak, naive | 0.128 (1) | 0.026 (0) |
| Observed 20 through kloak, naive | 0.161 (2) | 0.019 (0) |
| Observed 50 through kloak, naive | 0.161 (2) | 0.017 (0) |
| Observed 5 through kloak, kloak-aware | 0.523 (30) | 0.289 (10) |
| Observed 20 through kloak, kloak-aware | 0.746 (48) | 0.512 (28) |
| Observed 50 through kloak, kloak-aware | 0.777 (49) | 0.558 (31) |

The attribution channel labels none of the sampled forgeries automation (0 %
for both kinds).

## Caveats

- The forger is assumed able to emit arbitrary timings: an injector the
  recorder sees as virtual (E01), a microcontroller posing as a keyboard (E19
  if hot-plugged), or a device between keyboard and machine. The numbers say
  what the timing alone is worth, not how hard injection is.
- Attempts are scored one repetition at a time. Over a session, a forger
  sampling from a template also has to keep the right variance and
  correlations from one repetition to the next; nothing here tests that.
- The "centre replayed" forger sends the same repetition every time, which a
  repeat check would catch at once; it is there as the upper bound.
