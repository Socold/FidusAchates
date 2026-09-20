# Contributing to FidusAchates

Research project, **source-available, commercial use prohibited** (see [LICENSE](LICENSE) and [ADR-0002](docs/adr/0002-noncommercial-licence.md)).

## Before proposing anything

Read [docs/05-PRIVACY.md](docs/05-PRIVACY.md). Every contribution must answer yes to the four questions of its section 9:

1. Does the collected data appear in the processing register?
2. Can the added signal be computed without knowing the content?
3. Does the purpose remain "is it the same person, is it a human"?
4. Would a user reading the code feel betrayed?

## Refused on principle

These contributions are refused whatever their technical quality:

- Capture of content, window titles, URLs, file names, the clipboard.
- Any outbound network from the agent, in any form.
- Any function allowing the agent's execution to be concealed.
- Coercive action on the machine (locking, blocking, logout).
- Productivity, presence or attendance metrics.
- Making granularity level P2 the default configuration.

## Adding a signal

1. Register it in [docs/04-SIGNAL-CATALOGUE.md](docs/04-SIGNAL-CATALOGUE.md) with its cost, its expected discriminating power and its forgery difficulty.
2. Check that it requires no data missing from the register in [docs/05-PRIVACY.md](docs/05-PRIVACY.md) section 3. If a piece of data is missing, it must be added to the register **in the same commit**.
3. Implement the `Expert` or `Extractor` trait: the fusion engine is not modified.
4. Provide a quality measure (FR-11).
5. Provide a unit test with a reference vector.
6. Measure its real discriminating power according to [research/EVALUATION-PROTOCOL.md](research/EVALUATION-PROTOCOL.md). **A signal whose measured discriminating power is zero is removed, not kept out of comfort.**

## Commits

- Messages in English, imperative mood, prefixed with the work package: `wp1: add rootless evdev reading`.
- No secret, key or token in the repository.
- Privacy tests are blocking: never bypass them nor mark them as skipped.

## Licensing of contributions

Since the project reserves commercial rights to its author, any outside contribution will need an explicit inbound licence. Open a discussion **before** submitting substantial work.
