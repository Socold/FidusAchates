# FidusAchates GNOME Shell extension

Two jobs, and nothing else (architecture section 2.2):

1. **The indicator.** A small icon in the top bar, placed right of the clock
   wherever the clock sits (I look the clock up instead of assuming the default
   layout, since other extensions move it). It is always visible and shows one
   of four states, driven over D-Bus:
   - `off`: the daemon is not running (dim grey icon, no text);
   - `learning`: enrolment in progress, with its percentage, then how sure the
     engine is that I am the one typing once a window has been scored (grey,
     `34% · 91%`);
   - `recognized`: the current actor matches the enrolled user (green icon,
     with the same confidence, `91%`);
   - `alert`: a foreign actor is likely, shown as a red badge with the
     confidence (`72%`) when it exceeds 50 % (FR-60).

   It never takes focus and only reacts to a deliberate click (FR-61). The
   click opens a menu with the status line, the confidence line, a
   **Monitoring** switch and **Open console**. The switch runs
   `systemctl --user start|stop fidusachates.service`: off stops the recorder
   for this session; the service is still enabled, so it starts again at the
   next login.
2. **Context, content-free.** Exposes the *category* of the focused application
   (browser, terminal, development, office, communication, media, other) and a
   bare activity tick on focus change, so the agent can notice window activity
   that has no hardware input behind it (phantom activity, E20). Never a window
   title, never an executable name (FR-5).

## D-Bus interface

`org.fidusachates.Overlay` at `/org/fidusachates/Overlay`:

- `SetStatus(s state, u percent)`: set the state (`off`, `learning`,
  `recognized`, `alert`; anything else is treated as `off`) and its percentage.
- `SetIndicator(s state, u percent, i confidence)`: as `SetStatus`, plus the
  confidence that the person at the keyboard is me, in percent (`-1`: no
  score yet). The daemon uses this one and falls back to `SetStatus` when the
  loaded extension predates it.
- `SetConfidence(u percent, s channel)`: above 50, switch to `alert` with that
  percentage; at or below 50, return to the last non-alert state. Kept so the
  replay console keeps working unchanged.
- `Clear()`: leave `alert` and return to the last non-alert state.
- `GetContext() -> (s category, b remote_active)`: the focused category and
  whether a remote session is active (the latter is a best-effort placeholder
  for now).
- signal `ActivityTick(s category)`: emitted on focus change.

**Heartbeat.** The daemon calls `SetIndicator` about every 30 s. With no
`SetIndicator`, `SetStatus` or `SetConfidence` call for 90 s, the indicator falls back to `off`,
so it never keeps claiming a state the daemon is no longer there to back.

**Console link.** **Open console** reads one line from
`$XDG_RUNTIME_DIR/fidusachates/console-link`, a one-time login link that the
daemon writes (mode 0600) and rewrites after each use. Only a link starting with
`http://127.0.0.1:` is opened; otherwise the item reads "Console not running".

## Install

    cp -r fidusachates@socold.github.io ~/.local/share/gnome-shell/extensions/

Then **log out and back in** (GNOME does not reload a changed extension live on
Wayland), and enable it:

    gnome-extensions enable fidusachates@socold.github.io

## Smoke test, once enabled

    # learning, 34 %
    gdbus call --session -d org.fidusachates.Overlay \
      -o /org/fidusachates/Overlay \
      -m org.fidusachates.Overlay.SetStatus learning 34

    # a 72 % alert on the Identity channel
    gdbus call --session -d org.fidusachates.Overlay \
      -o /org/fidusachates/Overlay \
      -m org.fidusachates.Overlay.SetConfidence 72 Identity

    # back to the previous state
    gdbus call --session -d org.fidusachates.Overlay \
      -o /org/fidusachates/Overlay -m org.fidusachates.Overlay.Clear

    # read the focused application category
    gdbus call --session -d org.fidusachates.Overlay \
      -o /org/fidusachates/Overlay -m org.fidusachates.Overlay.GetContext

I test it without touching my session in a headless shell with its own bus and
data directories:

    XDG_DATA_HOME=... XDG_CONFIG_HOME=... XDG_RUNTIME_DIR=/tmp/short \
      dbus-run-session -- gnome-shell --headless --virtual-monitor 1280x800 \
      --wayland --unsafe-mode

The console (`python -m fidus_lab.console_main <trace> --open`) drives
`SetConfidence` automatically.
