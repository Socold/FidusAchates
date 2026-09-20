//! Biomechanical class of a key pair (ADR-0008).
//!
//! What makes a digraph latency personal is the motor pattern, not the
//! letters. Each key of the main block gets a geometric position (hand,
//! finger column, row) following the touch-typing convention, and a pair of
//! keys is reduced to the relation between the two positions.
//!
//! The finger assignment is a **geometric convention**, not a claim about the
//! finger actually used: many people do not touch-type. It only has to be a
//! stable partition of key pairs.

use crate::codes::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Hand {
    Left,
    Right,
}

/// Geometric position of a key of the main block.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Pos {
    pub hand: Hand,
    /// 0 little finger, 1 ring, 2 middle, 3 index.
    pub finger: u8,
    /// 0 digit row, 1 top row, 2 home row, 3 bottom row.
    pub row: u8,
}

/// Relation between the positions of two consecutive keys.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum Relation {
    /// One of the two keys is outside the main block, or there is no previous key.
    None = 0,
    /// Same key twice.
    Repeat = 1,
    SameFinger = 2,
    SameHandAdjacent = 3,
    SameHandDistant = 4,
    AlternatingHands = 5,
}

/// Row distance between two consecutive keys, without direction.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum RowMove {
    Same = 0,
    One = 1,
    TwoOrMore = 2,
    NotApplicable = 3,
}

/// Class of a key pair, as recorded: relation and row distance, nothing else.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct DigraphClass {
    pub relation: Relation,
    pub row_move: RowMove,
}

impl DigraphClass {
    pub const NONE: DigraphClass =
        DigraphClass { relation: Relation::None, row_move: RowMove::NotApplicable };

    /// Packed form: relation in bits 0-2, row distance in bits 3-4.
    pub fn to_u8(self) -> u8 {
        (self.relation as u8) | ((self.row_move as u8) << 3)
    }

    pub fn from_u8(v: u8) -> Option<Self> {
        if v & 0b1110_0000 != 0 {
            return None;
        }
        let relation = match v & 0b111 {
            0 => Relation::None,
            1 => Relation::Repeat,
            2 => Relation::SameFinger,
            3 => Relation::SameHandAdjacent,
            4 => Relation::SameHandDistant,
            5 => Relation::AlternatingHands,
            _ => return None,
        };
        let row_move = match (v >> 3) & 0b11 {
            0 => RowMove::Same,
            1 => RowMove::One,
            2 => RowMove::TwoOrMore,
            _ => RowMove::NotApplicable,
        };
        Some(DigraphClass { relation, row_move })
    }
}

/// Position of a key of the main block, `None` outside it.
pub fn position(code: u16) -> Option<Pos> {
    // (row, first code of the run, columns of the run starting at `first`)
    let (row, col) = match code {
        KEY_GRAVE => (0, 0),
        KEY_1..=KEY_EQUAL => (0, 1 + (code - KEY_1)),
        KEY_Q..=KEY_RIGHTBRACE => (1, 1 + (code - KEY_Q)),
        KEY_A..=KEY_APOSTROPHE => (2, 1 + (code - KEY_A)),
        KEY_BACKSLASH => (2, 12),
        KEY_102ND => (3, 0),
        KEY_Z..=KEY_SLASH => (3, 1 + (code - KEY_Z)),
        _ => return None,
    };
    // Column 0 is left of the first letter column; columns 1..=10 are the ten
    // letter columns; anything beyond belongs to the right little finger.
    let (hand, finger) = match col {
        0 | 1 => (Hand::Left, 0),
        2 => (Hand::Left, 1),
        3 => (Hand::Left, 2),
        4 | 5 => (Hand::Left, 3),
        6 | 7 => (Hand::Right, 3),
        8 => (Hand::Right, 2),
        9 => (Hand::Right, 1),
        _ => (Hand::Right, 0),
    };
    Some(Pos { hand, finger, row: row as u8 })
}

/// Class of the pair `(previous, current)`.
pub fn digraph_class(previous: Option<u16>, current: u16) -> DigraphClass {
    let Some(previous) = previous else { return DigraphClass::NONE };
    let (Some(p), Some(c)) = (position(previous), position(current)) else {
        return DigraphClass::NONE;
    };
    let row_move = match p.row.abs_diff(c.row) {
        0 => RowMove::Same,
        1 => RowMove::One,
        _ => RowMove::TwoOrMore,
    };
    let relation = if previous == current {
        Relation::Repeat
    } else if p.hand != c.hand {
        Relation::AlternatingHands
    } else {
        match p.finger.abs_diff(c.finger) {
            0 => Relation::SameFinger,
            1 => Relation::SameHandAdjacent,
            _ => Relation::SameHandDistant,
        }
    };
    DigraphClass { relation, row_move }
}

/// Mirror image of a key across the middle of the keyboard (F and J swap,
/// D and K, and so on). Mirroring preserves every relation and every row
/// distance, which makes it the tool for the content-free property test.
pub fn mirror(code: u16) -> u16 {
    let run = |first: u16, code: u16| first + (9 - (code - first));
    match code {
        KEY_1..=KEY_0 => run(KEY_1, code),
        KEY_Q..=KEY_P => run(KEY_Q, code),
        KEY_A..=KEY_SEMICOLON => run(KEY_A, code),
        KEY_Z..=KEY_SLASH => run(KEY_Z, code),
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const KEY_F: u16 = 33;
    const KEY_J: u16 = 36;
    const KEY_R: u16 = 19;
    const KEY_D: u16 = 32;
    const KEY_S: u16 = 31;
    const KEY_V: u16 = 47;
    const KEY_4: u16 = 5;

    #[test]
    fn home_row_positions() {
        assert_eq!(position(KEY_F), Some(Pos { hand: Hand::Left, finger: 3, row: 2 }));
        assert_eq!(position(KEY_J), Some(Pos { hand: Hand::Right, finger: 3, row: 2 }));
        assert_eq!(position(KEY_A), Some(Pos { hand: Hand::Left, finger: 0, row: 2 }));
        assert_eq!(position(KEY_SEMICOLON), Some(Pos { hand: Hand::Right, finger: 0, row: 2 }));
        assert_eq!(position(KEY_SPACE), None);
        assert_eq!(position(KEY_LEFTSHIFT), None);
    }

    #[test]
    fn relations() {
        let c = |a, b| digraph_class(Some(a), b);
        assert_eq!(c(KEY_F, KEY_J).relation, Relation::AlternatingHands);
        assert_eq!(c(KEY_F, KEY_J).row_move, RowMove::Same);
        assert_eq!(c(KEY_F, KEY_R).relation, Relation::SameFinger);
        assert_eq!(c(KEY_F, KEY_R).row_move, RowMove::One);
        assert_eq!(c(KEY_F, KEY_D).relation, Relation::SameHandAdjacent);
        assert_eq!(c(KEY_F, KEY_S).relation, Relation::SameHandDistant);
        assert_eq!(c(KEY_F, KEY_F).relation, Relation::Repeat);
        assert_eq!(c(KEY_4, KEY_V).row_move, RowMove::TwoOrMore);
        assert_eq!(c(KEY_F, KEY_SPACE), DigraphClass::NONE);
        assert_eq!(digraph_class(None, KEY_F), DigraphClass::NONE);
    }

    #[test]
    fn packing_round_trip() {
        for r in 0u8..=5 {
            for m in 0u8..=3 {
                let v = r | (m << 3);
                let c = DigraphClass::from_u8(v).unwrap();
                assert_eq!(c.to_u8(), v);
            }
        }
        assert!(DigraphClass::from_u8(6).is_none());
        assert!(DigraphClass::from_u8(0b0010_0000).is_none());
    }

    #[test]
    fn mirror_is_an_involution_that_changes_keys() {
        for code in 0u16..128 {
            assert_eq!(mirror(mirror(code)), code);
        }
        assert_eq!(mirror(KEY_F), KEY_J);
        assert_ne!(mirror(KEY_A), KEY_A);
    }

    /// Keys the mirror is defined on: the four rows of ten columns, plus every
    /// key outside the main block (which has no position and mirrors to itself).
    fn in_mirror_domain(code: u16) -> bool {
        position(code).is_none() || mirror(code) != code
    }

    #[test]
    fn mirror_preserves_every_class() {
        for a in (0u16..128).filter(|c| in_mirror_domain(*c)) {
            for b in (0u16..128).filter(|c| in_mirror_domain(*c)) {
                assert_eq!(
                    digraph_class(Some(a), b),
                    digraph_class(Some(mirror(a)), mirror(b)),
                    "pair ({a},{b})"
                );
            }
        }
    }
}
