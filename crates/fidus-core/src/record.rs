//! The record: everything the project keeps about one input event.
//!
//! This type is the content-free guarantee made structural. It has fields for
//! a key **class** and a digraph **class**, and **no field able to hold a key
//! code or a character**. Whatever a reviewer thinks of the rest of the code,
//! this type cannot carry a typed secret, because there is nowhere to put it.

use crate::biomech::DigraphClass;
use crate::keyclass::KeyClass;

/// Monotonic microseconds since an arbitrary origin. Never wall-clock time, so
/// that a trace cannot be tied to a moment in the day.
pub type MicroTime = u64;

/// A key going down or up.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KeyPhase {
    Down,
    Up,
}

/// What happened, reduced to what the model may see.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Event {
    Key {
        phase: KeyPhase,
        class: KeyClass,
        /// Class of the pair (previous key down, this key). Meaningful on
        /// `Down` only; `DigraphClass::NONE` otherwise.
        digraph: DigraphClass,
    },
    /// Relative pointer motion. Deltas are behaviour, not content.
    Motion { dx: i32, dy: i32 },
    /// Vertical (`dy`) and horizontal (`dx`) wheel notches.
    Wheel { dx: i32, dy: i32 },
    Button { phase: KeyPhase, button: Button },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Button {
    Left,
    Right,
    Middle,
    Other,
}

/// Whether the source device is real hardware or a virtual `uinput` device.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Provenance {
    Hardware,
    Virtual,
}

/// One reduced event, with its time, source and provenance.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Record {
    pub time: MicroTime,
    /// Index into the session's device table, not a device path.
    pub device: u16,
    pub provenance: Provenance,
    pub event: Event,
}
