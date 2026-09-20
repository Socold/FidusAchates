# FidusAchates GNOME Shell extension

Two jobs, and nothing else (architecture section 2.2):

1. **The red square.** Drawn at the top right, shown only when the confidence
   that the actor is foreign exceeds 50 % (FR-60), driven over D-Bus. It never
   takes focus and never intercepts a click (FR-61).
2. **Context, content-free.** Exposes the *category* of the focused application
   (browser, terminal, development, office, communication, media, other) and a
   bare activity tick on focus change, so the agent can notice window activity
   that has no hardware input behind it (phantom activity, E20). Never a window
   title, never an executable name (FR-5).

## D-Bus interface

`org.fidusachates.Overlay` at `/org/fidusachates/Overlay`:

- `SetConfidence(u percent, s channel)` — show the square with the percentage if
  above 50, hide it otherwise.
- `Clear()` — hide the square.
- `GetContext() -> (s category, b remote_active)` — the focused category and
  whether a remote session is active (the latter is a best-effort placeholder
  for now).
- signal `ActivityTick(s category)` — emitted on focus change.

## Install

    cp -r fidusachates@socold.github.io ~/.local/share/gnome-shell/extensions/

Then **log out and back in** (GNOME does not rescan the extensions directory
live on Wayland), and enable it:

    gnome-extensions enable fidusachates@socold.github.io

## Smoke test, once enabled

    # show a 72% red square on the Identity channel
    gdbus call --session -d org.fidusachates.Overlay \
      -o /org/fidusachates/Overlay \
      -m org.fidusachates.Overlay.SetConfidence 72 Identity

    # read the focused application category
    gdbus call --session -d org.fidusachates.Overlay \
      -o /org/fidusachates/Overlay -m org.fidusachates.Overlay.GetContext

    # clear it
    gdbus call --session -d org.fidusachates.Overlay \
      -o /org/fidusachates/Overlay -m org.fidusachates.Overlay.Clear

The console (`python -m fidus_lab.console`) drives `SetConfidence` automatically.
