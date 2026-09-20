//! Coarse class of a key. This, and not the key, is what gets recorded.

use crate::codes::*;

/// Coarse class of a key. Twelve values: enough to describe typing behaviour
/// (corrections, modifiers, navigation), far too few to recover a text.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum KeyClass {
    Other = 0,
    Letter = 1,
    Digit = 2,
    Punctuation = 3,
    Space = 4,
    Enter = 5,
    Tab = 6,
    /// Backspace and Delete.
    Correction = 7,
    /// Shift, Ctrl, Alt, AltGr, Super.
    Modifier = 8,
    /// Arrows, Home, End, Page Up, Page Down, Insert.
    Navigation = 9,
    /// F1 to F12, Escape, the lock keys.
    Function = 10,
    Keypad = 11,
}

impl KeyClass {
    pub fn from_u8(v: u8) -> Option<Self> {
        use KeyClass::*;
        Some(match v {
            0 => Other,
            1 => Letter,
            2 => Digit,
            3 => Punctuation,
            4 => Space,
            5 => Enter,
            6 => Tab,
            7 => Correction,
            8 => Modifier,
            9 => Navigation,
            10 => Function,
            11 => Keypad,
            _ => return None,
        })
    }
}

/// Class of an evdev key code.
pub fn classify(code: u16) -> KeyClass {
    use KeyClass::*;
    match code {
        KEY_Q..=KEY_P | KEY_A..=KEY_L | KEY_Z..=KEY_M => Letter,
        KEY_1..=KEY_0 => Digit,
        KEY_MINUS | KEY_EQUAL | KEY_LEFTBRACE | KEY_RIGHTBRACE | KEY_SEMICOLON | KEY_APOSTROPHE
        | KEY_GRAVE | KEY_BACKSLASH | KEY_COMMA | KEY_DOT | KEY_SLASH | KEY_102ND => Punctuation,
        KEY_SPACE => Space,
        KEY_ENTER => Enter,
        KEY_TAB => Tab,
        KEY_BACKSPACE | KEY_DELETE => Correction,
        KEY_LEFTSHIFT | KEY_RIGHTSHIFT | KEY_LEFTCTRL | KEY_RIGHTCTRL | KEY_LEFTALT
        | KEY_RIGHTALT | KEY_LEFTMETA | KEY_RIGHTMETA | KEY_COMPOSE => Modifier,
        KEY_HOME | KEY_UP | KEY_PAGEUP | KEY_LEFT | KEY_RIGHT | KEY_END | KEY_DOWN
        | KEY_PAGEDOWN | KEY_INSERT => Navigation,
        KEY_ESC
        | KEY_F1..=KEY_F10
        | KEY_F11
        | KEY_F12
        | KEY_CAPSLOCK
        | KEY_NUMLOCK
        | KEY_SCROLLLOCK => Function,
        KEY_KPASTERISK | KEY_KP7..=KEY_KPDOT | KEY_KPENTER | KEY_KPSLASH => Keypad,
        _ => Other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn main_classes() {
        assert_eq!(classify(KEY_A), KeyClass::Letter);
        assert_eq!(classify(KEY_M), KeyClass::Letter);
        assert_eq!(classify(KEY_1), KeyClass::Digit);
        assert_eq!(classify(KEY_0), KeyClass::Digit);
        assert_eq!(classify(KEY_SPACE), KeyClass::Space);
        assert_eq!(classify(KEY_BACKSPACE), KeyClass::Correction);
        assert_eq!(classify(KEY_DELETE), KeyClass::Correction);
        assert_eq!(classify(KEY_RIGHTSHIFT), KeyClass::Modifier);
        assert_eq!(classify(KEY_LEFT), KeyClass::Navigation);
        assert_eq!(classify(KEY_F12), KeyClass::Function);
        assert_eq!(classify(KEY_KP7), KeyClass::Keypad);
        assert_eq!(classify(0x2ff), KeyClass::Other);
    }

    #[test]
    fn every_letter_position_is_a_letter() {
        let n = (0u16..256)
            .filter(|c| classify(*c) == KeyClass::Letter)
            .count();
        assert_eq!(n, 26);
    }

    #[test]
    fn u8_round_trip() {
        for v in 0u8..=11 {
            assert_eq!(KeyClass::from_u8(v).unwrap() as u8, v);
        }
        assert!(KeyClass::from_u8(12).is_none());
    }
}
