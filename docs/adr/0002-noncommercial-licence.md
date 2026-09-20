# ADR-0002 - PolyForm Noncommercial rather than an OSI licence

- **Status**: accepted
- **Date**: 2024-11, licence applied 2026-02

## Context

I want to publish the project as open research, forbid commercial exploitation by third parties, and keep the option of making commercial use of it myself later.

## Problem

"Open source" in the sense of the Open Source Initiative forbids any field-of-use restriction (criterion 6 of the definition). A licence that forbids commercial use **is not open source**, however visible the code is. Using the term would be inaccurate and would expose the project to a well-founded objection.

## Options

1. **MIT or Apache-2.0**: genuinely open source, but allows commercial exploitation by third parties. Ruled out, contrary to what I want.
2. **AGPL-3.0**: open source, strongly constrains online services, but does not forbid commerce. Ruled out.
3. **CC BY-NC**: not designed for software, ambiguous on patents and source code. Ruled out.
4. **BUSL-1.1**: commercial restriction with automatic switch to a free licence on a set date. Solid, but forces choosing a switch date right now. Ruled out for that reason.
5. **PolyForm Noncommercial 1.0.0**: written by lawyers for software, clear wording, explicit definition of non-commercial uses (personal research, teaching, public bodies), patent licence included, existing SPDX identifier.

## Decision

Option 5: **PolyForm Noncommercial 1.0.0**, with a copyright header explicitly reserving commercial rights.

The repository consistently says "source-available" or "open research", **never "open source"**.

## Consequences

- The project will not appear in directories of open source tools, and some organisations will rule it out in practice.
- Outside contributions will need an explicit inbound licence so that I keep the freedom to relicense. To be handled in `CONTRIBUTING.md` at the time of the first outside contribution.
- Moving later to a commercial or free licence remains entirely open, since I hold all the rights.
