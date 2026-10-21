//! The privacy boundary. A raw key code enters, a [`Record`] leaves.
//!
//! [`Reducer`] is the only place in the project that ever holds a key code, and
//! it holds one only long enough to look up three classes. It keeps the
//! previous key-down code so it can compute the digraph class of the next one,
//! and which modifiers are held (booleans only) so it can compute the shortcut
//! class. That one `u16` and those booleans are the whole of its memory, they
//! are private, and they never reach a [`Record`].

use crate::biomech::{digraph_class, DigraphClass};
use crate::codes::*;
use crate::keyclass::{classify, KeyClass};
use crate::record::{Button, Event, KeyPhase, MicroTime, Provenance, Record};
use crate::shortcut::{self, Layout, Modifiers, ShortcutClass};

/// Reduces the raw events of one device to [`Record`]s.
#[derive(Default)]
pub struct Reducer {
    previous_key_down: Option<u16>,
    modifiers: Modifiers,
    layout: Layout,
}

impl Reducer {
    /// A reducer for a QWERTY keyboard.
    pub fn new() -> Self {
        Self::default()
    }

    /// A reducer for the given layout, which only changes how letter
    /// shortcuts are named (key codes are positional).
    pub fn with_layout(layout: Layout) -> Self {
        Self {
            layout,
            ..Self::default()
        }
    }

    /// Feed one raw evdev event. Returns a [`Record`] for the events the model
    /// cares about, `None` for the rest (key auto-repeat, syn, unknown codes).
    ///
    /// `value` follows evdev: for keys, 1 down, 0 up, 2 auto-repeat; for
    /// relative axes, the signed delta.
    pub fn reduce(
        &mut self,
        time: MicroTime,
        device: u16,
        provenance: Provenance,
        etype: u16,
        code: u16,
        value: i32,
    ) -> Option<Record> {
        let event = match etype {
            EV_KEY => self.reduce_key(code, value)?,
            EV_REL => Self::reduce_rel(code, value)?,
            _ => return None,
        };
        Some(Record {
            time,
            device,
            provenance,
            event,
        })
    }

    fn reduce_key(&mut self, code: u16, value: i32) -> Option<Event> {
        if is_button(code) {
            let phase = match value {
                1 => KeyPhase::Down,
                0 => KeyPhase::Up,
                _ => return None,
            };
            return Some(Event::Button {
                phase,
                button: button_of(code),
            });
        }
        match value {
            1 => {
                let class = classify(code);
                let digraph = digraph_class(self.previous_key_down, code);
                let is_modifier = self.modifiers.update(code, true);
                let shortcut = if is_modifier {
                    ShortcutClass::None
                } else {
                    shortcut::classify(code, &self.modifiers, self.layout)
                };
                // A modifier is not part of the digraph rhythm; keep the
                // previous real key so that "a", "Shift", "b" still forms a-b.
                if class != KeyClass::Modifier {
                    self.previous_key_down = Some(code);
                }
                Some(Event::Key {
                    phase: KeyPhase::Down,
                    class,
                    digraph,
                    shortcut,
                })
            }
            0 => {
                self.modifiers.update(code, false);
                Some(Event::Key {
                    phase: KeyPhase::Up,
                    class: classify(code),
                    digraph: DigraphClass::NONE,
                    shortcut: ShortcutClass::None,
                })
            }
            // 2 is auto-repeat: a held key, not a new keystroke.
            _ => None,
        }
    }

    fn reduce_rel(code: u16, value: i32) -> Option<Event> {
        match code {
            REL_X => Some(Event::Motion { dx: value, dy: 0 }),
            REL_Y => Some(Event::Motion { dx: 0, dy: value }),
            REL_WHEEL => Some(Event::Wheel { dx: 0, dy: value }),
            REL_HWHEEL => Some(Event::Wheel { dx: value, dy: 0 }),
            _ => None,
        }
    }
}

fn is_button(code: u16) -> bool {
    (BTN_MISC..BTN_JOYSTICK).contains(&code)
}

fn button_of(code: u16) -> Button {
    match code {
        BTN_LEFT => Button::Left,
        BTN_RIGHT => Button::Right,
        BTN_MIDDLE => Button::Middle,
        _ => Button::Other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::biomech::Relation;

    const KEY_F: u16 = 33;
    const KEY_J: u16 = 36;

    fn down(r: &mut Reducer, code: u16) -> Event {
        r.reduce(0, 0, Provenance::Hardware, EV_KEY, code, 1)
            .unwrap()
            .event
    }

    #[test]
    fn key_down_carries_classes_not_codes() {
        let mut r = Reducer::new();
        match down(&mut r, KEY_A) {
            Event::Key {
                phase: KeyPhase::Down,
                class,
                ..
            } => {
                assert_eq!(class, KeyClass::Letter)
            }
            e => panic!("{e:?}"),
        }
    }

    #[test]
    fn digraph_spans_consecutive_keys() {
        let mut r = Reducer::new();
        down(&mut r, KEY_F);
        match down(&mut r, KEY_J) {
            Event::Key { digraph, .. } => assert_eq!(digraph.relation, Relation::AlternatingHands),
            e => panic!("{e:?}"),
        }
    }

    #[test]
    fn modifiers_do_not_break_the_digraph() {
        let mut r = Reducer::new();
        down(&mut r, KEY_F);
        down(&mut r, KEY_LEFTSHIFT);
        match down(&mut r, KEY_J) {
            Event::Key { digraph, .. } => assert_eq!(digraph.relation, Relation::AlternatingHands),
            e => panic!("{e:?}"),
        }
    }

    fn shortcut_of(e: Event) -> ShortcutClass {
        match e {
            Event::Key { shortcut, .. } => shortcut,
            e => panic!("{e:?}"),
        }
    }

    fn up(r: &mut Reducer, code: u16) -> Event {
        r.reduce(0, 0, Provenance::Hardware, EV_KEY, code, 0)
            .unwrap()
            .event
    }

    #[test]
    fn shortcut_on_down_only() {
        let mut r = Reducer::with_layout(Layout::Azerty);
        assert_eq!(shortcut_of(down(&mut r, KEY_LEFTCTRL)), ShortcutClass::None);
        // AZERTY: the key at QWERTY W carries Z, so Ctrl+it is Undo.
        assert_eq!(shortcut_of(down(&mut r, KEY_W)), ShortcutClass::Undo);
        assert_eq!(shortcut_of(up(&mut r, KEY_W)), ShortcutClass::None);
        up(&mut r, KEY_LEFTCTRL);
        assert_eq!(shortcut_of(down(&mut r, KEY_W)), ShortcutClass::None);
    }

    #[test]
    fn plain_typing_has_no_shortcut() {
        let mut r = Reducer::new();
        assert_eq!(
            shortcut_of(down(&mut r, KEY_LEFTSHIFT)),
            ShortcutClass::None
        );
        assert_eq!(shortcut_of(down(&mut r, KEY_C)), ShortcutClass::None);
    }

    #[test]
    fn auto_repeat_is_dropped() {
        let mut r = Reducer::new();
        assert!(r
            .reduce(0, 0, Provenance::Hardware, EV_KEY, KEY_A, 2)
            .is_none());
    }

    #[test]
    fn buttons_and_motion() {
        let mut r = Reducer::new();
        assert_eq!(
            r.reduce(0, 0, Provenance::Hardware, EV_KEY, BTN_LEFT, 1)
                .unwrap()
                .event,
            Event::Button {
                phase: KeyPhase::Down,
                button: Button::Left
            }
        );
        assert_eq!(
            r.reduce(0, 0, Provenance::Hardware, EV_REL, REL_X, -7)
                .unwrap()
                .event,
            Event::Motion { dx: -7, dy: 0 }
        );
    }

    #[test]
    fn provenance_is_carried_through() {
        let mut r = Reducer::new();
        let rec = r
            .reduce(0, 4, Provenance::Virtual, EV_KEY, KEY_A, 1)
            .unwrap();
        assert_eq!(rec.provenance, Provenance::Virtual);
        assert_eq!(rec.device, 4);
    }
}
