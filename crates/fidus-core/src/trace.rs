//! Reduced trace: encoding of [`Record`]s (FR-70, ADR-0010).
//!
//! Only compiled with the `research-trace` feature, so a release binary does
//! not contain the code that writes events to disk. The format is the
//! interface between the Rust recorder and the Python reader; both are tested
//! against `research/TRACE-FORMAT.md`.
//!
//! Fixed 16-byte little-endian records. No key code, no character: an encoded
//! trace can be decoded back only to classes, deltas and timings.

use crate::biomech::DigraphClass;
use crate::keyclass::KeyClass;
use crate::record::{Button, Event, KeyPhase, Provenance, Record};

pub const MAGIC: &[u8; 8] = b"FIDUSTR\x01";
pub const RECORD_LEN: usize = 16;

const EV_KEY_DOWN: u8 = 0x01;
const EV_KEY_UP: u8 = 0x02;
const EV_MOTION: u8 = 0x03;
const EV_WHEEL: u8 = 0x04;
const EV_BUTTON_DOWN: u8 = 0x05;
const EV_BUTTON_UP: u8 = 0x06;

const PROV_VIRTUAL: u8 = 0x80;

/// Encode one record into 16 bytes.
///
/// Layout: time u64, device u16, flags u8 (event kind in the low bits,
/// provenance in the high bit), then a 4-byte payload and one padding byte.
pub fn encode(r: &Record) -> [u8; RECORD_LEN] {
    let mut b = [0u8; RECORD_LEN];
    b[0..8].copy_from_slice(&r.time.to_le_bytes());
    b[8..10].copy_from_slice(&r.device.to_le_bytes());

    let (kind, payload): (u8, [u8; 4]) = match r.event {
        Event::Key {
            phase,
            class,
            digraph,
        } => (
            if phase == KeyPhase::Down {
                EV_KEY_DOWN
            } else {
                EV_KEY_UP
            },
            [class as u8, digraph.to_u8(), 0, 0],
        ),
        Event::Motion { dx, dy } => (EV_MOTION, pack_i16(dx, dy)),
        Event::Wheel { dx, dy } => (EV_WHEEL, pack_i16(dx, dy)),
        Event::Button { phase, button } => (
            if phase == KeyPhase::Down {
                EV_BUTTON_DOWN
            } else {
                EV_BUTTON_UP
            },
            [button as u8, 0, 0, 0],
        ),
    };
    b[10] = kind
        | if r.provenance == Provenance::Virtual {
            PROV_VIRTUAL
        } else {
            0
        };
    b[11..15].copy_from_slice(&payload);
    b
}

/// Decode 16 bytes back into a record, or `None` if the bytes are not a valid
/// record. Decoding can never yield a key code: there is none in the bytes.
pub fn decode(b: &[u8; RECORD_LEN]) -> Option<Record> {
    let time = u64::from_le_bytes(b[0..8].try_into().unwrap());
    let device = u16::from_le_bytes(b[8..10].try_into().unwrap());
    let provenance = if b[10] & PROV_VIRTUAL != 0 {
        Provenance::Virtual
    } else {
        Provenance::Hardware
    };
    let payload: [u8; 4] = b[11..15].try_into().unwrap();

    let event = match b[10] & 0x7f {
        EV_KEY_DOWN | EV_KEY_UP => Event::Key {
            phase: if b[10] & 0x7f == EV_KEY_DOWN {
                KeyPhase::Down
            } else {
                KeyPhase::Up
            },
            class: KeyClass::from_u8(payload[0])?,
            digraph: DigraphClass::from_u8(payload[1])?,
        },
        EV_MOTION => {
            let (dx, dy) = unpack_i16(payload);
            Event::Motion { dx, dy }
        }
        EV_WHEEL => {
            let (dx, dy) = unpack_i16(payload);
            Event::Wheel { dx, dy }
        }
        EV_BUTTON_DOWN | EV_BUTTON_UP => Event::Button {
            phase: if b[10] & 0x7f == EV_BUTTON_DOWN {
                KeyPhase::Down
            } else {
                KeyPhase::Up
            },
            button: button_from_u8(payload[0])?,
        },
        _ => return None,
    };
    Some(Record {
        time,
        device,
        provenance,
        event,
    })
}

fn pack_i16(dx: i32, dy: i32) -> [u8; 4] {
    let dx = dx.clamp(i16::MIN as i32, i16::MAX as i32) as i16;
    let dy = dy.clamp(i16::MIN as i32, i16::MAX as i32) as i16;
    let mut p = [0u8; 4];
    p[0..2].copy_from_slice(&dx.to_le_bytes());
    p[2..4].copy_from_slice(&dy.to_le_bytes());
    p
}

fn unpack_i16(p: [u8; 4]) -> (i32, i32) {
    let dx = i16::from_le_bytes(p[0..2].try_into().unwrap()) as i32;
    let dy = i16::from_le_bytes(p[2..4].try_into().unwrap()) as i32;
    (dx, dy)
}

fn button_from_u8(v: u8) -> Option<Button> {
    Some(match v {
        0 => Button::Left,
        1 => Button::Right,
        2 => Button::Middle,
        3 => Button::Other,
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::biomech::{DigraphClass, Relation, RowMove};

    fn round_trip(ev: Event, prov: Provenance) {
        let r = Record {
            time: 123_456_789,
            device: 3,
            provenance: prov,
            event: ev,
        };
        let bytes = encode(&r);
        assert_eq!(bytes.len(), RECORD_LEN);
        assert_eq!(decode(&bytes), Some(r));
    }

    #[test]
    fn all_events_round_trip() {
        let dg = DigraphClass {
            relation: Relation::SameHandDistant,
            row_move: RowMove::One,
        };
        round_trip(
            Event::Key {
                phase: KeyPhase::Down,
                class: KeyClass::Letter,
                digraph: dg,
            },
            Provenance::Hardware,
        );
        round_trip(
            Event::Key {
                phase: KeyPhase::Up,
                class: KeyClass::Correction,
                digraph: DigraphClass::NONE,
            },
            Provenance::Virtual,
        );
        round_trip(Event::Motion { dx: -1200, dy: 900 }, Provenance::Hardware);
        round_trip(Event::Wheel { dx: 0, dy: -1 }, Provenance::Hardware);
        round_trip(
            Event::Button {
                phase: KeyPhase::Down,
                button: Button::Right,
            },
            Provenance::Virtual,
        );
    }

    #[test]
    fn motion_saturates_rather_than_wrapping() {
        let r = Record {
            time: 0,
            device: 0,
            provenance: Provenance::Hardware,
            event: Event::Motion {
                dx: 99_999,
                dy: -99_999,
            },
        };
        match decode(&encode(&r)).unwrap().event {
            Event::Motion { dx, dy } => {
                assert_eq!(dx, i16::MAX as i32);
                assert_eq!(dy, i16::MIN as i32);
            }
            e => panic!("{e:?}"),
        }
    }

    #[test]
    fn garbage_decodes_to_none_not_panic() {
        assert!(decode(&[0xff; RECORD_LEN]).is_none());
    }
}
