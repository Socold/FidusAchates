# 00 - Preliminary analysis and state of the art

> Analysis notes. They come before the [requirements](01-REQUIREMENTS.md) and justify them.

---

## 1. Restating the problem

What I am trying to build goes, in academic terms, by the following name:

> **Multimodal implicit continuous authentication through behavioural biometrics, local, explainable, with unsupervised estimation of the number of distinct users and detection of non-human input.**

Four distinct questions hide behind it, and they do not have the same technical answers:

| # | Question | Nature | Difficulty |
|---|---|---|---|
| Q1 | *Is this still the same person who opened the session?* | 1:1 verification against a template | Moderate, well covered in the literature |
| Q2 | *How many different people use this machine?* | Unsupervised clustering, unknown number of classes | High, poorly covered |
| Q3 | *Does the input come from a human, or from an automaton, an AI agent, a RAT?* | Anomaly detection without enrolment | Moderate, highly discriminating |
| Q4 | *Why did the system reach that conclusion?* | Explainability | Structural, to be handled in the architecture of the engine |

These four questions structure the whole project. Q3 is the most useful in operational security and the cheapest in privacy terms: it requires **no** personal template. Q4 is not a cosmetic layer added at the end: it forces a choice of decision engine (additive fusion of log-likelihoods) that has to be made from the start.

---

## 2. Tensions identified

Six contradictions or impossibilities sit inside the problem statement. Naming them now avoids building on a false assumption.

### T1. "Perfectly anonymous" does not hold in the strict sense

The GDPR (art. 4-14) defines biometric data as *"personal data resulting from specific technical processing relating to the physical, physiological or **behavioural** characteristics of a natural person, which allow or confirm the unique identification of that natural person"*. The CNIL explicitly places keystroke dynamics within behavioural biometrics, and considers that biometric authentication falls under the sensitive-data regime (art. 9), including continuous authentication.

In other words: **a tool whose very function is to tell one user from another produces biometric data by construction.** A behavioural template is not anonymous, it is pseudonymised at best.

**Decision.** I drop the word "anonymous" and replace it with three verifiable commitments, stronger in practice than the label:

- **Content-free**: no typed content is captured, stored or reconstructible (no text, URL, file name, or window title in clear).
- **Identity-free**: no civil identifier, account, e-mail, MAC address, serial number. Profiles are opaque labels (`profile-a1b2`).
- **Local-first**: no outbound network, no telemetry, no third-party call. The machine is the only place where processing happens.

On top of that come minimisation (aggregates rather than events), encryption of the template at rest, and purging by default.

Legal frame for the project in its current phase: strictly personal use on a test machine, which falls under the household exemption (art. 2-2-c). **As soon as a third party is observed, or an organisational deployment is considered, a legal basis under art. 9-2-a (explicit consent) and a DPIA are required.** This is written down in [05-PRIVACY.md](05-PRIVACY.md).

### T2. Keystroke dynamics versus zero key logging

The best keyboard discriminants are **per-digraph** latencies (`t-h`, `e-r`): they presuppose knowing *which* keys were pressed. But capturing the identity of keys is a keylogger.

**Decision: three levels of granularity, P1 by default.**

| Level | What is kept | Discriminating power | Text reconstruction |
|---|---|---|---|
| **P0** (paranoid) | Key class only (letter / digit / space / correction / modifier / navigation) plus timings | Good | Impossible |
| **P1** (default) | **Hashed** digraph: `HMAC(volatile_salt, keycode_1 ‖ keycode_2)` truncated to 32 bits, aggregated online | Very good | Impossible without the salt, which is never persisted and rotates every session |
| **P2** (research) | Keycodes in clear | Reference | Possible: **reserved for dedicated test corpora, never in real use** |

Salted hashing keeps the ability to compute a mean and a deviation per digraph (which is what the model needs) while making the reverse dictionary useless from one session to the next. A rotating salt forces the statistics to be re-anchored: the agent therefore keeps a lookup table in volatile memory only, and persists aggregates alone.

**Additional safeguards**: no ordered sequence longer than 2 keys is persisted, online aggregation (Welford's algorithm) without keeping raw events beyond a ring buffer of a few seconds, and capture stops on an application blocklist (password manager, private browsing, terminal if desired).

**Honest limit to document**: under Wayland there is no reliable way to know that an input field is a password field. Protection therefore rests on the application blocklist, an immediate pause shortcut, and purging. This belongs in the README, not in a footnote.

### T3. "As light as possible" versus "fine-grained detection"

Without a numeric budget this requirement is not testable. I turn it into ceilings measured continuously and shown in the console (see NFR-1 to NFR-5): less than 1 % average CPU, less than 40 MB resident memory for the agent, less than 2 MB of storage per day of heavy use, decision latency under 250 ms.

The architectural consequence is direct: **stream processing**, incremental aggregates, no raw-event storage beyond a hot buffer, no deep neural network online in the first work packages.

### T4. Constraints of the test machine: GNOME on Wayland

Verified on the target machine (Fedora, GNOME, Wayland session, user in the `input` group):

- **Global keyboard and mouse capture**: impossible through desktop APIs (Wayland isolates applications). **Possible through `/dev/input/event*` (evdev)**, and membership of the `input` group makes that access available without root. This is the route I take.
- **Active window / foreground application**: not reachable from an ordinary process under GNOME Wayland. It needs a **GNOME Shell extension** exposing the category of the focused application over D-Bus.
- **On-screen overlay (the red square)**: `gtk-layer-shell` is not supported by Mutter. The overlay therefore also has to go through the GNOME Shell extension.

So the GNOME Shell extension is not a convenience: it is a required component, for two functions.

**Security consequence to own**: reading `/dev/input` grants the same capabilities as a keylogger. That requires the code to be auditable (hence publishing the sources), the binary to be reproducible, and the no-exfiltration guarantees to be verifiable (no network dependency whatsoever in the agent, tested in CI).

### T5. The red square warns the attacker

Displaying a suspicion indicator tells the impostor he has been detected and lets him iterate until he slips under the threshold. That is acceptable, and desirable, for a research bench (it is the visual feedback that makes the project demonstrable), but it would be a fault in a real deployment.

**Decision**: two explicit modes, `research` (visible overlay, the one I use on my machine) and `silent` (logging only, no visual feedback). The mode lives in the configuration and is shown in the console.

### T6. The mobile scope is not the desktop scope

On iOS and on non-rooted Android, global capture of interactions is forbidden by the sandbox. Only three routes exist:

1. **SDK embedded in an application**: only the inside of that application is observed (this is what BioCatch, TypingDNA and BehavioSec do). Route retained for later.
2. **Custom IME keyboard**: covers typing system-wide, but an IME sees the text in clear, which contradicts T1 head-on.
3. **Android accessibility service**: highly intrusive, and rejected by app-store policies outside genuine accessibility use.

**Decision**: work package 9, in-app SDK (route 1), with touch and inertial modalities. Routes 2 and 3 are explicitly out of scope.

---

## 3. State of the art

### 3.1 Keystroke dynamics

The oldest and best documented modality. The recent reference survey is *Keystroke Dynamics: Concepts, Techniques, and Applications* (ACM Computing Surveys, 2025).

- **Fixed text**: the reference benchmark is the CMU dataset by Killourhy and Maxion (51 subjects, 8 sessions at least a day apart, password `.tie5Roanl`, 400 vectors per subject). The best simple detector on it is the **scaled Manhattan distance**, with an EER of about **0.096**. More recent metrics get down to 0.087. That order of magnitude (10 %) is the yardstick to keep in mind for a *single* decision.
- **Free text** (my case): the work of Gunetti and Picardi (R and A measures over shared n-graphs) remains the conceptual basis. The relevant datasets are Clarkson II, Buffalo and the Aalto corpus (136 million keystrokes).
- **Key lesson for this project**: a 10 % EER on *one* isolated decision becomes excellent once decisions are accumulated over time. That is the whole point of sequential decision making (see 3.5).

### 3.2 Mouse dynamics

- Founding work: Ahmed and Traore (2007), on velocity curves by direction.
- Datasets: **Balabit Mouse Dynamics Challenge** (2016, 10 users doing administration tasks, first public corpus), **SapiMouse**, **DFL**.
- State of the art 2025-2026: AUC/EER of about **99.45 % / 2.87 %** on Balabit and **99.10 % / 3.14 %** on SapiMouse, against 13 % to 7.5 % for earlier work. Simpler approaches (2D CNN on trajectories) reach about 7.9 % EER.
- **Key lesson**: the mouse is at least as discriminating as the keyboard, and it is available in contexts where nobody is typing. It is indispensable for continuous coverage.
- **Under-used and cheap signal**: **Fitts's law**. A user's pointing time follows `T = a + b·log2(D/W + 1)`. The pair `(a, b)`, estimated by regression over pointing movements, is a remarkably stable individual invariant and very cheap to compute. I keep it as a first-rank signal.

### 3.3 Touch and inertial modalities (mobile)

- **Touchalytics** (Frank et al., 2013): 30 swipe features, the historical reference.
- **HMOG**: combines hand movement, orientation and grasp, with the inertial sensors.
- **BB-MAS**: multi-device corpus.
- Relevant for work package 9 only.

### 3.4 Detecting synthetic input, automata and takeover

This is the most directly "security" part, and the most cost-effective.

- **QUACK!** (arXiv 2604.15845): a systematic study of keystroke dynamics for HID injection detection, with a conclusion that is structuring for me: *robust detection is possible with lightweight timing models, without user enrolment and without access to content*. That is exactly the property I want for Q3.
- **Injection detection through IP KVM**: timing signatures (cadence, jitter, tightness, robust percentiles, tail width, throughput) computed over inter-key intervals flagged 365 clipboard replay sessions out of 365, with no false positive over 20 human sessions.
- **BadUSB / Rubber Ducky attacks**: detectable through log analysis and timing regularity.
- **Warning from the literature, to build into the design**: heuristics based on speed alone or regularity alone **can be evaded** by slowing down and randomising delays. Signals that are structurally harder to forge are therefore needed: device provenance (real hardware versus `uinput`), timestamp quantisation on a grid, absence of micro-corrections, cross-modal consistency, and physical impossibilities (inconsistent key overlap, cursor teleportation).
- **Robustness against synthetic forgeries**: keystroke dynamics remains attackable by generators trained on aggregate statistics (Stefan et al., 2010; Serwadda and Phoha). To be treated as a threat model, not ignored.

### 3.5 Fusion and sequential decision

- *A Comprehensive Overview of Biometric Fusion* (arXiv 1902.02919): overview of fusion levels. **Score** level is the right trade-off here.
- Continuous authentication systems classically use a **dynamic trust model**: a trust score that rises when behaviour conforms and falls otherwise.
- Sequential implementations compute a **log-likelihood ratio (LLR)** per interaction turn, accumulate it and compare it to two thresholds derived from **Wald's sequential probability ratio test (SPRT)**.

**This is the direct answer to the requirement "able to say very quickly that it is not him".** Under its assumptions, the SPRT is the procedure that minimises the number of observations needed to reach target error rates. I retain it as the core of the decision engine. A decisive side benefit: the LLR is **additive**, so the contribution of each signal to the decision can be decomposed exactly. **Explainability (Q4) becomes a property of the model and not an after-the-fact approximation.**

### 3.6 Estimating the number of users

A question little addressed in the authentication literature (which assumes identity is known). It belongs to clustering with an unknown number of classes: **Dirichlet process** mixture models, or truncated Bayesian Gaussian mixtures, with retrospective revision of the partitions.

The behaviour I want, first believing in several users and then understanding through cross-checking that there are only one or two, corresponds precisely to a **component merging** procedure tested by likelihood ratio. See [03-DECISION-ENGINE.md](03-DECISION-ENGINE.md), section 6.

**Main trap, to be handled explicitly**: one and the same individual produces several behavioural **regimes** (laptop keyboard versus external keyboard, right hand versus trackpad, morning versus late evening, rested versus tired). Without a distinction between *regime* and *identity*, the system will systematically count too many users. The model therefore has to be **hierarchical**: identity, then modes.

### 3.7 Existing tools and products

| Category | Examples | What I take from it |
|---|---|---|
| Commercial behavioural biometrics | BioCatch, BehavioSec (LexisNexis), TypingDNA, Plurilock | Mainly targets banking fraud and remote access; closed, unexplainable models, server-side processing |
| Enterprise UEBA | Exabeam (covers AI agent behaviour since January 2026), Securonix, Microsoft Defender for Identity | Reasons over application and network logs, not over physical interaction; too coarse for Q1 |
| Open UEBA | OpenUBA, CyberSentinel-UEBA, Wazuh | Good inspiration for correlation and dashboards; none handles local behavioural biometrics |
| Academic research | CMU, Balabit, SapiMouse, HMOG, Clarkson II corpora | Provide the comparable evaluation base, indispensable for publishing credible results |

**FidusAchates niche** (what does not already exist in the open):

1. A **local-first**, deliberately **content-free** agent, with no server, auditable.
2. A decision that is **explainable by construction** (additive LLR, contributions in decibans).
3. **Unsupervised estimation of the number of users**, with visible retrospective revision.
4. Joint handling of both threats: **human impostor** and **automated driving** (AI agent, RAT, HID injection).
5. A **deterministic replay** bench to compare models on real traces without collecting again.

### 3.8 Standards to anchor to

- **ISO/IEC 19795**: biometric performance testing methodology (FAR/FRR/EER vocabulary, protocols).
- **ISO/IEC 24745**: biometric template protection (irreversibility, unlinkability, revocability).
- **ISO/IEC 30107**: presentation attack detection.
- **NIST SP 800-63B**: authentication assurance levels, session reauthentication.
- **MITRE ATT&CK**: T1078 (valid accounts) and T1219 (remote access tools) on the detected-threats side; T1056.001 (input capture) on the side of the risk the tool itself represents.

---

## 4. Threat model

What the tool tries to detect, by increasing difficulty:

| # | Scenario | Expected signals | Difficulty |
|---|---|---|---|
| M1 | Machine left unlocked, someone uses it | All modalities diverge at once | Low |
| M2 | HID injection (BadUSB, Rubber Ducky, IP KVM) | Abnormal regularity, throughput, device provenance | Low |
| M3 | Local automation (`ydotool`, `xdotool`, test robot) | `uinput` provenance, timestamp quantisation, ideal trajectories | Low |
| M4 | AI agent driving the machine | As M3, plus no micro-corrections and atypical application sequences | Low to moderate |
| M5 | Remote takeover (RDP, VNC, RAT) | Bursts aligned on network latency, network jitter, no intermediate mouse events | Moderate |
| M6 | Uninformed human impostor | Progressive multimodal divergence | Moderate |
| M7 | Human impostor who has observed the victim | Divergence on involuntary signals (Fitts, micro-corrections, rare digraphs) | High |
| M8 | Synthetic forgery trained on the template statistics | Cross-modal consistency, second-order signals | Very high |

Threats **against the tool itself**, to be handled in [01-REQUIREMENTS.md](01-REQUIREMENTS.md) section SR:

- M9: theft of the template database (encrypt at rest, key in the system keyring).
- M10: template poisoning through slow adaptation by an impostor (*drift hijacking*).
- M11: silent shutdown of the agent by the attacker (detect and log the service gap).
- M12: access to the local administration console by the impostor himself.

---

## 5. Assumptions

They are explicit because everything else depends on them. If one is false, the requirements must be revised.

- **H1**: the test machine is my personal machine, I am its legitimate user, no third party is observed on it without knowing.
- **H2**: the target machine runs Fedora / GNOME / Wayland, my account belongs to the `input` group, and that access will remain available.
- **H3**: phase 1 aims at research and demonstration, not at production deployment nor at a fleet.
- **H4**: a non-zero false alarm rate is acceptable in the research phase, provided it is measured and displayed.
- **H5**: I accept running, continuously, a process that reads `/dev/input`, and I understand what that implies.
- **H6**: collected data stays on the machine and feeds no automated decision producing legal effects.

---

## 6. Sources

- [Keystroke Dynamics: Concepts, Techniques, and Applications (ACM Computing Surveys)](https://dl.acm.org/doi/full/10.1145/3733103) and its [arXiv version](https://arxiv.org/html/2303.04605v2)
- [Robust Keystroke Biometric Anomaly Detection (arXiv)](https://arxiv.org/pdf/1606.09075)
- [Distinguishability of keystroke dynamic template (PLOS One)](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0261291)
- [Optimizing Mouse Dynamics for User Authentication by Machine Learning (arXiv 2504.21415)](https://arxiv.org/html/2504.21415v1)
- [From Clicks to Security: Investigating Continuous Authentication via Mouse Dynamics (arXiv 2403.03828)](https://arxiv.org/pdf/2403.03828)
- [Machine and Deep Learning Applications to Mouse Dynamics (arXiv 2205.13646)](https://arxiv.org/pdf/2205.13646)
- [User identity authentication via spatiotemporal mouse dynamics modeling (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1389128626005141)
- [QUACK! A Systematic Study of Keystroke Dynamics for HID Injection Detection (arXiv 2604.15845)](https://arxiv.org/abs/2604.15845)
- [Detecting HID Keystroke Injection in IP KVM Clipboard Workflows Using Timing Signatures (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443044)
- [Forensic Log Based Detection For Keystroke Injection BadUSB Attacks (arXiv 2302.04541)](https://arxiv.org/pdf/2302.04541)
- [Keystroke-Dynamics Authentication Against Synthetic Forgeries (UCSD)](https://cseweb.ucsd.edu/~dstefan/pubs/stefan:2010:keystroke.pdf)
- [Robustness of keystroke-dynamics based biometrics against synthetic forgeries (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0167404811001179)
- [A Comprehensive Overview of Biometric Fusion (arXiv 1902.02919)](https://arxiv.org/pdf/1902.02919)
- [Continuous User Authentication Using Machine Learning and Multi-Finger Mobile Touch Dynamics (arXiv 2207.13648)](https://arxiv.org/pdf/2207.13648)
- [Continuous Authentication Using Mouse Movements, Machine Learning, and Minecraft (arXiv 2110.11080)](https://arxiv.org/pdf/2110.11080)
- [Design and Implementation of Continuous Authentication Mechanism Based on Multimodal Fusion (Wiley)](https://onlinelibrary.wiley.com/doi/10.1155/2021/6669429)
- [GitHub Topics: user-behavior-analytics](https://github.com/topics/user-behavior-analytics)
- [CyberSentinel-UEBA](https://github.com/AdityaUmathe/CyberSentinel-UEBA)
- [Top Open Source UEBA Tools (AIMultiple)](https://aimultiple.com/open-source-ueba)
- [CNIL: Biometrics](https://www.cnil.fr/fr/biometrie) and [Q&A on the biometrics model regulation](https://www.cnil.fr/fr/question-reponses-sur-le-reglement-type-biometrie)
- [CNIL: Biometrics available to individuals](https://www.cnil.fr/fr/biometrie-disposition-de-particuliers-quels-sont-les-principes-respecter)
- [CNIL: Practical GDPR guide on personal data security (PDF)](https://www.cnil.fr/sites/cnil/files/atoms/files/cnil_guide_securite_des_donnees_personnelles-2023.pdf)
