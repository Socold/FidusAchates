# 09 - Study: the input path, from my hands to the recorder

*3 to 4 November 2026. Status: corrections deployed on my machine, residual risks listed in section 5.*

FidusAchates recognises me by how I type and move the pointer. That only means
something if what the recorder reads is my hands, unaltered, and if what it
keeps about my hands stays mine. A public discussion of keystroke
de-anonymisation ("your typing style is a fingerprint") raised, from the
outside, the questions that matter from the inside: can the rhythm be hidden,
can hiding be seen, can a remote hand be told from mine, and what is my rhythm
worth to someone who copies it. This study measures each of them, records what
I changed in the tool as a result, and keeps the negative results and what is
still open.

Four write-ups go with it, for readers outside the project:
[Does kloak hide how I type?](../research/articles/2026-11-04-kloak.md),
[Hiding how I type for real](../research/articles/2026-11-04-hiding-for-real.md),
[A remote hand on the keyboard](../research/articles/2026-11-04-remote-hand.md),
[What my typing rhythm is worth to a thief](../research/articles/2026-11-04-stolen-rhythm.md).

---

## 1. Questions

| # | Question | Why it matters here |
|---|---|---|
| Q1 | Does random jitter (kloak) hide a typist? | A legitimate privacy tool on my own machine would also blind my verifier. |
| Q2 | Can such a tool be seen in the timing? | If it can, it is a signal; if it cannot, it is a blind spot. |
| Q3 | Does re-timing keys on a schedule hide a typist, and at what cost? | The serious version of Q1, and the textbook way to defeat behavioural verification. |
| Q4 | Does a remote-desktop hop show in the timing (E11)? | Remote takeover is in the threat model. |
| Q5 | What does a forger gain from my template, or from observing me? | My rhythm is a credential. |
| Q6 | Can a forgery be caught by its texture over a session? | The obvious defence against Q5. |
| Q7 | Does what the recorder reads, and keeps, belong to me only? | Not asked by the discussion; raised by deploying the answers. |

## 2. Method

**Data.** The CMU keystroke benchmark (Killourhy and Maxion 2009: 51 people,
one password, 400 repetitions each, hold and latency columns) for everything
that needs many people, under the published protocol (first 200 repetitions to
train, last 200 as genuine, first 5 of each other person as zero-effort
impostors). My own reduced traces, 12 days, 614 segments with at least 15
holds, for every threshold the live daemon uses: a figure that only holds on
CMU is not allowed to raise an alert on my machine.

**Models of the input path**