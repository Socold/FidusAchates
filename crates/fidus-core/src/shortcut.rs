//! Shortcut classes (signal catalogue A16), computed without keeping a key.
//!
//! A shortcut is a habit, not content: whether I copy with Ctrl+C or through a
//! menu, whether I switch windows with Alt+Tab or the mouse. What leaves this
//! module is one of a fixed list of classes; anything outside the list is
//! `Other`, so the class never says which key was pressed beyond the habit.
//!
//! Key codes are positional and shortcuts are bound to the letter printed on
//! the key, so letter shortcuts need the keyboard layout to be named right.

use crate::codes::*;

/// Class of a shortcut. Stored in one byte of the trace; 0 means no shortcut.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum ShortcutClass {
    #[default]
    None = 0,
    Copy = 1,
    Paste = 2,
    Cut = 3,
    Undo = 4,
    Redo = 5,
    SelectAll = 6,
    Save = 7,
    Find = 8,
    NewTab = 9,
    CloseTab = 10,
    ReopenTab = 11,
    Reload = 12,
    NewWindow = 13,
    Open = 14,
    Quit = 15,
    Print = 16,
    NextTab = 17,
    PrevTab = 18,
    SwitchApp = 19,
    CloseWindow = 20,
    WordMove = 21,
    WordDelete = 22,
    TerminalCopy = 23,
    TerminalPaste = 24,
    LockScreen = 25,
    DocStartEnd = 26,
    /// A shortcut modifier was held, but the combination is not in the list.
    Other = 27,
}

impl ShortcutClass {
    pub fn from_u8(v: u8) -> Option<Self> {
        use ShortcutClass::*;
        Some(match v {
            0 => None,
            1 => Copy,
            2 => Paste,
            3 => Cut,
            4 => Undo,
            5 => Redo,
            6 => SelectAll,
            7 => Save,
            8 => Find,
            9 => NewTab,
            10 => CloseTab,
            11 => ReopenTab,
            12 => Reload,
            13 => NewWindow,
            14 => Open,
            15 => Quit,
            16 => Print,
            17 => NextTab,
            18 => PrevTab,
            19 => SwitchApp,
            20 => CloseWindow,
            21 => WordMove,
            22 => WordDelete,
            23 => TerminalCopy,
            24 => TerminalPaste,
            25 => LockScreen,
            26 => DocStartEnd,
            27 => Other,
            _ => return Option::None,
        })
    }
}

/// Keyboard layout, for naming letter shortcuts from positional codes.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Layout {
    #[default]
    Qwerty,
    Azerty,
}

/// Which modifier keys are held. Booleans only: no key code is kept.
///
/// Right Alt is AltGr, which types characters on many layouts, so it is not a
/// shortcut modifier and is not tracked.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Modifiers {
    left_ctrl: bool,
    right_ctrl: bool,
    left_alt: bool,
    left_meta: bool,
    right_meta: bool,
    left_shift: bool,
    right_shift: bool,
}

impl Modifiers {
    /// Update from a key going down or up. Returns true if `code` is a
    /// tracked modifier.
    pub fn update(&mut self, code: u16, down: bool) -> bool {
        let slot = match code {
            KEY_LEFTCTRL => &mut self.left_ctrl,
            KEY_RIGHTCTRL => &mut self.right_ctrl,
            KEY_LEFTALT => &mut self.left_alt,
            KEY_LEFTMETA => &mut self.left_meta,
            KEY_RIGHTMETA => &mut self.right_meta,
            KEY_LEFTSHIFT => &mut self.left_shift,
            KEY_RIGHTSHIFT => &mut self.right_shift,
            _ => return false,
        };
        *slot = down;
        true
    }

    fn ctrl(&self) -> bool {
        self.left_ctrl || self.right_ctrl
    }

    fn shift(&self) -> bool {
        self.left_shift || self.right_shift
    }
}

/// The letter printed on a key, for the few letters shortcuts use. Internal:
/// it never leaves this module.
fn letter(code: u16, layout: Layout) -> Option<u8> {
    if layout == Layout::Azerty {
        match code {
            KEY_Q => return Some(b'a'),
            KEY_W => return Some(b'z'),
            KEY_A => return Some(b'q'),
            KEY_Z => return Some(b'w'),
            KEY_SEMICOLON => return Some(b'm'),
            // The comma, not a letter.
            KEY_M => return None,
            _ => {}
        }
    }
    Some(match code {
        KEY_A => b'a',
        KEY_C => b'c',
        KEY_F => b'f',
        KEY_L => b'l',
        KEY_N => b'n',
        KEY_O => b'o',
        KEY_P => b'p',
        KEY_Q => b'q',
        KEY_R => b'r',
        KEY_S => b's',
        KEY_T => b't',
        KEY_V => b'v',
        KEY_W => b'w',
        KEY_X => b'x',
        KEY_Y => b'y',
        KEY_Z => b'z',
        _ => return None,
    })
}

/// Class of a non-modifier key pressed with the given modifiers held.
pub fn classify(code: u16, mods: &Modifiers, layout: Layout) -> ShortcutClass {
    use ShortcutClass::*;
    let ctrl = mods.ctrl();
    let alt = mods.left_alt;
    let meta = mods.left_meta || mods.right_meta;
    if !(ctrl || alt || meta) {
        return None;
    }
    let shift = mods.shift();

    if ctrl && !alt && !meta {
        if let Some(l) = letter(code, layout) {
            return match (l, shift) {
                (b'c', false) => Copy,
                (b'v', false) => Paste,
                (b'c', true) => TerminalCopy,
                (b'v', true) => TerminalPaste,
                (b'x', false) => Cut,
                (b'z', false) => Undo,
                (b'z', true) | (b'y', false) => Redo,
                (b'a', false) => SelectAll,
                (b's', false) => Save,
                (b'f', false) => Find,
                (b't', false) => NewTab,
                (b't', true) => ReopenTab,
                (b'w', false) => CloseTab,
                (b'r', false) => Reload,
                (b'n', false) => NewWindow,
                (b'o', false) => Open,
                (b'q', false) => Quit,
                (b'p', false) => Print,
                _ => Other,
            };
        }
        return match (code, shift) {
            (KEY_TAB, false) | (KEY_PAGEDOWN, _) => NextTab,
            (KEY_TAB, true) | (KEY_PAGEUP, _) => PrevTab,
            (KEY_LEFT | KEY_RIGHT, _) => WordMove,
            (KEY_BACKSPACE | KEY_DELETE, _) => WordDelete,
            (KEY_HOME | KEY_END, _) => DocStartEnd,
            _ => Other,
        };
    }
    if alt && !ctrl && !meta {
        return match code {
            KEY_TAB => SwitchApp,
            KEY_F4 => CloseWindow,
            _ => Other,
        };
    }
    if meta && !ctrl && !alt {
        if code == KEY_TAB {
            return SwitchApp;
        }
        if letter(code, layout) == Some(b'l') {
            return LockScreen;
        }
    }
    Other
}

#[cfg(test)]
mod tests {
    use super::*;

    fn held(codes: &[u16]) -> Modifiers {
        let mut m = Modifiers::default();
        for c in codes {
            assert!(m.update(*c, true));
        }
        m
    }

    #[test]
    fn qwerty_letters() {
        let ctrl = held(&[KEY_LEFTCTRL]);
        let q = Layout::Qwerty;
        assert_eq!(classify(KEY_C, &ctrl, q), ShortcutClass::Copy);
        assert_eq!(classify(KEY_V, &ctrl, q), ShortcutClass::Paste);
        assert_eq!(classify(KEY_Z, &ctrl, q), ShortcutClass::Undo);
        assert_eq!(classify(KEY_W, &ctrl, q), ShortcutClass::CloseTab);
        assert_eq!(classify(KEY_A, &ctrl, q), ShortcutClass::SelectAll);
        assert_eq!(classify(KEY_Q, &ctrl, q), ShortcutClass::Quit);
        assert_eq!(classify(KEY_1, &ctrl, q), ShortcutClass::Other);
    }

    #[test]
    fn azerty_letters_follow_the_printed_key() {
        let ctrl = held(&[KEY_RIGHTCTRL]);
        let a = Layout::Azerty;
        assert_eq!(classify(KEY_W, &ctrl, a), ShortcutClass::Undo);
        assert_eq!(classify(KEY_Z, &ctrl, a), ShortcutClass::CloseTab);
        assert_eq!(classify(KEY_Q, &ctrl, a), ShortcutClass::SelectAll);
        assert_eq!(classify(KEY_A, &ctrl, a), ShortcutClass::Quit);
        assert_eq!(classify(KEY_C, &ctrl, a), ShortcutClass::Copy);
        // KEY_M carries the comma on AZERTY: not a listed shortcut.
        assert_eq!(classify(KEY_M, &ctrl, a), ShortcutClass::Other);
    }

    #[test]
    fn shift_qualifies() {
        let m = held(&[KEY_LEFTCTRL, KEY_LEFTSHIFT]);
        let q = Layout::Qwerty;
        assert_eq!(classify(KEY_Z, &m, q), ShortcutClass::Redo);
        assert_eq!(classify(KEY_T, &m, q), ShortcutClass::ReopenTab);
        assert_eq!(classify(KEY_C, &m, q), ShortcutClass::TerminalCopy);
        assert_eq!(classify(KEY_V, &m, q), ShortcutClass::TerminalPaste);
        assert_eq!(classify(KEY_TAB, &m, q), ShortcutClass::PrevTab);
        // Shift alone is never a shortcut.
        assert_eq!(
            classify(KEY_C, &held(&[KEY_LEFTSHIFT]), q),
            ShortcutClass::None
        );
    }

    #[test]
    fn altgr_never_counts() {
        let mut m = Modifiers::default();
        assert!(!m.update(KEY_RIGHTALT, true));
        assert_eq!(classify(KEY_1, &m, Layout::Azerty), ShortcutClass::None);
        assert_eq!(classify(KEY_C, &m, Layout::Azerty), ShortcutClass::None);
    }

    #[test]
    fn alt_and_super() {
        let q = Layout::Qwerty;
        let alt = held(&[KEY_LEFTALT]);
        assert_eq!(classify(KEY_TAB, &alt, q), ShortcutClass::SwitchApp);
        assert_eq!(classify(KEY_F4, &alt, q), ShortcutClass::CloseWindow);
        let sup = held(&[KEY_LEFTMETA]);
        assert_eq!(classify(KEY_TAB, &sup, q), ShortcutClass::SwitchApp);
        assert_eq!(classify(KEY_L, &sup, q), ShortcutClass::LockScreen);
        assert_eq!(classify(KEY_F, &sup, q), ShortcutClass::Other);
    }

    #[test]
    fn navigation_with_ctrl() {
        let ctrl = held(&[KEY_LEFTCTRL]);
        let q = Layout::Qwerty;
        assert_eq!(classify(KEY_LEFT, &ctrl, q), ShortcutClass::WordMove);
        assert_eq!(classify(KEY_BACKSPACE, &ctrl, q), ShortcutClass::WordDelete);
        assert_eq!(classify(KEY_END, &ctrl, q), ShortcutClass::DocStartEnd);
        assert_eq!(classify(KEY_PAGEDOWN, &ctrl, q), ShortcutClass::NextTab);
        assert_eq!(classify(KEY_TAB, &ctrl, q), ShortcutClass::NextTab);
    }

    #[test]
    fn release_clears_state() {
        let mut m = held(&[KEY_LEFTCTRL]);
        m.update(KEY_LEFTCTRL, false);
        assert_eq!(classify(KEY_C, &m, Layout::Qwerty), ShortcutClass::None);
        // One ctrl released while the other is held still counts.
        let mut m = held(&[KEY_LEFTCTRL, KEY_RIGHTCTRL]);
        m.update(KEY_LEFTCTRL, false);
        assert_eq!(classify(KEY_C, &m, Layout::Qwerty), ShortcutClass::Copy);
    }

    #[test]
    fn u8_round_trip() {
        for v in 0u8..=27 {
            assert_eq!(ShortcutClass::from_u8(v).unwrap() as u8, v);
        }
        assert!(ShortcutClass::from_u8(28).is_none());
    }
}
