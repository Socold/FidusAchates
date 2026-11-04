# Hiding how I type for real, and being seen hiding

*4 November 2026. Follows [Does kloak hide how I type?](2026-11-04-kloak.md).
Numbers and code: [research/results/2026-11-04-input-paths](../results/2026-11-04-input-paths/README.md).*

The first article ended on a claim I had not measured: random jitter around
my own rhythm leaves my rhythm in place, so real hiding needs an output whose
timing no longer depends on how I type. A discussion of keystroke
de-anonymisation raised the same idea from several sides (buffer the keys and
replay them on a fake pattern, drive a second keyboard from a small computer),
and also the obvious objection: whatever you do, the protection itself may
give you away. I measured both on the CMU benchmark, with the same protocol
and the same observer as before.

## Can anyone see that I run kloak?

The observer does not need to know who I am. kloak adds a triangular noise
of standard deviation D / sqrt(6) to every hold, and human holds are tight
(29 ms of spread between repetitions on CMU). So the spread of my holds is a
tell: at the default 100 ms, the standard deviation of the holds in one
11-key repetition separates kloak from no kloak with an EER of 0.11, and five
repetitions (55 keys) bring it to 0.047. The share of holds under 30 ms works
too, a bit less well. If the observer already has a clean template of me, the
distance to it gives 0.09 on a single repetition.

At 25 ms, the setting that is comfortable to type with, detection is near
chance (0.42 to 0.48). But that is also the setting that hides nothing once a
few repetitions are averaged. So the trade is stark: kloak strong enough to
blur a sample is visible, kloak invisible enough to pass is useless.

My own engine's attribution channel does not call kloak automation (0 % of
repetitions): its timing cue looks for metronomic regularity, and kloak is the
opposite. That is the right outcome for a privacy tool, and a reminder that a
"human or machine" test is not a "re-timed or not" test.

## Re-timing for real: a buffer

A buffer holds the keys and releases them on its own schedule. One physical
constraint shapes everything: it cannot release a key before I type it. If my
gap is shorter than the planned one, the key waits; if it is longer, the key
goes out when I type it, and my own gap leaks into the output.

I tried two schedules. A fixed clock, one key every P ms, each held 90 ms. And
someone else's rhythm: the gaps and holds of a random repetition of a donor,
either the median-speed subject of the corpus or the slowest.

| Path | Mean lag | Keys leaking my gap | Identification, k = 1 / 20 | Seen by my engine as automation |
|---|---|---|---|---|
| Nothing | 0 | | 48 % / 75 % | 0 % |
| kloak 100 ms | 53 ms | | 22 % / 68 % | 0 % |
| Clock, 150 ms | 29 ms | 55 % | 13 % / 24 % | 6 % |
| Clock, 400 ms | 0.84 s | 5 % | 3.5 % / 8.6 % | 82 % |
| Median donor | 0.19 s | 38 % | 7 % / 14 % | 0 % |
| Slowest donor | 1.4 s | 3 % | 2.0 % / 1.4 % | 0 % |

(Identification among 51 subjects, chance is 2 %, by an observer who knows
the buffer and averages k repetitions.)

Three things stand out.

**Buffers work where jitter does not.** Even the cheap 150 ms clock holds
identification at 24 % after 20 repetitions, where kloak lets it climb back
to 68 %. Averaging does not help the observer much any more, because the
output is no longer my rhythm plus noise; it is mostly the schedule.

**What is left is the leak.** Every key I type slower than the plan carries
my own gap. With the median donor, 38 % of key pairs leak, and that is enough
to keep identification at 14 %, seven times chance. Only a schedule slower
than almost everything I type closes the leak: the slowest donor brings
identification to chance, at a mean lag of 1.4 seconds per key and up to 13
seconds. That is not a keyboard any more, it is a message queue.

**And it is visible.** A fixed clock gives constant holds, which no human
produces: separation is perfect. My engine flags the 400 ms clock as
automation 82 % of the time, through the same regularity cue. The donor
schedules pass as human, but everyone behind the same donor shares the
donor's rhythm, and that rhythm can be told from the crowd (EER 0.05 to 0.07
on 5 repetitions in this corpus). Hiding behind one person makes you that
person's crowd, which is only as good as the number of people in it.

## What I take from it

- Random jitter (kloak) is the wrong tool for anything longer than a
  password. It is cheap, it is detectable at the settings where it helps, and
  averaging defeats it.
- Decoupling the output from the typist does work, and the cost is latency
  set by the slowest gaps you want to cover. For composing a message offline
  and sending it as one block, that cost is fine; for live typing, it is not.
  The plain advice from the discussion, write elsewhere and paste, is the
  extreme case of a buffer: one release, no rhythm at all, and the paste
  event as the only tell.
- A shared rhythm needs a large population of users to hide in, and a
  generative model rather than one donor's recordings. That is a product, not
  a setting.

## What it means for FidusAchates

The question I build for is the reverse one: is it still me, and is it still a
human. Two lessons go into the engine. First, "re-timed input" deserves its
own cue, distinct from "automated input": the distance to my own template
catches kloak at 100 ms on one repetition (EER 0.09), mostly through the holds,
while the regularity cue never will. Second, a buffer replaying someone else's rhythm is the
textbook way to defeat behavioural verification, and it looks human by
construction; what betrays it is the lag structure (keys held back, then
released on a schedule that ignores mine). That is a signal worth adding to
the catalogue next to E18.

## Limits

One fixed password typed 400 times, so leak shares depend on how fast people
type that password; free text is faster on average, which helps buffers. The
donor is one real subject's recordings. The detectors are deliberately simple;
better ones only make "being seen" more likely.
