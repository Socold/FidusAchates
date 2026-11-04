//! FidusAchates indicator for Windows (notification area) and macOS (menu bar).
//!
//! STATUS: reference skeleton (WP10, docs/11-PORTING-WINDOWS-MACOS.md). It is
//! built on the target, not in the offline Linux flow, and the tray wiring
//! marked TODO is finished there. On Linux the GNOME Shell extension already
//! does this job; this crate is the cross-platform equivalent for the other two.
//!
//! It is a thin viewer over the daemon, exactly like the GNOME extension: it
//! shows the state and offers the Monitoring switch and a way into the console.
//! It reads no input and holds no biometric data; it only reads two small files
//! the daemon maintains and writes one control file. The contract:
//!
//!   $RUNTIME/fidusachates/state         one word: calm | watching | alarm
//!   $RUNTIME/fidusachates/console-link  the one-time console URL (already exists)
//!   $RUNTIME/fidusachates/control       written by this indicator: pause | resume
//!
//! `state` and `control` are the small addition the daemon needs for this
//! indicator (the GNOME path uses D-Bus instead); `console-link` already exists.
//! On Windows, $RUNTIME maps to %LOCALAPPDATA%\FidusAchates.

use std::fs;
use std::path::PathBuf;

#[derive(Clone, Copy, PartialEq, Eq)]
enum State {
    Calm,
    Watching,
    Alarm,
    Unknown,
}

impl State {
    fn parse(s: &str) -> Self {
        match s.trim() {
            "calm" => State::Calm,
            "watching" => State::Watching,
            "alarm" => State::Alarm,
            _ => State::Unknown,
        }
    }

    /// Tooltip and icon colour, matching the onboarding page and the GNOME square.
    fn label(self) -> &'static str {
        match self {
            State::Calm => "FidusAchates: recognises you",
            State::Watching => "FidusAchates: watching, gathering evidence",
            State::Alarm => "FidusAchates: alarm, open the console",
            State::Unknown => "FidusAchates: starting",
        }
    }

    fn rgb(self) -> (u8, u8, u8) {
        match self {
            State::Calm => (0x4b, 0x9e, 0x6a),
            State::Watching => (0xc6, 0x89, 0x3f),
            State::Alarm => (0xb5, 0x45, 0x2f),
            State::Unknown => (0x8e, 0x86, 0xa6),
        }
    }
}

fn runtime_dir() -> PathBuf {
    // Linux/macOS: $XDG_RUNTIME_DIR, else a temp fallback. Windows: %LOCALAPPDATA%.
    if let Ok(d) = std::env::var("XDG_RUNTIME_DIR") {
        return PathBuf::from(d).join("fidusachates");
    }
    if let Ok(d) = std::env::var("LOCALAPPDATA") {
        return PathBuf::from(d).join("FidusAchates");
    }
    std::env::temp_dir().join("fidusachates")
}

fn read_state(dir: &PathBuf) -> State {
    match fs::read_to_string(dir.join("state")) {
        Ok(s) => State::parse(&s),
        Err(_) => State::Unknown,
    }
}

fn console_url(dir: &PathBuf) -> Option<String> {
    fs::read_to_string(dir.join("console-link"))
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

fn set_monitoring(dir: &PathBuf, on: bool) -> std::io::Result<()> {
    fs::create_dir_all(dir)?;
    fs::write(dir.join("control"), if on { "resume" } else { "pause" })
}

fn main() {
    let dir = runtime_dir();
    let state = read_state(&dir);
    eprintln!("fidus-tray: {} ({})", state.label(), dir.display());

    // TODO (on the target): build the tray with `tray-icon`.
    //   - an Icon tinted with state.rgb(), tooltip state.label()
    //   - a `muda` menu:
    //       "Open console"      -> open console_url(&dir) in the browser
    //       "Pause monitoring"  -> set_monitoring(&dir, false) (toggles to Resume)
    //       "Quit"
    //   - a `tao` event loop that, every second, calls read_state(&dir) and
    //     updates the icon colour and tooltip when the state changes.
    //
    // Keep it a viewer: never read input, never store anything, no network.
    // Measure the footprint against NFR-1..4 like the agent.
    let _ = (State::Calm.rgb(), console_url(&dir), set_monitoring(&dir, true));
}
