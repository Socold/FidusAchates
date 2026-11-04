# Research and study

This directory is the study behind FidusAchates: the questions raised while
building it, the measurements that answered them, and what each answer changed in
the engine. It is kept separate from the product documentation in `docs/` because
its job is different. `docs/` says what the tool does; this says what I learned,
with the numbers and the code to reproduce them.

Two rules hold everything here together:

- **A claim is a measurement or it is a note.** Every figure below links to a
  results folder with the seed, the corpus and the script that produced it. The
  protocol is [EVALUATION-PROTOCOL.md](EVALUATION-PROTOCOL.md); the input format
  the lab replays is [TRACE-FORMAT.md](TRACE-FORMAT.md).
- **Public corpora, not my own data, for anything I publish.** The headline
  numbers use the CMU keystroke benchmark and the Balabit mouse corpus, so they
  can be checked without my recordings. Where only my machine can answer a
  question, the article says so and treats the result as indicative.

## Measurement baseline

The lab reproduces the CMU keystroke benchmark at EER 0.096 (against the published
0.096) and ingests the Balabit mouse corpus. That baseline is what the signal
studies and the attack studies are measured against, so a number here is a move
away from a known reference rather than a figure with no scale.

## Articles

| Date | Article | Question | Headline finding |
|---|---|---|---|
| 2026-11-04 | [Does kloak hide how I type?](articles/2026-11-04-kloak.md) | Does the standard anti-fingerprinting daemon actually hide a typing rhythm? | At its real default (100 ms) it is visible, mostly through hold times; invisible only at a delay too small to protect. |
| 2026-11-04 | [Hiding how I type for real, and being seen hiding](articles/2026-11-04-hiding-for-real.md) | What does it cost to hide a rhythm so it cannot be recovered? | Real hiding needs output whose timing no longer depends on the typing; a buffer that replays someone else's rhythm is the textbook defeat, and its lag structure betrays it. |
| 2026-11-04 | [A remote hand on the keyboard](articles/2026-11-04-remote-hand.md) | Can a remote operator be told from key timing? | Near-simultaneous key bursts from a long network path are a cheap, enrolment-free signal (E11), strong exactly where the threat is. |
| 2026-11-04 | [What my typing rhythm is worth to a thief](articles/2026-11-04-stolen-rhythm.md) | If someone steals my template, can they impersonate me? | Yes, on a fixed password, and the forgery reads as human; which is why the template must be protected at rest and never scored alone. |
| 2026-11-04 | [Right on average, wrong in texture](articles/2026-11-04-session-texture.md) | Does a forgery that passes attempt by attempt hold up over a session? | No, unless it holds the full covariance: the correlations between keys expose a template forger (EER 0.01 over 50 attempts) and, less well, one who watched me (0.22 to 0.35). |

The input-path study that several of these draw on is written up in
[docs/09-STUDY-INPUT-PATH.md](../docs/09-STUDY-INPUT-PATH.md); its results are in
[results/2026-11-04-input-paths](results/2026-11-04-input-paths/).

## What the study found, by theme

### A rhythm is a credential, so it must be guarded like one

A forger holding my template reproduces my fixed-password rhythm well enough to be
accepted most of the time, and the attempt is labelled human, not automation
([stolen-rhythm](articles/2026-11-04-stolen-rhythm.md)). Three consequences went
into the design:

- The template is biometric and secret. It is now sealed at rest (AES-256-GCM,
  key in the keyring), which closes the "readable copy that leaves the machine"
  risk this study made concrete. See [docs/10-SECURITY-REVIEW.md](../docs/10-SECURITY-REVIEW.md)
  section 2.
- The behavioural score is never read alone. Provenance (how the input reached
  the machine) carries weight next to it, especially against a device wired
  between the keyboard and the machine.
- Over a session, texture helps: a forger drawing each timing on its own misses
  the correlations between keys and is caught over a window, but one holding the
  full covariance is not ([session-texture](articles/2026-11-04-session-texture.md)).
  Storing that covariance makes the template a better forging kit, which raises
  the stakes of sealing it.

### Hiding a rhythm is harder than adding noise

Jitter around your own rhythm leaves your rhythm in place; the standard tool
(kloak) is visible at its real default and only disappears at a delay too small to
help ([kloak](articles/2026-11-04-kloak.md),
[hiding-for-real](articles/2026-11-04-hiding-for-real.md)). For the engine this
separates two cues that are easy to confuse:

- **Re-timed input** deserves its own signal, distinct from **automated input**.
  The distance to my own template catches re-timing where a regularity test never
  would.
- A buffer replaying another rhythm looks human by construction; what gives it
  away is the lag structure, keys held back and released on a schedule that
  ignores mine. That is a signal to add next to E18.

### A remote hand leaves a mark in the timing

A long network path packs keys into near-simultaneous bursts, a signal that needs
no enrolment and is strongest where the risk is highest, a far-away operator
([remote-hand](articles/2026-11-04-remote-hand.md)). Two honest limits shape how
it is used:

- Under Wayland, remote-desktop input never reaches `evdev`, so there the right
  signals are the shell's (phantom activity, remote session active), not E11.
- A careful operator who smooths delivery erases the bursts; what remains is the
  distance to my template, as long as the path keeps adding jitter.

### Automation betrays itself through cadence, but not always

Fixed-cadence replay is caught as automation (82% at a 400 ms period), but the
slowest human donor becomes indistinguishable from chance once enough lag is
added; a median donor still leaks about a third of the signal
([input-paths study](../docs/09-STUDY-INPUT-PATH.md)). The lesson is to under-react:
automation is labelled, and only becomes an alarm when it meets identity
divergence or a sensitive action (ADR-0011).

## Open experiments

Carried forward from the articles above, in rough priority:

1. **Texture in free text**: how much of the correlation structure survives
   pooling by digraph class, and whether it holds as a live session signal.
2. **A careful remote operator** who smooths input: what is left beyond the
   template distance.
3. **A physical rig** between keyboard and machine, which adds its own timing
   noise the perfect-timing forger does not.
4. **Detecting the recorder going blind** (an `EVIOCGRAB` by another tool), which
   the kloak study found is currently silent.

## Reproducing a result

Each results folder carries its own `README.md` with the exact command. In short:

```bash
cd lab && python3 -m pytest        # the lab test suite, standard library only
# then the evaluation entry point named in the relevant results/ README
```

No result here needs my private data; the ones that would are marked indicative
and are not used to support a published claim.
