# 10 - Security and data-protection review

> Reviewed on 2026-11-04. Covers the repository, the data the live daemon keeps,
> the attack surface it exposes, and the position on being seen by security
> tooling. It complements [05-PRIVACY.md](05-PRIVACY.md) (what is collected and
> why) and [07-DESIGN-REVIEW.md](07-DESIGN-REVIEW.md) (design trade-offs). Where
> the two disagree, 05-PRIVACY is authoritative on collection and this document
> on protection.

---

## 0. Verdict

Nothing sensitive is committed to the repository. The data the tool keeps on the
machine is biometric and is treated as such: sealed at rest with a key that never
touches the disk in clear, under a threat model that is stated plainly rather
than oversold. The network isolation is a structural property enforced by the
process, not a promise. Three residual findings remain, all about the edges of
the at-rest sealing, and one operational point: the sealing code is not yet
committed, so the published tree does not have it.

| # | Finding | Severity | State |
|---|---|---|---|
| F1 | Cleartext fallback when no keyring is available is near-silent and not opt-in | Medium | Open |
| F2 | Today's trace and context stay in clear until the daily seal | Low | Accepted, documented |
| F3 | `cryptography` is an optional import; its absence must degrade, not crash | Low | To verify |
| F4 | At-rest sealing (`vault.py` and its wiring) is uncommitted and unpushed | Operational | Open |

---

## 1. Secrets and sensitive data in the repository

**Checked.** Every tracked file was scanned for credential patterns (API keys,
passwords, tokens, private-key headers, cloud-provider key formats), for personal
data (e-mail addresses, routable IP addresses, real user paths), and for
committed data or model files.

**Result.** Clean.

- Every hit on `secret`, `password` or `token` is legitimate: the password-input
  filter (`privacy.py`, `daemon.py`), the console's one-time login token built on
  Python's `secrets` module (`console.py`), the shell hook's list of credential
  commands (`contrib/shell/fidus-actions.bash`), and tests. No value is hardcoded.
- No e-mail, routable IP or real-user path outside the allowlisted
  `socold.github.io` and loopback.
- The only committed data files are `research/fixtures/sample.fidustr` (104 bytes,
  a synthetic record of one event of each kind, produced by
  `crates/fidus-core/examples/write_fixture.rs`, not real typing) and the
  `research/results/**/metrics.json` aggregates (acceptance rates, EER, seeds; no
  raw events). Neither carries biometric data or anything reconstructible.
- `.gitignore` already excludes `*.sqlite`, `*.fidustr`, `/data/`, `/traces/`,
  `research/datasets/*`, `research/results/*`, `.env`, `*.key`, `*.pem`. The
  committed fixture and metrics are the deliberate exceptions, re-added past the
  ignore.

No action required. The repository's privacy discipline holds in practice.

---

## 2. Data at rest

The live daemon keeps behavioural templates, reduced traces, focus context,
guest sessions, daily model snapshots and the pooled guest reference under
`~/.local/share/fidusachates/`. The register of every file is in
[05-PRIVACY.md](05-PRIVACY.md) section 3.

**What protects it.** `vault.py` seals with AES-256-GCM. The key is 32 random
bytes generated once and stored in the session keyring through libsecret
(`org.fidusachates.Vault`); it is never written to disk in clear. A sealed file
is `MAGIC || 12-byte nonce || ciphertext+tag`. Reading accepts plain files too,
so data written before sealing existed stays readable and is sealed on the next
write (`vault.reseal`, `storage.seal_file`). `model.json` and `population.json`
go through `vault.write_bytes` (`saved_model.py`); completed-day traces and old
guest sessions are sealed by the daemon; the directory is `0700` and every file
`0600`.

**Threat model, as stated in `vault.py` and endorsed here.** Sealing protects
copies of the data folder that leave the session: a backup, a file sync, a disk
image, another local account reading the directory. It does **not** protect
against a process running as the user while the session is unlocked, because such
a process can ask the keyring for the key exactly as the daemon does. That is an
inherent limit of any scheme where the running tool must read its own data; it is
not a gap to close but a boundary to state. On a machine whose `/home` is already
encrypted at the block level, sealing adds the copies that block encryption does
not follow.

### F1 - Cleartext fallback is near-silent and not opt-in (Medium)

When there is no keyring to ask (no session bus, a locked or absent keyring, no
libsecret), `keyring_key()` returns `None`, `vault.active()` is `None`, and
`write_bytes` writes **in clear**. The only signal is one line on stderr
(`daemon.py`: "no keyring key, templates and traces stay in clear"). The vault's
own docstring says the template "holds the means and spreads of my rhythm" and a
day of trace "holds every hold and gap it was fitted from" — data the stolen-rhythm
article shows is enough to impersonate the user. Writing that in clear should not
be a quiet default.

Recommendation, in order of preference:

1. Make clear persistence **opt-in**: without a key, refuse to persist and run
   from memory only, unless started with an explicit `--allow-clear-at-rest`.
2. Failing that, offer a **passphrase-derived key** (Argon2id) as a fallback when
   no keyring is present, so a headless session still seals.
3. At minimum, make the warning loud and durable: surface it in the console as a
   standing banner, not only on stderr, so the state is visible while it lasts.

### F2 - Today's files stay in clear until the daily seal (Low)

Today's trace and context are appended in clear and sealed only when the day rolls
over (`storage.py`: "Today's files stay plain while they are being appended to").
A backup taken mid-day captures up to a day of unsealed behavioural data. This is
a reasonable trade-off against sealing on every append, and it is documented.
Accepted. If it ever needs tightening, seal on daemon stop in addition to the
day boundary.

### F3 - `cryptography` is an optional import (Low)

`Vault.__init__` imports `cryptography` lazily. If the keyring returns a key but
`cryptography` is not installed, constructing the vault raises `ImportError`. The
daemon must treat that like "no key" (degrade to the F1 path and say so), never
crash or, worse, half-seal. To verify in `daemon.py` where the vault is
configured, and to cover with a test that simulates the missing dependency.

---

## 3. Data in motion

**No outbound network, enforced by the process.** At start-up the agent sets
`no_new_privs`, installs a seccomp filter that denies network sockets, then
checks that opening one fails and refuses to run otherwise (`crates/fidus-agent`,
[05-PRIVACY.md](05-PRIVACY.md) section 2). `PrivateNetwork=yes` in the user unit
is a second layer where supported. There is no telemetry, no crash reporting, no
remote asset. This is the strongest part of the design: the absence of network is
a structural property, not a configuration that can be turned off by editing a
unit file.

Nothing to change. The release-signing work in section 7 deliberately keeps
verification **offline by default** so it does not become the one thing that
reaches out.

---

## 4. Privacy reduction

The agent never keeps a key code. It drops every key event at the lock screen and
in the prompt that follows `sudo`, `passwd` or `ssh-keygen`, since even key
classes would leak a password's length and shape (`privacy.py`,
`SecretInputFilter`). The known, unfixable limit under Wayland is that a browser
password field cannot be told from any other field; protection there rests on the
application blocklist, the manual Monitoring switch, and the fact that no key code
is ever stored. This is correctly documented in the README and
[05-PRIVACY.md](05-PRIVACY.md) section 5, and backed by content-free and lockdown
tests in CI (`crates/fidus-agent/tests/content_free.rs`, `lockdown.rs`). No gap.

---

## 5. Attack surface

- **Local console**: binds `127.0.0.1` only, behind a one-time login token that
  re-arms on use (`console.py`); the page carries no secret, checked by test
  (`test_console.py`). Good. Confirm the bind is never `0.0.0.0` on any platform
  port.
- **UNIX socket / console link**: `0600`, in `$XDG_RUNTIME_DIR`. Good.
- **D-Bus to the GNOME extension**: carries focus category and overlay state, no
  content. In scope for the WP3 attack bench, still to be run.
- **Shell hook** (`contrib/shell/fidus-actions.bash`, ADR-0014): sends action
  **classes** only, never the command or its arguments, to a `0600` file in the
  runtime dir, read once and truncated past 1 MB. Good. The hook is the one piece
  a user pastes into their shell; keep it short enough to audit in one reading.
- **Path handling**: guest deletion rejects traversal (`test_daemon.py` checks
  `../../etc/passwd` is refused). Keep that property under test for every
  id-to-path mapping.

---

## 6. Permissions and least privilege

Runs as a normal user in the `input` group, no root. `no_new_privs` and seccomp
are set by the process itself. Data root `0700`, files `0600`, atomic writes
(`write_bytes` uses a temp file plus `os.replace`). This matches the stated
posture. The capture capability is the irreducible risk and is called out in the
README's first section; nothing here widens it.

---

## 7. Supply-chain integrity and proving legitimacy

The tool has the capabilities of a keylogger and asks to be trusted. A user, or a
tool acting for them, must be able to confirm that a given binary is the genuine
release and not a fork or a trojaned copy. The approach is **transparency, not
obscurity**: sign releases and publish what is needed to verify them offline.
Design and rollout are in [ADR-0015](adr/0015-release-signing-and-verification.md);
`scripts/verify-release.sh` is the offline verifier.

What a signature can and cannot prove is stated there and repeated here so it is
not overread: a verified signature proves the **distributed file** is genuine. It
does not, on its own, prove that the **running process** is unmodified — that
needs OS-level code signing and platform attestation, which the porting work
(WP10) brings on Windows and macOS and which Linux leaves to the packager. The
honest claim is "this file is the real FidusAchates", not "nothing on this machine
can lie about it".

---

## 8. Position on EDR, antivirus and detectability

FidusAchates must be **visible** to the security tools on a machine, not hidden
from them. A keystroke recorder engineered to evade EDR or antivirus is, in
mechanism, a covert keylogger regardless of intent, and the evasion is reusable
for exactly that. The project does the opposite:

- It declares what it is in the README and refuses to run without the input
  permission the OS grants openly (the `input` group on Linux; Input Monitoring
  on macOS; see WP10).
- It signs its releases so a security tool, an administrator or a user can
  **allowlist it by identity** (publisher, hash, signature) rather than by
  guessing.
- It keeps no network path, so there is nothing for egress monitoring to catch
  and nothing to hide.

The correct answer to "antivirus flags my behavioural tool" is code signing,
notarization and allowlisting — being known — not evasion. This position is
deliberate and is not open for a build-time flag that reverses it.

---

## Appendix - what was checked

- Tracked-file scan for secrets, PII and committed data (section 1).
- `vault.py`, `storage.py`, `saved_model.py` read for the at-rest path (section 2).
- Network enforcement and privacy filter read from the agent and lab (3, 4).
- Console, socket, D-Bus, shell hook and path handling surveyed (5).
- Permissions and write atomicity confirmed in `storage.py`/`vault.py` (6).

Not done here, and left to their own work packages: the WP3 attribution attack
bench, dynamic analysis of the running agent, and fuzzing of the trace reader.
