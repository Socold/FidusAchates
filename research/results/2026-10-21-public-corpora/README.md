# First measurement on public corpora: CMU keystroke and Balabit mouse

**What this is.** The first time I run the engine's code on data from real
people: the CMU Keystroke Dynamics benchmark (Killourhy and Maxion, 51
subjects, one fixed password) and the Balabit Mouse Dynamics Challenge (10
users, RDP mouse sessions). It answers roadmap criteria 2.2 (scaled Manhattan
on CMU) and 4.2 (digraph classes against true digraphs), and gives a first,
honest number for the pointer expert. Nothing was tuned on the test data:
every parameter is the published protocol's or the engine's default.

## Reproducing

Neither corpus is redistributed. I keep them under `.cache/corpora/`
(gitignored):

- `DSL-StrongPasswordData.csv` from https://www.cs.cmu.edu/~keystroke/
  (sha256 `b11d2353...a7a33`).
- The Balabit repository archive (github.com/balabit/Mouse-Dynamics-Challenge,
  `master`), `public_labels.csv` sha256 `efd27f2a...842c`.

```
cd lab
python3 -m fidus_lab.public_eval \
  --cmu ../.cache/corpora/cmu/DSL-StrongPasswordData.csv \
  --balabit ../.cache/corpora/balabit \
  --out ../research/results/2026-10-21-public-corpora
```

Deterministic; it takes tens of minutes, mostly fitting the population reference. The code
is `fidus_lab.corpus` (ingest) and `fidus_lab.public_eval` (protocols), tested
on synthetic files in `tests/test_public_corpora.py`. All numbers are in
`metrics.json`, per subject and per user.

## CMU keystroke

**Protocol** (Killourhy and Maxion 2009): per subject, train on the first 200
repetitions, test on the remaining 200 as genuine and on the first 5
repetitions of each of the 50 other subjects as impostors (250 impostor
samples). EER per subject, read at the FAR/FRR crossing over every distinct
score (`metrics.eer_exact`), then averaged over the 51 subjects.

| Detector and representation | Features | Mean EER | Std |
|---|---|---|---|
| Scaled Manhattan, all H, DD, UD | 31 | **0.0960** | 0.069 |
| Published (Killourhy and Maxion) | 31 | 0.096 | 0.069 |
| Scaled Manhattan, every hold + DD of the 9 classed pairs | 20 | 0.0941 | 0.074 |
| Scaled Manhattan, mean hold per key class + mean DD per digraph class | 10 | 0.1223 | 0.083 |
| Keystroke expert, digraph classes (as recorded) | | 0.2185 | 0.129 |
| Keystroke expert, true digraphs | | 0.1968 | 0.118 |

**Criterion 2.2 is met**: 0.0960 against the published 0.096, well within
0.01. The fixed 400-step grid of `metrics.eer` gives 0.0986 on the same scores;
a few extreme impostor distances stretch its range, which is why I added the
exact reading.

**Criterion 4.2.** With the same detector, pooling into classes costs about
2.8 points of EER (0.094 to 0.122). That loss mixes two things: holds pooled
per key class (8 of the 11 keys are letters, so 8 holds collapse into one),
and the 9 key pairs pooled into 6 digraph classes. Inside the keystroke expert,
where holds are pooled by class in both runs and only the digraph tagging
changes, true digraphs gain 2.2 points (0.219 to 0.197). So on this corpus the
digraph classes cost roughly 2 points of EER, and most of the remaining gap to
the canonical detector comes from elsewhere. My reading: the cost is real but
moderate, the default of ADR-0008 stands for free text (where true digraphs
would be too sparse to model and would carry content), and the pooled hold is
the bigger loss on this fixed-text task.

**A bug found on the way.** The expert's hold matcher (`_hold_times` in
`experts/keystroke.py`) pairs a key-up with the last key-down *of the same
class*. When a letter goes down before the previous letter is up (rollover),
the first down is overwritten: its hold becomes up(first) minus down(second),
and the second hold is lost. On CMU, 53.5 % of repetitions contain at least one
such overlap. As a diagnostic only, I re-ran the expert with a first-in,
first-out matcher patched in for that run:

| Keystroke expert, FIFO hold matcher | Mean EER | Std |
|---|---|---|
| Digraph classes | 0.1287 | 0.088 |
| True digraphs | 0.1152 | 0.079 |

The matcher alone is worth about 9 points of EER here, far more than the class
abstraction. Fast free-text typing rolls over too, so I expect it to matter
live. I have not changed the expert in this run.

## Balabit mouse

**Ingest** (`corpus.load_balabit_session`). Absolute positions become deltas
between successive events and are then dropped, as the recorder only sees
relative motion. Move and Drag become MOTION, Pressed and Released become
button down and up, each Scroll Down or Up becomes one wheel notch. Time is
the client timestamp, kept non-decreasing. Two motion variants: one record
per event with both deltas, and split axes (an X then a Y record at the same
time, none for a zero axis), which is what the live recorder writes.

**Protocol.** Per user, the pointer template is fitted on all of that user's
training sessions, segmented with the default segmenter (2 s gap, 60 s cap).
Test data is the 816 test sessions labelled in `public_labels.csv` (the other
test sessions have no public label and are not used). Each session is
segmented and run through `IdentityEngine` with only the pointer expert
enrolled; segments below the engine's quality gate are left out. The
reference is the wide fallback (no impostor data in training). Scores: per
segment, summed over non-overlapping runs of 3 and 5 consecutive segments of
a session, and the mean evidence of the whole session. EER per user, then
averaged over the 10 users.

| Mean EER over 10 users (std) | 1 segment | 3 segments | 5 segments | Session |
|---|---|---|---|---|
| Wide fallback, combined motion | 0.377 (0.107) | 0.328 (0.136) | 0.310 (0.139) | 0.286 (0.153) |
| Wide fallback, split axes | 0.370 (0.120) | 0.324 (0.149) | 0.302 (0.152) | 0.281 (0.158) |
| Population reference, combined | 0.379 (0.114) | 0.321 (0.139) | 0.311 (0.144) | 0.289 (0.146) |

Per user (wide fallback, combined), session level: user9 0.00, user7 0.08,
user15 0.26, user16 0.26, user20 0.26, user29 0.30, user23 0.31, user35 0.37,
user12 0.51, user21 0.51. Two users are recognised well, two are at chance.

**Reading.** These are bad numbers, and I report them as they are. The pointer
expert was written as a minimal fallback so the engine is not blind without
typing: four timing signals (speed, pause before click, click duration, wheel
interval), each a single log-normal, nothing about trajectory shape,
curvature, direction or acceleration, which is where the published Balabit
detectors get their power. Accumulation helps (0.38 per segment to 0.29 per
session), but the per-segment evidence is too weak for accumulation to rescue
most users. The population reference does not help either, which suggests the
limit is in the signals rather than in the reference.

## Caveats

- **CMU is fixed-text and lab-collected**: one password, typed 400 times. The
  engine targets free text; the expert numbers measure the representation on a
  task it was not built for, not its live performance.
- **The digraph comparison covers 9 pairs and 6 classes.** That is a narrow
  slice of the class space (four of the five relations, no repeat, a single
  same-finger pair). A free-text corpus is needed for a broader verdict.
- **CMU rows are rebuilt as records** from H and DD, which is exact to the
  microsecond rounding; Shift is not a separate key in CMU, consistent with
  the reducer, which skips modifiers in digraphs.
- **Balabit is RDP traffic**: motion is coalesced (events about every 16 to
  110 ms, many sharing a timestamp), positions are screen pixels, not device
  counts. Speeds are therefore not comparable with local evdev traces, and the
  velocity signal drops motion that arrives with a zero time step.
- **Balabit impostors are imitated**: the challenge mixed other users' data
  into each user's test folder. The population reference uses the other
  users' training sessions, so it may contain the very attacker; that would be
  optimistic, yet it did not help.
- **Only the public half of the Balabit labels exists**, so 816 of 1611 test
  sessions are used, with an unequal genuine to impostor mix per user.
- **Split axes** changes the velocity signal: with X and Y as separate
  records sharing a timestamp, each velocity is computed from one axis only.
  It made almost no difference here, but it means the live velocity is not the
  speed of the pointer; worth knowing when reading the signal.
- **EER only.** No CUSUM run lengths are reported: the alarm threshold is not
  calibrated for these corpora, and calibrating it on the test sessions would
  be tuning on the test set.
