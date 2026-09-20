# 07 - Design review

> A critical re-reading of documents 00 to 06 before any code is written. The point is to find what is wrong while it is still cheap to change.
>
> Nothing below is applied yet. Section A lists plain errors; sections B to D need a decision.

---

## A. Errors in the documents as written

### A1. The evidence sign is inconsistent and the level table is numerically wrong

[03-DECISION-ENGINE.md](03-DECISION-ENGINE.md) defines `e_i = 10·log10[P(x|genuine)/P(x|impostor)]`, so positive evidence **supports the legitimate user**, and gives `P(impostor) = 1/(1+10^(E/10))`. The same document then says that crossing the **upper** threshold `A` means "conclude impostor", and that level L3 starts at `E = 10 dB` with `P(impostor) = 0.50`.

Those statements cannot all be true. With the formula as written, `E = +10 dB` gives `P(impostor) = 0.09`, and `E = A = 19.8 dB` gives `0.01`: the engine would conclude "impostor" at the exact moment it is 99 % sure of the opposite.

Flipping the sign does not rescue the table either: `E = 10 dB` then gives `0.91`, not `0.50`. Working backwards, the boundaries at 5 dB and 10 dB match a hidden prior of about -10 dB, while the boundaries at `A` and `B` match no single prior at all.

The root cause is that I mixed two different things: **Wald thresholds**, which are statements about error rates, and a **posterior probability**, which needs a prior. The document never states a prior.

**Correction.** Define evidence as evidence *for the impostor hypothesis*, state the prior explicitly, and derive the displayed probability from both:

```
e_i          = 10·log10 [ P(x_i | impostor) / P(x_i | genuine) ]
posterior_dB = prior_dB + E
P(impostor)  = 1 / (1 + 10^(-posterior_dB / 10))
```

With a prior of -10 dB the overlay threshold `P = 0.50` stays at `E = 10 dB`, which is what I intended, and `P = 0.99` lands at `E = 30 dB`. Decision thresholds and displayed probability must then be specified separately, and the level table recomputed from the formula instead of written by hand.

### A2. A sequential test with forgetting is no longer Wald's test

ADR-0004 justifies the SPRT by its optimality: fewest observations for given error rates. But the engine also applies exponential forgetting to the cumulative evidence. The two do not combine:

- Wald's guarantees on `α` and `β` assume plain accumulation. With decay they no longer hold, so thresholds derived from `α` and `β` lose their meaning.
- With decay the cumulative evidence is **bounded**. For 60 s windows and a 15 min half-life the ceiling is about 22 times the mean evidence per window. An impostor yielding less than about 0.9 dB per window can **never** reach `A = 19.8 dB`, however long he stays.

More fundamentally, the SPRT answers "which of two hypotheses has held since the start?". My problem is different: the legitimate user is present, and at some **unknown moment** someone else takes over. That is change detection, and the standard tool is **CUSUM** (Page), which is optimal for detection delay at a fixed false alarm rate:

```
S_t = max(0, S_{t-1} + e_t)        alarm when S_t ≥ h
```

Three things make it a better fit than what I specified:

1. The reflecting barrier at zero replaces the half-life. One hard-to-tune parameter disappears, and genuine evidence accumulated over a long morning can no longer be "spent" by an impostor in the afternoon.
2. The threshold `h` is set from a target **average run length to false alarm**, which is exactly my primary metric ANGA. Expected detection delay is about `h` divided by the mean evidence per window under the impostor hypothesis, which is ANIA. The engine and the evaluation protocol finally speak the same language.
3. `S_t` is still a sum of per-signal contributions since the last reset, so exact explainability is preserved.

There is some irony in the catalogue listing CUSUM as meta-signal F01 while the engine itself uses the wrong tool.

What is lost: CUSUM has no "conclude genuine" outcome, which the adaptation admission filter relied on (`E ≤ B`). It needs restating, for instance as `S_t = 0` over several consecutive windows together with strongly genuine window-level evidence.

### A3. Under Wayland, remote sessions and portal-driven agents never reach evdev

The threat model claims RDP/VNC takeover (M5) is detected through "bursts aligned on network latency" in the input stream (signal E11), and the README lists RDP among what the Humanity channel detects.

On the target platform this is false. GNOME's remote desktop injects input through Mutter's own interface (libei); those events **never pass through `/dev/input`**. The same holds for any agent that drives the desktop through the RemoteDesktop portal. An evdev-based agent sees nothing at all: no timing to analyse, no device to flag. Only agents that inject through `uinput` (`ydotool`) are visible, as virtual devices.

So for M4 and M5 the evdev channel is not weak, it is blind. The detectable symptom is the opposite of what I wrote:

- **Phantom activity**: the shell extension reports focus changes and window activity while evdev reports no hardware input. This is very hard to forge from outside.
- **Remote session active**: Mutter exposes active remote-desktop and screencast sessions. The extension can report that directly, with no statistics involved.

Consequence: the GNOME Shell extension is **not optional** for M4 and M5. INS-25 can keep a degraded mode, but it has to say plainly that this mode is blind to remote takeover and portal-driven agents.

### A4. Rotating the digraph salt defeats its own purpose

ADR-0005 regenerates the salt at every start, so the hash of a given digraph changes every session. It then says the agent "persists only aggregates that have already been reconciled". Reconciled against what? To add today's observations of a digraph to yesterday's statistics, the persisted key must be stable across sessions. If it is stable, the rotating salt adds nothing. If it is not, nothing can accumulate. I wrote around the problem instead of solving it.

Two further weaknesses of the hashed scheme:

- A table of per-hash counts is open to **frequency analysis**. The most frequent digraphs of a language are well known, so the most frequent hashes can be identified by rank without ever knowing the salt. No text can be rebuilt, since no sequence is stored, but "unusable" was too strong a claim.
- With a small input space, a leaked salt makes the dictionary trivial.

**Proposed replacement for the default level: biomechanical digraph classes.** evdev key codes are positional, so at capture time, in memory, each key pair can be mapped to a class: same finger, same hand adjacent fingers, same hand distant, alternating hands, row change up or down, involving a modifier. That is fifteen to twenty classes. What gets persisted carries essentially no information about content, needs no salt, has no continuity problem, and captures exactly what makes digraph latencies personal: the motor pattern, not the letters. Hashed digraphs would remain as an opt-in level with a per-installation secret held in the keyring, and an honest description of the frequency attack.

This needs measuring: if biomechanical classes lose too much discriminating power against true digraphs, the trade-off has to be reopened.

### A5. The README states targets as if they were measurements

The README table gives "0 % CPU at rest, under 40 MB" in the present tense. Nothing is built; those are budgets. A project that commits to publishing its failures cannot present intentions as results. Reword as targets until work package 1 has measured them.

### A6. Network isolation: verified here, not guaranteed elsewhere

The central privacy claim rests on `PrivateNetwork=yes` in a `systemd --user` unit. User units cannot always create a network namespace, and some sandboxing directives are silently ignored for them, so I tested it on the target machine (systemd 259, unprivileged user namespaces enabled): the unit sees only `lo`. The claim holds **here**.

It will not hold on systems where unprivileged user namespaces are disabled or restricted. The agent therefore must not trust its unit file:

- **Self-test at start**: try to open an outbound socket; if it succeeds, refuse to run.
- **Self-applied seccomp filter** denying `socket()` for network address families. It needs no privilege, does not depend on systemd, and works on every distribution.

---

## B. Decisions to reopen

### B1. The `input` group exposes the whole session, not just this tool

ADR-0006 adds the user to the `input` group. That makes `/dev/input` readable by **every process running as that user**: a browser exploit, a malicious package post-install script, anything. The default logind model gives device access to the compositor alone; I would be removing a system-wide protection against keyloggers in order to install a security tool.

I dismissed the alternative in ADR-0006 with a bad argument ("the confinement gain is illusory since the created group would have exactly the same rights"). The rights are the same, but **the holder is not**: a dedicated service account, not the user and all his processes.

Alternative: a very small privileged helper, a system service running as a dedicated `fidus` account in the `input` group, that opens the devices and forwards only **already reduced** events (timestamp, key class, device) over a UNIX socket, checking the peer's credentials. The user never joins `input`. Cost: root at installation and a system service, which breaks INS-12.

On my own machine the account is already in `input`, so the marginal cost is nil. For anyone else it is real. **Proposal**: support both. "Simple" mode (group) documented as acceptable on a personal research machine only, with the exposure stated plainly; "hardened" mode (helper) as the recommended installation everywhere else. INS-12 and ADR-0006 to be rewritten accordingly.

### B2. Writing ninety extractors in Rust before knowing which signals matter

ADR-0001 puts the whole pipeline in Rust from work package 1. But which signals are worth keeping is precisely the *output* of the calibration package. Implementing, testing and optimising ninety extractors in Rust, to discard most of them later, is the expensive order.

**Proposal**: the Rust agent starts as a **recorder** only: capture, privacy reduction, trace writing. Small, stable, auditable. All feature extraction, experts and fusion live in Python, offline, until measurement has selected the useful signals. Only those get ported.

This exposes a contradiction I had not seen. FR-8 forbids persisting raw events; FR-71 demands replay. Replaying stored *window vectors* can re-run the fusion, but it cannot evaluate a **new signal**, which needs the events. Research replay requires reduced event traces. This has to be said openly: a `research-trace` build feature, off by default, absent from release builds, storing reduced events only (timestamp, class, biomechanical class, device), encrypted, used on my machine. FR-8 then applies to release builds, and the privacy register gains a line.

### B3. One global damping factor cannot correct heterogeneous correlations

The engine corrects the false independence assumption with a single factor `λ` applied to the whole sum. Correlation is not uniform: keyboard signals are strongly correlated with each other and hardly at all with mouse signals. One scalar over-damps some and under-damps others.

**Proposal**: linear logistic-regression fusion over the experts' LLRs, the standard method in speaker verification: `E = Σ w_i·e_i + b`, weights learned on development data. Redundant experts get small weights; calibration of the fused score comes with it. It is still linear, so the contribution of each signal remains exact and the explainability argument of ADR-0004 stands untouched.

### B4. The self-estimated EER of criterion C3 is biased by hardware

C3 estimates the EER against "a reference impostor population drawn from the public corpora". Those corpora were recorded on other keyboards, other mice, other operating systems, with other timer resolutions. Hardware and capture-stack differences dominate differences between people. The classifier will learn to tell *my keyboard* from *theirs* and report an excellent, meaningless EER.

The real impostor sits at **my** machine with **my** devices, where every hardware-correlated feature is worthless.

**Corrections**: use public corpora only for within-corpus experiments; state that the self-estimated figure is an optimistic bound; treat same-machine impostor sessions as the only honest measurement; and demote signals such as B21 (device signature) to mode detection, never identity evidence.

### B5. AC-1 cannot be measured by one person

AC-1 demands an EER under 5 % against human impostors, and my own protocol demands bootstrap confidence intervals **over subjects**. With the two or three consenting friends I can realistically recruit, that interval spans tens of points. I wrote a criterion I cannot verify.

**Proposal**: two explicit tiers. Statistical claims come from public corpora, where the number of subjects supports them. My own machine is a **case study**: detection delays per session, false alarm counts, no EER claim. AC-1 to be reworded; AC-4 (false alarms per 8 h) stays as is, being both measurable alone and the criterion that decides whether the tool gets kept.

### B6. Ninety signals is a liability

Over a 60 s window most of the ninety signals will have too few observations to vote. The catalogue is an inventory of candidates, not a specification. **Proposal**: an explicit parsimony target, at most about fifteen signals retained by greedy forward selection on fused performance.

### B7. Latencies are not Gaussian

The engine fits a Gaussian to robustly standardised values. Inter-key and pointing latencies are right-skewed, close to log-normal. A Gaussian on the raw scale produces wrong likelihood ratios in the tails, which is exactly where the evidence is. **Correction**: model log-latencies.

---

## C. Gaps

| # | Gap | Proposal |
|---|---|---|
| C1 | **E01 is overrated.** Legitimate software creates `uinput` devices all the time: key remappers, gesture daemons, software KVMs, game input layers, accessibility tools. And a BadUSB key is *real* hardware, so E01 does not see it at all. | Learn an allowlist of virtual devices during bootstrap; lower E01's forgery rating from 4 to 2; add **hot-plug then immediate typing** (a keyboard that appears and types at full speed within a second) as the actual BadUSB signal. |
| C2 | **No way for the legitimate user to say "it is me".** A new keyboard or an injured hand leaves the red square on for good, and the tool gets uninstalled. | Re-assurance through real system authentication, which labels the current regime as a new mode. It must require actual authentication: a simple "it's me" button would be the poisoning vector of threat M10. |
| C3 | **No ground truth in daily use**, so AC-4 cannot be computed. | Console action to mark an alert as true or false. |
| C4 | **The local console is attackable from the browser.** Any web page can target `127.0.0.1`: DNS rebinding, cross-site requests; a token in the URL leaks into history. | Strict `Host` and `Origin` checks, `SameSite=Strict` cookie instead of URL token, no CORS. |
| C5 | **The console helps the impostor** (threat M12): anyone at the keyboard can open it and read which signals give him away. | Require system re-authentication to open the console, at least in `silent` mode. |
| C6 | **Clearing the overlay without a timer.** INS-1 forbids timers, but an alert must clear when the impostor leaves and nobody types. | Clear on session lock and on idle, both delivered as logind events, so still no polling. |
| C7 | **Extension maintenance is a recurring cost.** GNOME ships a major version every six months and extensions break. | Budget it; keep the extension minimal; pin supported Shell versions. |
| C8 | **The legitimate user changing** (new hardware, injury, fatigue) is absent from the evaluation protocol. | Add a `legit-shift` trace. |

---

## D. Roadmap

Four problems with the current order:

1. **Circular dependency.** Work package 3 requires results "reproducible by replay", but replay arrives in work package 7.
2. **Data collection starts too late.** The calendar is dominated by the 30-day `legit-long` trace. Every week spent before recording starts is a week added to the end.
3. **The best-value feature is split.** The Humanity channel is spread over packages 1 and 5, and the overlay, the only thing that makes the project demonstrable, waits until package 6.
4. **Rust too early** (see B2).

**Proposed order**

| WP | Content | Why here |
|---|---|---|
| 1 | **Recorder**: minimal Rust capture, privacy reduction, reduced trace, CLI, installer, content-free test | Recording starts on day one; the component that reads `/dev/input` stays small enough to audit |
| 2 | **Lab**: Python replay, evaluation bench, corpus ingestion | Everything after this is measurable |
| 3 | **Humanity channel and overlay** | No enrolment needed, so a full demonstration within days: run `ydotool`, the red square appears |
| 4 | **Signal study** in Python: all candidates, measured, about fifteen retained | Decides what is worth porting |
| 5 | **Fusion, CUSUM, explainability, console** | |
| 6 | **Enrolment and convergence criteria** | Needs the 30-day trace, which has been recording since package 1 |
| 7 | **Port the retained signals to the Rust agent**, verify resource budgets | Rust effort spent only on what survived |
| 8 | Multiple profiles, modes, revision | |
| 9 | Other operating systems | |
| 10 | Mobile SDK | |

---

## E. What holds up

Not everything needs changing. After this pass I still stand by:

- **Additive log-likelihood fusion**, because it makes the explanation exact. B3 and A2 change how evidence is weighted and accumulated, not that principle.
- **Two separate channels**, Identity and Humanity, never blended.
- **Mode versus identity**, with temporal interleaving as the discriminant.
- **Convergence criteria instead of a duration** for enrolment, with C3 corrected as in B4.
- **No raw-event table** in release builds, and the privacy register as a contract.
- **Temporal cross-validation only**, confidence intervals mandatory, failures published.

---

## Summary

| # | Item | Kind | Touches |
|---|---|---|---|
| A1 | Evidence sign, explicit prior, recomputed level table | Error | 03, README |
| A2 | CUSUM instead of SPRT with forgetting | Error | 03, ADR-0004, 01 (FR-32) |
| A3 | Remote sessions invisible to evdev; phantom activity; extension required for M4/M5 | Error | 00, 04, 01 (INS-25), README |
| A4 | Biomechanical digraph classes as default; salt rotation dropped | Error | ADR-0005, 00 (T2), 05 |
| A5 | README targets worded as targets | Error | README |
| A6 | Start-up self-test and seccomp self-confinement | Hardening | 02, 01 (SR-3) |
| B1 | Hardened install mode with a dedicated capture helper | Decision | ADR-0006, 01 (INS-12) |
| B2 | Rust recorder first, Python for signals; `research-trace` feature | Decision | ADR-0001, 01 (FR-8, FR-71), 05 |
| B3 | Logistic-regression fusion instead of a global `λ` | Decision | 03, ADR-0004 |
| B4 | C3 no longer measured against foreign hardware | Decision | 03, protocol |
| B5 | AC-1 reworded; two evidence tiers | Decision | 01, protocol |
| B6 | Parsimony target on signals | Decision | 04, 06 |
| B7 | Log-latency modelling | Correction | 03 |
| C1-C8 | Gaps | Additions | 01, 04, protocol |
| D | Roadmap reordered | Decision | 06 |
