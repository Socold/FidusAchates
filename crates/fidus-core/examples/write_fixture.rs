//! Generate the shared trace fixture used by the Python reader test.
//!
//!     cargo run -p fidus-core --features research-trace --example write_fixture
//!
//! Writes research/fixtures/sample.fidustr with one record of each kind, in a
//! fixed order, so that lab/tests/test_trace.py can check the two languages
//! agree on the format (roadmap 1.7).

use fidus_core::biomech::DigraphClass;
use fidus_core::keyclass::KeyClass;
use fidus_core::record::{Button, Event, KeyPhase, Provenance, Record};
use fidus_core::trace::{encode, MAGIC};
use std::io::Write;

fn main() -> std::io::Result<()> {
    let records = [
        rec(
            1000,
            Event::Key {
                phase: KeyPhase::Down,
                class: KeyClass::Letter,
                digraph: DigraphClass::NONE,
            },
        ),
        rec(
            1040,
            Event::Key {
                phase: KeyPhase::Up,
                class: KeyClass::Letter,
                digraph: DigraphClass::NONE,
            },
        ),
        rec(2000, Event::Motion { dx: -5, dy: 3 }),
        rec(2100, Event::Wheel { dx: 0, dy: -1 }),
        rec(
            3000,
            Event::Button {
                phase: KeyPhase::Down,
                button: Button::Left,
            },
        ),
        rec(
            3050,
            Event::Button {
                phase: KeyPhase::Up,
                button: Button::Left,
            },
        ),
    ];

    let path = "research/fixtures/sample.fidustr";
    let mut f = std::fs::File::create(path)?;
    f.write_all(MAGIC)?;
    for r in &records {
        f.write_all(&encode(r))?;
    }
    eprintln!("wrote {} records to {path}", records.len());
    Ok(())
}

fn rec(time: u64, event: Event) -> Record {
    Record {
        time,
        device: 0,
        provenance: Provenance::Hardware,
        event,
    }
}
