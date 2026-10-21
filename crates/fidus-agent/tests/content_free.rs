//! Acceptance test 1.1: content-free, by property.
//!
//! The guarantee: a key event's reduced record is a pure function of the key
//! **class**, the digraph **class** and the shortcut **class**, plus phase and
//! timing. It carries no finer trace of which key was pressed. If it did, two
//! keys that share the same three classes would nonetheless produce different
//! records, and the content could be told apart.
//!
//! We prove the opposite exhaustively, for each layout: over every
//! previous/current key-code pair, group the produced records by their
//! (class, digraph, shortcut) signature, the shortcut class computed here
//! independently of the reducer, and check that every member of a group is
//! byte-identical. Any hidden dependence on the raw code would split a group.

use fidus_core::biomech::digraph_class;
use fidus_core::keyclass::classify;
use fidus_core::record::{Event, Provenance};
use fidus_core::reduce::Reducer;
use fidus_core::shortcut::{self, Layout, Modifiers, ShortcutClass};
use std::collections::HashMap;

const EV_KEY: u16 = 0x01;
const KEY_MAX: u16 = 256;

/// The record produced for a key-down of `current` after a key-down of
/// `previous`, at a fixed device, provenance and time.
fn key_down_event(previous: u16, current: u16, layout: Layout) -> Event {
    let mut r = Reducer::with_layout(layout);
    r.reduce(0, 0, Provenance::Hardware, EV_KEY, previous, 1);
    r.reduce(1000, 0, Provenance::Hardware, EV_KEY, current, 1)
        .expect("key down produces a record")
        .event
}

/// The shortcut class expected when `current` goes down while `previous` is
/// still held.
fn expected_shortcut(previous: u16, current: u16, layout: Layout) -> ShortcutClass {
    let mut mods = Modifiers::default();
    mods.update(previous, true);
    if mods.update(current, true) {
        ShortcutClass::None
    } else {
        shortcut::classify(current, &mods, layout)
    }
}

#[test]
fn a_key_record_is_a_function_of_its_classes_only() {
    sweep(Layout::Qwerty);
    sweep(Layout::Azerty);
}

fn sweep(layout: Layout) {
    // signature -> the single event every member must share
    let mut seen: HashMap<(u8, u8, u8), (u16, u16, String)> = HashMap::new();

    for previous in 0..KEY_MAX {
        for current in 0..KEY_MAX {
            // Skip codes that are buttons or non-keys: classify treats them as
            // Other, which is fine, but they are handled on a different path.
            if is_button(current) || is_button(previous) {
                continue;
            }
            let signature = (
                classify(current) as u8,
                digraph_class(Some(previous), current).to_u8(),
                expected_shortcut(previous, current, layout) as u8,
            );
            let event = key_down_event(previous, current, layout);
            let rendered = format!("{event:?}");

            match seen.get(&signature) {
                None => {
                    seen.insert(signature, (previous, current, rendered));
                }
                Some((pp, pc, expected)) => {
                    assert_eq!(
                        &rendered, expected,
                        "keys ({previous},{current}) and ({pp},{pc}) share the \
                         class/digraph/shortcut signature {signature:?} but produce \
                         different records: content leaked"
                    );
                }
            }
        }
    }

    // Sanity: the exhaustive sweep actually exercised many distinct signatures.
    assert!(seen.len() > 20, "too few signatures seen: {}", seen.len());
}

fn is_button(code: u16) -> bool {
    (0x100..0x120).contains(&code)
}
