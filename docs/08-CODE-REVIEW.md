# 08 - Code review

> A critical re-reading of the code once work packages 0 to 8 existed, the way
> [07-DESIGN-REVIEW.md](07-DESIGN-REVIEW.md) re-read the design. Every finding
> was confirmed in the source before being written down, and every one is now
> fixed; the fix and the test that guards it are named. Kept as a record: the
> point of a review is what it teaches, and most of what it taught here was that
> my own tests were not looking in the right places.

## Verdict at review time

The architecture was sound and matched the specifications; the code was clean
and well tested on its pure logic; but the project was more "verified
foundations" than "system that works for real", and it held several bugs the
tests had not caught, two of which contradicted my own security requirements.

## Confirmed bugs

| # | Where | What | Severity | Fix |
|---|---|---|---|---|
| 1 | `engine.py` | The CUSUM was never reset after an alarm: one alarm made every later window "alarmed" for the session. The spec said reset at L4. | High | Reset at L4; the decision carries the statistic before the reset. Test: a genuine window after an alarm is not alarmed. |
| 2 | `console.py` | The session token travelled in the URL, including the SSE stream. My own SR-9 says cookie, never URL. | High | HttpOnly, SameSite=Strict cookie set by a one-time bootstrap link that dies on first use. Tests: link works once, then 403; foreign Host refused even with the cookie. |
| 3 | `confine.rs` | The seccomp filter checked no ABI (a 32-bit syscall uses another table: bypass) and did not block io_uring (which can create sockets). Both identified at design time, neither implemented. | High | Non-native ABI is killed; io_uring_setup refused; the self-test checks both. Verified on the real machine and by an integration test on the real binary. |
| 4 | `live.py` | The console's profile count added the same enrolled template every segment, so it always collapsed to one. | Medium | A template per observed segment. |
| 5 | demos | `reference=genuine` made every likelihood ratio exactly zero: the Identity channel looked alive and was inert. | Medium | The engine refuses it; `None` uses a wide fallback and says so; demos enrol on a temporal split and announce when a trace is too short. |
| 6 | `loop_.rs` | An unplugged device kept its path in the open set and its fd open: plugged back, it was never captured again. | Medium | Retire the device, forget the path, close the fd. Verified with a virtual keyboard destroyed and recreated: 7 + 7 keystrokes. |
| 7 | `TRACE-FORMAT.md` | Claimed a crash loses at most one record; the writer buffers kilobytes. | Low | Corrected. |
| 8 | READMEs | Two different console commands, one non-existent. | Low | Corrected. |

## Design weaknesses

| Finding | Fix |
|---|---|
| The pointer was captured and never used; the engine was blind whenever nobody typed. | A pointer expert (velocity, pause before click, click duration, wheel cadence). Test: a pointer-only impostor is detected with no typing at all. |
| Explainability was decorative: one scalar per expert, one bar in the waterfall. | Experts return per-signal evidence; the waterfall has several bars that sum exactly to the fused evidence (tested). |
| Profile merging used the minimum distance over modes and only the closest pair: one close mode anywhere could chain distinct people into one profile. | Average linkage for distance-only merges; closest-mode distance only with temporal interleaving; every qualifying pair considered. Test: a bridge regime between two people no longer joins them. |
| Enrolment assessment trusted caller-supplied counts. | An `EnrolmentTracker` derives keystrokes, sessions and devices from the segments it is fed. |
| The overlay client spawned a `gdbus` process per segment. | A Gio proxy where PyGObject exists, and calls only on state change. |

## Validation weaknesses

| Finding | Fix |
|---|---|
| Circular validation: every result came from log-normal typists, the model the engine assumes. | A `HostileTypist` (bimodal, bursty, corrections, heavy tails). It exposed the close-impostor failure, recorded in `research/results/2026-09-20-off-model-validation`, then remedied and re-measured in `2026-09-20-off-model-remedies`. |
| The seccomp lockdown, the most security-critical code, was never exercised in CI; a first BPF program that made the process refuse itself every syscall passed CI unnoticed. | A `selftest` command and an integration test on the real binary: a real check on the CI runner and a developer machine, an explicit skip where seccomp is forbidden, never a fake pass. |
| The inotify event walk, hand-parsed, had no test. | A pure parser over a byte buffer, tested including a truncated record. |
| No Python lint in CI. | ruff, with an explicit rule set so local and CI agree (the CI's newer ruff had flagged 49 things a local run never showed). |

## Found while fixing

Fixing on real data turned up two more things the synthetic tests could not:

- **Provenance diluted across modalities.** On a real trace, 14 injected
  keystrokes inside 400 hardware mouse events were labelled human because the
  virtual fraction was computed over all events. Provenance is now judged per
  modality: a burst of injected keystrokes is automation whatever the mouse
  does.
- **Measured signals are coupled.** Down-to-down latency is hold plus gap, so a
  "cross-regime" impostor has to be built on the measured signals, not the
  generator's parameters; a first attempt was trivially detected for the wrong
  reason. Recorded in the remedies artifact so it is not re-learned.

## What held up

The privacy boundary (the record type cannot hold a key code; the content-free
property is proven exhaustively, not sampled); the separation of attribution
from malice (ADR-0011); the recorder's size, auditability and measured
footprint; the CUSUM-plus-linear-fusion choice; and the habit of saying what
is synthetic.
