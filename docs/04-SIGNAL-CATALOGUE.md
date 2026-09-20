# 04 - Signal catalogue

> Covers FR-10 and FR-11. This is an **inventory of candidates**, not a specification: over a 60 s window most of these signals will not have enough observations to vote. The target is about **fifteen retained signals**, chosen by measurement in work package 4.

**Columns**:
- **Cost**: computational load (L low, M medium, H high).
- **Disc.**: expected discriminating power, from the state of the art or by reasoning (to be confirmed by measurement in work package 4; the values are hypotheses).
- **Forge**: how hard it is for an adversary to forge this signal, from 1 (easy) to 4 (very hard).
- **WP**: work package in which the signal is **studied**. Families A to D are studied in Python in work package 4; only the signals retained there are ported to the agent in work package 7.

---

## Family A - Keystroke dynamics

| ID | Signal | Definition | Cost | Disc. | Forge | WP |
|---|---|---|---|---|---|---|
| A01 | Hold time | Press to release duration, per key class | L | High | 2 | 4 |
| A02 | Flight time | Release to next press interval | L | High | 2 | 4 |
| A03 | DD latency | Press to next press | L | High | 2 | 4 |
| A04 | UU latency | Release to next release | L | Medium | 2 | 4 |
| A05 | Digraph latencies by **biomechanical class** | Latency statistics per class of key pair: same finger, same hand adjacent fingers, same hand distant, alternating hands, row change, modifier involved. The class is computed in memory from key positions; no key identity is kept (default level P1) | M | High | 3 | 4 |
| A05h | Hashed digraphs | Statistics per key pair, keyed by a hash with a per-installation secret (opt-in level P1h). Open to frequency analysis; kept as a comparison point | M | Very high | 3 | 4 |
| A06 | Trigraph latencies by biomechanical class | As A05, over triplets | M | High | 3 | 4 |
| A07 | Overlap | Negative flight: next key pressed before the previous one is released. Gives away dexterity and fingering | L | Very high | 4 | 4 |
| A08 | Typing speed | Characters per minute, sliding | L | Medium | 1 | 4 |
| A09 | Rhythm | Structure of bursts and pauses: burst length, pause duration | M | High | 3 | 4 |
| A10 | Correction rate | Share of backspaces and deletions | L | High | 3 | 4 |
| A11 | Correction depth | Number of characters erased per correction episode | L | High | 3 | 4 |
| A12 | Correction latency | Delay between the error and the start of the correction. Very personal: gives away proofreading speed | M | High | 4 | 4 |
| A13 | Shift preference | Left Shift versus right Shift for the same letter | L | Very high | 4 | 4 |
| A14 | Caps Lock versus Shift | Strategy for consecutive capitals | L | Medium | 3 | 4 |
| A15 | Modifier use | Frequency and combinations of Ctrl, Alt, Super, AltGr | L | Medium | 2 | 4 |
| A16 | Shortcut repertoire | Set of shortcuts used and their relative frequency | L | High | 3 | 4 |
| A17 | Keyboard versus mouse | Share of actions done by keyboard rather than mouse for the same function | L | High | 3 | 4 |
| A18 | Double letters | Cadence of consecutive repeated letters | L | Medium | 3 | 4 |
| A19 | Numeric keypad | Use of the keypad versus the digit row | L | High | 3 | 4 |
| A20 | Punctuation and spaces | Delays around spaces and punctuation, double space after full stop | M | Medium | 3 | 4 |
| A21 | Auto-repeat | Holding a key down to repeat, rather than successive presses | L | Medium | 3 | 4 |
| A22 | Inter-session stability | Variance of A01 to A05 from one session to the next. A regular user has low variance: a meta-signal | M | Medium | 4 | 4 |
| A23 | Left-hand / right-hand asymmetry | Ratio of hold times between the two halves of the keyboard | L | High | 4 | 4 |
| A24 | Fatigue effect | Drift of speed and error rate over a long session | H | Low | 4 | 4 |
| A25 | Composed input | Use of dead keys and accented characters, composition time | L | Medium | 3 | 4 |

## Family B - Pointer dynamics

| ID | Signal | Definition | Cost | Disc. | Forge | WP |
|---|---|---|---|---|---|---|
| B01 | Velocity | Distribution of velocities, per direction octant | L | High | 2 | 4 |
| B02 | Acceleration | Acceleration and deceleration profile per gesture | M | High | 3 | 4 |
| B03 | Jerk | Third derivative of position. Closely tied to fine motor control | M | High | 4 | 4 |
| B04 | Curvature | Mean and maximum curvature of the trajectory | M | High | 3 | 4 |
| B05 | Straightness | Ratio of distance travelled to direct distance | L | High | 3 | 4 |
| B06 | **Fitts's law** | Regression `T = a + b·log2(D/W+1)` over pointings. The pair `(a,b)` is a stable, cheap individual invariant | M | **Very high** | 4 | 4 |
| B07 | Overshoot | Amplitude and frequency of target overshoot | M | Very high | 4 | 4 |
| B08 | Micro-corrections | Number and amplitude of adjustments in the last 100 pixels | M | **Very high** | 4 | 4 |
| B09 | Pause before click | Delay between the cursor stopping and the click | L | High | 3 | 4 |
| B10 | Click duration | Button press to release time | L | High | 3 | 4 |
| B11 | Double-click interval | Delay between the two clicks, and cursor drift between them | L | Very high | 4 | 4 |
| B12 | Drag and drop | Speed, hesitations, drop precision | M | High | 3 | 4 |
| B13 | Wheel | Amplitude per notch, cadence, pauses, direction reversals | L | High | 3 | 4 |
| B14 | Scrolling style | Wheel versus scrollbar versus keyboard versus two-finger swipe | L | High | 3 | 4 |
| B15 | Approach angle | Preferred direction of arrival on targets. Gives away handedness and hand position | M | High | 4 | 4 |
| B16 | Drift at rest | Micro-movements of the cursor during pauses. Gives away physiological tremor | M | Very high | 4 | 4 |
| B17 | Parking zone | Position where the cursor is left at rest | L | Medium | 3 | 4 |
| B18 | Screen coverage | Heat map of positions, normalised | M | Medium | 2 | 4 |
| B19 | Transition speed | Time to cross between two distant screen zones | L | Medium | 3 | 4 |
| B20 | Pointing / scrolling ratio | Share of time spent pointing versus scrolling | L | Medium | 2 | 4 |
| B21 | Device signature | Effective resolution, sampling rate, presence of acceleration. Tells mouse, trackpad and trackball apart. **Mode detection only, never identity evidence**: an impostor at my desk uses my devices | L | n/a (mode) | 2 | 4 |
| B22 | Trackpad gestures | Number of fingers, swipe speed, pinch | M | High | 3 | 4 |
| B23 | Right-click / left-click ratio | And use of the context menu | L | Medium | 3 | 4 |
| B24 | Selection precision | Length and stability of drag selections | M | Medium | 3 | 4 |

## Family C - Application context

Reminder: categories and opaque identifiers only, never a title nor an executable name (FR-5).

| ID | Signal | Definition | Cost | Disc. | Forge | WP |
|---|---|---|---|---|---|---|
| C01 | Application repertoire | Set of categories used and their frequency | L | High | 2 | 4 |
| C02 | Markov chain of applications | Transition probabilities from one category to the next. Captures the habitual order of use | M | **Very high** | 3 | 4 |
| C03 | Opening sequence | Order of applications launched at the start of a session | L | Very high | 3 | 4 |
| C04 | Dwell time | Time spent per category and per visit | L | High | 2 | 4 |
| C05 | Switching cadence | Frequency of window changes | L | High | 3 | 4 |
| C06 | Number of windows | Distribution of the number of windows open at once | L | Medium | 2 | 4 |
| C07 | Virtual desktop use | Number of workspaces, frequency of changes | L | High | 3 | 4 |
| C08 | Terminal / graphical ratio | Preference for the command line | L | High | 3 | 4 |
| C09 | Command categories | Classes of shell commands (files, network, version control, containers), **never the arguments**. Feeds action sensitivity (FR-47) | M | High | 3 | 4 |
| C10 | Elevation cadence | Frequency of privilege requests. Feeds the **action-sensitivity** input (FR-47): unsanctioned automation that elevates is what lifts doubt | L | Medium | 3 | 4 |
| C11 | File navigation style | Tree depth, use of search versus browsing | M | Medium | 3 | 4 |
| C12 | Multitasking density | Entropy of the time split between applications | M | Medium | 3 | 4 |

## Family D - Temporal rhythm

| ID | Signal | Definition | Cost | Disc. | Forge | WP |
|---|---|---|---|---|---|---|
| D01 | Hourly profile | Distribution of activity over 24 hours | L | High | 2 | 4 |
| D02 | Weekly profile | Distribution over the 7 days | L | Medium | 2 | 4 |
| D03 | Session duration | Distribution of continuous activity durations | L | Medium | 2 | 4 |
| D04 | Pause structure | Distribution of intra-session inactivity durations | M | High | 3 | 4 |
| D05 | Start-up latency | Delay between unlocking and the first useful action | L | High | 3 | 4 |
| D06 | Warm-up rhythm | Evolution of typing speed over the first 5 minutes | M | High | 4 | 4 |
| D07 | Circadian regularity | Stability of the hourly profile from one day to the next | M | Medium | 3 | 4 |
| D08 | Locking cadence | Frequency and context of manual locks | L | Medium | 3 | 4 |

## Family E - Attribution: human or automation (Attribution channel)

**These signals require no enrolment** (FR-34). They tell human input from automated input. Automated is **not** the same as hostile: the label they produce is combined with the sanctioned-actor registry (FR-39) and, for doubt, with action sensitivity (family C), before anything is alarmed (ADR-0011). A developer's AI assistant or a user's MCP tools land here as `automation_sanctioned`.

| ID | Signal | Definition | Cost | Disc. | Forge | WP |
|---|---|---|---|---|---|---|
| E01 | **Device provenance** | Event coming from a virtual `uinput` device **not on the allowlist** learned at bootstrap (key remappers, gesture daemons and software KVMs are legitimate virtual devices). Blind to BadUSB, which is real hardware: see E19. On Windows, the `LLKHF_INJECTED` flag | L | High | 2 | 3 |
| E02 | Timestamp quantisation | Are delays multiples of a grid (1 ms, 10 ms, one video frame)? Signature of a programmed delay | L | Very high | 3 | 3 |
| E03 | Under-dispersion | Abnormally low coefficient of variation of intervals. A human never types with metronome regularity | L | High | 2 | 3 |
| E04 | Interval entropy | Entropy of the delay distribution, against the human reference | M | High | 2 | 3 |
| E05 | Sustained throughput | Bursts durably exceeding the plausible human maximum | L | High | 1 | 3 |
| E06 | No correction | Long output with no backspace at all | L | High | 2 | 3 |
| E07 | No overlap | A07 strictly zero on fast typing: physically unlikely for a fast human | L | Very high | 4 | 3 |
| E08 | Cursor teleportation | Position jump with no intermediate events | L | **Very high** | 4 | 3 |
| E09 | Ideal trajectory | Perfect straight line, or overly smooth Bézier curve, with near-zero jerk | M | Very high | 3 | 3 |
| E10 | No micro-corrections | B08 zero while targets are small: perfect pointing is non-human | M | **Very high** | 4 | 3 |
| E11 | Remote session timing signature | Bursts aligned on network latency, bimodal jitter, events grouped in packets. **Only where remote input reaches the capture layer** (X11, Windows, a RAT injecting through `uinput`). Under Wayland, remote-desktop input never reaches `evdev`: see E20 and E21 | M | High | 3 | 9 |
| E12 | Clipboard replay | Long, perfectly paced sequence, typical of a paste emitted as keystrokes by an IP KVM | L | Very high | 3 | 3 |
| E13 | Impossible order | Release without press, inconsistent modifier, physically unachievable event order | L | Very high | 4 | 3 |
| E14 | Cross-modal inconsistency | Plausible human typing but synthetic mouse, or the reverse | M | Very high | 4 | 3 |
| E15 | Application switching cadence | Switches between applications faster than human reaction time | L | High | 3 | 3 |
| E16 | No reading time | Action on newly displayed content with no plausible reading delay | M | High | 4 | 3 |
| E17 | Scroll step regularity | Scrolling in rigorously constant increments | L | High | 3 | 3 |
| E18 | Emission cadence signature | Cadence, jitter, tightness, robust percentiles, tail width over inter-key intervals, from the literature on HID injection detection | M | Very high | 3 | 3 |
| E19 | **Hot-plug then typing** | A keyboard that appears and starts typing at full speed within a second or two. The actual BadUSB signal | L | Very high | 3 | 3 |
| E20 | **Phantom activity** | The shell reports focus changes or window activity while no hardware input arrives. Signature of input injected into the compositor (remote desktop, portal-driven agent). Deterministic indicator, needs the shell extension | L | Very high | 4 | 3 |
| E21 | **Remote session active** | The compositor reports an active remote-desktop or screencast session. Deterministic indicator, needs the shell extension | L | Very high | 4 | 3 |
| E22 | **Sanctioned-actor match** | The segment matches the sanctioned-actor registry (a declared device pattern or an open agent session). Turns an automation label into `automation_sanctioned` (FR-39) | L | n/a (label) | n/a | 3 |

## Family F - Meta-signals

| ID | Signal | Definition | Cost | Disc. | Forge | WP |
|---|---|---|---|---|---|---|
| F01 | Change-point detection | Abrupt regime change on several signals at once (CUSUM or Page-Hinkley). A user handover produces a clean break, not a drift | M | **Very high** | 4 | 8 |
| F02 | Cross-modal consistency | Habitual correlation between modalities (does someone who types fast also point fast?). Broken during a partial takeover | M | High | 4 | 8 |
| F03 | Drift versus jump | A slowly evolving template is the same user; a jump is another user | M | High | 4 | 8 |
| F04 | Temporal interleaving | Do two regimes alternate within one session? Central discriminant between "mode" and "person" (cf. 03, section 6.1) | L | Very high | 4 | 8 |
| F05 | Service gap | Agent interruption followed by a restart with different behaviour (threat M11) | L | High | 4 | 3 |
| F06 | Drift versus anchor | Cumulative gap between the current template and the frozen enrolment template (threat M10) | L | Medium | 4 | 6 |
| F07 | Overall evidence quality | Amount of evidence available over the window. Used to tell "conforming" from "not enough information", which must never be confused | L | n/a | n/a | 5 |

## Family G - Mobile modalities (work package 10, in-app SDK)

| ID | Signal | Definition |
|---|---|---|
| G01 | Contact pressure | Force reported by the screen, per gesture type |
| G02 | Contact area | Size of the touch footprint, correlated with finger morphology |
| G03 | Tap duration | Contact time |
| G04 | Swipe speed and curvature | Touch equivalents of B01 and B04 |
| G05 | Swipe angle | Preferred direction, gives away the dominant hand |
| G06 | Strike position within the key | Systematic offset from the centre of virtual keyboard keys |
| G07 | Multi-touch | Frequency and type of multi-finger gestures |
| G08 | Device orientation | Distribution of holding angles (accelerometer, gyroscope) |
| G09 | Micro-tremor | Inertial signature during interaction |
| G10 | Reaction to the gesture | Device stabilisation after a tap |

---

## Cross-cutting rules

1. **No signal depends on content.** A signal that would require knowing the text, a URL or a file name is rejected by design (PR-1).
2. **Each signal exposes its quality** (FR-11). A signal without enough observations has zero weight; it does not "vote neutral": it does not vote.
3. **Each signal is measured before it is believed.** The "Disc." columns are hypotheses. Work package 4 produces the real values, and a signal whose measured discriminating power is zero is removed rather than kept out of comfort.
4. **Each signal has a privacy cost**, assessed and recorded in [05-PRIVACY.md](05-PRIVACY.md). A slightly discriminating but privacy-expensive signal is refused.
5. **Priority to the Humanity channel**: family E requires no enrolment, stores no personal template, and detects threats M2 to M5. It is the best value-to-risk ratio in the project, which is why it comes first, in work package 3.
6. **Hardware is not identity.** A signal that mostly encodes the device (sampling rate, key travel, sensor resolution) separates my machine from another one, not me from someone sitting at my desk. Work package 4 measures that sensitivity, and such signals are barred from identity evidence.
7. **Latencies live on a log scale.** Every latency signal is modelled on its logarithm.
