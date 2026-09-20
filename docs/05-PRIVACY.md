# 05 - Privacy, ethics and compliance

> Covers requirements PR-1 to PR-10. This document is authoritative: any collection not described here is a defect.

---

## 1. Position of principle

FidusAchates is a tool capable of reading everything typed on a keyboard. That is a dangerous power, owned rather than played down. The project therefore gives itself a rule that overrides all others:

> **Do not collect what can be inferred, and do not infer what is not needed.**

The goal of the project is to answer "is it the same person?". It is not to know what that person writes, reads, searches for or produces. Any feature that strays from that boundary is a defect to fix, not an evolution to discuss (PR-9).

## 2. What the tool never does

Binding list, to be checked in code review and by automated test:

- No typed content, in any form, including partial or reconstructible derivatives.
- No window title, executable name, file path, URL, search term.
- No clipboard content.
- No screenshot, no access to the camera or microphone.
- No geolocation, no network identifier (MAC address, IP, SSID).
- No civil identifier: name, account, e-mail address, serial number, hardware identifier.
- No outbound network connection, no telemetry, no remote crash report, no remote font or script.
- No measurement of productivity, attendance, presence or performance.
- No coercive action on the machine: no locking, no logout, no blocking.

The most important point in this list is the following: the absence of network is not a promise, it is a structural property, and the process enforces it **itself**. At start-up the agent sets `no_new_privs`, installs a seccomp filter that denies network sockets, then checks that opening one fails and refuses to run otherwise. It does not trust its unit file. `PrivateNetwork=yes` is a second layer where the system supports it: I verified that it works in a user unit on my machine, and it cannot be assumed everywhere (SR-3, INS-14).

## 3. Processing register

| Category | Data | Purpose | Basis | Retention | Location |
|---|---|---|---|---|---|
| Input timings | Monotonic timestamps, key classes, buttons | Signals A, B, E | Operation | 10 s memory buffer, not persisted | RAM |
| Biomechanical digraph classes | Motor class of a key pair (same finger, alternating hands, row change...), about twenty values | Signal A05 | Operation | Aggregated only | Encrypted SQLite |
| Hashed digraphs (opt-in P1h) | Hash of a key pair with a per-installation secret held in the keyring | Signal A05h | Operation, opt-in | Aggregated only | Encrypted SQLite |
| **Reduced event trace** (`research-trace` builds only) | Timestamp, event kind, key class, biomechanical class, pointer deltas, device index. Never a keycode | Replay, signal study | Research, on my machine | Until the study is published, then deleted | Trace files in the data directory |
| Window vectors | Signal values per activity window | Decision, clustering | Operation | 7 days | Encrypted SQLite |
| Aggregates | n, mean, M2, quantiles per signal, profile, mode | Templates | Operation | 90 days | Encrypted SQLite |
| Templates | Statistical parameters per profile | Decision | Operation | Life of the profile | Encrypted SQLite |
| Decisions | Timestamp, level, contributions | Explainability, audit | Operation | 90 days | Encrypted SQLite |
| Profile revisions | Merges, splits, justifications | Traceability | Operation | Permanent | Encrypted SQLite |
| Application context | Category (7 values) and opaque identifier | Signals C | Operation | 7 days | Encrypted SQLite |
| Health | CPU, memory, throughput | NFR compliance | Operation | 7 days | Encrypted SQLite |

No other data is written to disk. Any line added to this table must be added in the same commit as the code that produces it.

The reduced event trace deserves a word. Release builds persist no event at all, and do not even contain the code to do so. But evaluating a **new** signal by replay needs events, not window vectors, and a research project that cannot replay cannot measure. The trace is therefore a build-time feature, off by default. What it records is pointer movement and the **rhythm** of typing with motor classes; it cannot give back a single typed character. Pointer deltas are a behavioural signal in their own right and are covered by the same biometric qualification as the templates.

## 4. Legal qualification

### 4.1 Nature of the data

A behavioural template that makes it possible to tell an individual apart falls under the definition of **biometric data** (GDPR art. 4-14), and therefore under the regime of **article 9** (special categories). The CNIL explicitly places keystroke dynamics within behavioural biometrics and maintains that regime for authentication, including continuous authentication.

**Consequence: the project does not claim to produce anonymous data.** It produces pseudonymised, minimised and locally confined data. The claim "perfectly anonymous" would be false, and writing it would expose the project to a well-founded objection.

### 4.2 Current situation: personal use

In the present configuration, my personal machine and no third party observed, the processing falls under the **exemption for purely personal or household activity** (art. 2-2-c). No formality is required.

That exemption disappears as soon as one of the following holds:

- another person uses the machine and is observed;
- the tool is installed on a work machine;
- results are published from data concerning a third party;
- the tool is deployed on several machines.

### 4.3 Conditions to meet before any use involving a third party (PR-8)

| # | Condition |
|---|---|
| 1 | **Legal basis art. 9-2-a**: explicit, free, specific, informed, revocable consent, collected and logged before any collection |
| 2 | **Data protection impact assessment (DPIA)**: mandatory (biometrics, systematic monitoring). Template provided in `docs/dpia-template.md` |
| 3 | Complete **prior information**: purposes, data, durations, rights, recipients, absence of automated decision |
| 4 | **Effective right to object**: immediate stop and purge, with no consequence for the person |
| 5 | **In a work context**: consultation of staff representatives, and verification that monitoring is proportionate. Such a deployment is out of scope of the project |
| 6 | **Ethics committee** if the project leads to academic publication with human subjects |
| 7 | **No decision producing legal effects** may be based on the tool's output (art. 22) |

These conditions are repeated in the README so that they are seen before installation.

## 5. Technical protection

| Measure | Implementation | Requirement |
|---|---|---|
| Encryption at rest | Encrypted database, key in the system keyring, never on disk in clear | PR-4 |
| Reduction at capture | Key identity is reduced to classes inside the function that reads the event; no keycode reaches storage, logs or the trace | FR-3 |
| No raw events | A property of the schema, not a purge policy | FR-8 |
| Bounded retention | Daily automatic purge according to the register above | PR-5 |
| Total purge | `fidus-cli purge` erases database, templates and logs | FR-7, PR-5 |
| Immediate suspension | Global shortcut and CLI command, effective in under a second | FR-7 |
| Application blocklist | Capture suspended for listed applications, by default: password managers | FR-6 |
| Network isolation | Self-applied seccomp filter and start-up self-test; `PrivateNetwork=yes` as a second layer | INS-14, SR-3 |
| Local console | Bound to `127.0.0.1` only, `Host` and `Origin` checks, `SameSite=Strict` session, system re-authentication to open it | FR-50, SR-9, SR-10 |
| Irreversibility | No template allows an input sequence to be reconstructed | PR-10 |

### A limit I own, and do not hide

**Under Wayland there is no reliable way to detect that an input field is a password field.** At the default level this matters less than it sounds: what is kept about a password is its typing rhythm and motor classes, never its characters. The rhythm of a frequently typed password is nonetheless distinctive, so the application blocklist (FR-6) and manual suspension (FR-7) remain.

This limit appears in the README, above the installation instructions, and not in a footnote.

## 6. Granularity levels

| Level | What is kept | Intended use |
|---|---|---|
| **P0** | Key classes only | Cautious user, public demonstration |
| **P1** (default) | Key classes plus biomechanical digraph classes | Normal use of the project |
| **P1h** | Hashed digraphs, per-installation secret in the keyring | Opt-in comparison point; open to frequency analysis |
| **P2** | Keycodes in clear | **Dedicated test corpora only.** To be refused in real use. The mode shows a permanent warning in the console and in the overlay |

The active level is shown permanently in the console (FR-57).

## 7. Research ethics

1. **Consent before any subject.** No data from a third party is collected without their explicit prior agreement.
2. **Reciprocity.** Anyone observed has access to the console and can view, export and erase their own data.
3. **No surprise.** The tool is visible: declared service, status indicator, no discreet execution. A tool of this kind that hides is malware.
4. **Publishing failures.** Signals measured as non-discriminating are published just like the others. A signal catalogue containing only successes would be a biased catalogue.
5. **No use against a person.** Outputs are never used to sanction, grade or assess someone.
6. **Reversibility.** At any time: stop, purge, complete uninstallation in one command.

## 8. Risk of misuse

The project produces, in effect, a building block technically close to a keylogger and a monitoring tool. Denying it would be dishonest. The countermeasures retained:

- **Non-commercial licence**: limits industrial reuse without prior discussion.
- **No upload function**: there is no exfiltration code to reuse. Misuse requires writing it, which makes it another piece of software.
- **No invisibility function**: the tool does not know how to hide, and no contribution in that direction will be accepted.
- **No coercive action**: no locking or blocking to repurpose.
- **Up-front documentation**: this document is linked from the README, before the installation instructions.

## 9. What this document commits to

Every contribution must answer yes to the following four questions, failing which it is refused:

1. Does the collected data appear in the register of section 3?
2. Can the added signal be computed without knowing the content?
3. Does the purpose remain "is it the same person, is it a human"?
4. Would a user reading the code feel betrayed?
