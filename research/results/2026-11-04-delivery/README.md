# A careful remote operator and a device in the middle, on CMU

**What this is.** What is left of the remote-hop signal (E11) when the operator
smooths delivery, and whether a device between the keyboard and the machine,
emitting a forger's timings, can be told from the keyboard by its polling
grid (E02). Written up in
[research/articles/2026-11-04-delivery.md](../../articles/2026-11-04-delivery.md).

## Reproducing

```
cd lab
python3 -m fidus_lab.delivery_eval \
  --cmu ../.cache/corpora/cmu/DSL-StrongPasswordData.csv \
  --out ../research/results/2026-11-04-delivery
```

Seeded, deterministic, about twenty seconds. Code in `fidus_lab.delivery_eval`
and `fidus_lab.input_paths`, tested in `tests/test_delivery.py`.

## Protocol

**Careful remote operator.** The far path of the input-path study (16 ms
frames, 150 ms mean latency, 40 ms jitter), then either nothing (`raw`), each
run of events closer than 1 ms spread evenly over one frame (`spread`), or
every event replayed 250 ms after its send-side time on a 1 ms tick, or on
arrival if later (`playout_250ms`). Three readings:

- blind detection, clean against delivered windows of k = 1 and 5 test
  repetitions: share of event gaps under 1 ms (`bursts`), share of gaps equal
  to the previous one within 0.05 ms (`repeated_gaps`), read in either
  direction;
- `my_template_notices`: mean EER, my clean test repetitions against the same
  repetitions delivered, both scored by my clean scaled-Manhattan template;
- `impostor_acceptance`: share of other people's repetitions (5 each),
  delivered by the path, accepted at my EER threshold set on clean data,
  against `local_impostor_acceptance` for the same people typing locally.

**Device in the middle.** My keyboard reports on a 1 ms or an 8 ms grid, with
a random phase per repetition and 0.05 ms of Gaussian timestamping jitter;
the verifier is trained and thresholded on that. The forger is the
stolen-template forger of `mimicry_eval` (200 attempts per victim), emitted
with perfect timing (`perfect`), or through a rig on a 1 ms or an 8 ms grid.
`grid_alignment` is the length of the mean phase vector of the event
intervals on a grid; the grid detection is the EER of my later repetitions
against the forgeries on that statistic, windows of k = 1 and 5.

## Results

Careful remote operator:

| Delivery | bursts k=1 | repeated gaps k=5 | my template notices | impostor accepted |
|---|---|---|---|---|
| Local typing | | | | 9.6 % |
| Raw far hop | 0.037 | 0.229 | 0.057 | 0.2 % |
| Spread over a frame | 0.471 | 0.204 | 0.057 | 0.2 % |
| Jitter buffer 250 ms | 0.467 | 0.357 | 0.468 | 9.0 % |

2.8 % of events arrive later than the 250 ms buffer.

Device in the middle (grid detection EER, k = 1; forgery acceptance):

| My keyboard | Forger emits | on 1 ms | on 8 ms | accepted |
|---|---|---|---|---|
| 1 ms | perfect timing | 0.000 | 0.495 | 96.3 % |
| 1 ms | rig at 1 ms | 0.496 | 0.499 | 96.1 % |
| 1 ms | rig at 8 ms | 0.496 | 0.000 | 95.8 % |
| 8 ms | perfect timing | 0.000 | 0.000 | 95.6 % |
| 8 ms | rig at 1 ms | 0.496 | 0.000 | 95.6 % |
| 8 ms | rig at 8 ms | 0.499 | 0.499 | 95.3 % |

**Indicative, my own machine.** On one day of my own trace, my mouse reports
every 8 ms and its motion intervals align at 0.998 on a 1 ms grid and 0.87
on an 8 ms grid: the polling grid of real hardware is visible in the evdev
timestamps the recorder reads. Only this aggregate was computed; no event
leaves the machine.

## Limits

The grids are simulated on CMU, whose intervals carry none (0.1 ms
resolution, residues uniform). Real stacks add their own structure (USB
frame scheduling, interrupt coalescing) which may help or hurt the test.
The remote paths are the input-path study's model, not measured links.
