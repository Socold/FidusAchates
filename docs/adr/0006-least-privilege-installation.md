# ADR-0006 - Least privilege, rootless installation, event-driven execution

- **Status**: accepted
- **Date**: 2026-05

## Context

Three requirements hang together: the tool must be as **light** as possible, run **in the background** permanently without anyone thinking about it, and **not ask for privileges**. A tool that demands root, installs a system service or consumes continuously will not be kept, whatever its detection performance.

Yet the very function of the project requires reading every input of the session, which is a strong privilege. The two requirements collide head-on.

## Options for capture

1. **Root daemon**: simple, works everywhere, but claims the highest privilege permanently. Ruled out.
2. **Setuid binary or `CAP_DAC_OVERRIDE`**: permanent privilege attached to an executable, lasting attack surface. Ruled out.
3. **Dedicated `udev` rule plus application group**: avoids adding the user to the global `input` group, but requires dropping a file into `/etc/udev/rules.d`, hence modifying the system (contrary to INS-27), and the confinement gain is illusory since the created group would have exactly the same rights.
4. **User membership of the `input` group**: a single privileged operation, at installation, reversible in one command, no privilege at run time.

## Decision

Option 4, with four non-negotiable counterparts:

1. **No privilege at run time**: no root, no setuid, no capability, no kernel module, no system service. `systemd --user` only.
2. **Structural network isolation**: `PrivateNetwork=yes` on the capture process. It has no network access to give, even if compromised.
3. **Write confinement**: `ProtectSystem=strict`, write access limited to the data directory.
4. **One-command reversibility**, offered at uninstallation.

For execution, the decision is an **event-driven** agent: blocked on `epoll`, it consumes nothing in the absence of input. No polling loop, no periodic timer beyond capped maintenance. The console is started by socket activation and does not exist until it is opened.

## Rationale

The real cost of a resident tool is not measured by its consumption under load, but by its consumption **at rest**, because that is the state in which it spends almost all of its time. An event-driven agent is strictly at zero there. A polling agent, even at low frequency, keeps the processor out of its deep sleep states and is paid for in battery life on a laptop.

## Consequences

- Membership of the `input` group becomes a prerequisite checked by `fidus-cli doctor`, and stated before installation.
- **This permission is a strong privilege, and the project never presents it as harmless.** It allows every input of the session to be read. That is why the sources are published, the build is reproducible, and network isolation is structural rather than promised.
- The GNOME Shell extension becomes **optional**: without it the agent works, losing signal family C and the overlay. Installation must never fail for lack of the extension.
- Porting to Windows and macOS will have to reopen this decision: macOS requires an accessibility permission granted by the user, more visible but also broader.
- Maintenance triggered by event thresholds rather than by the clock slightly complicates the implementation. That is the price of INS-1 and INS-2.
