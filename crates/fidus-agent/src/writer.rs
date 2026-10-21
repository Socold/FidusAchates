//! Reduced trace writer (only with the `research-trace` feature).
//!
//! Writes the 8-byte magic then fixed-size records from `fidus_core::trace`,
//! to a file or to standard output (`--trace -`, for the live pipeline).
//! Buffered so that writing does not slow capture; the loop flushes after each
//! batch of events so a reader on a pipe sees them without delay.

use fidus_core::record::Record;
use fidus_core::trace;
use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

pub struct TraceWriter {
    out: BufWriter<Box<dyn Write>>,
}

impl TraceWriter {
    /// `-` means standard output; anything else is a file path.
    pub fn create(path: &Path) -> io::Result<Self> {
        let sink: Box<dyn Write> = if path == Path::new("-") {
            Box::new(io::stdout())
        } else {
            Box::new(File::create(path)?)
        };
        let mut out = BufWriter::new(sink);
        out.write_all(trace::MAGIC)?;
        Ok(Self { out })
    }

    pub fn write(&mut self, record: &Record) -> io::Result<()> {
        self.out.write_all(&trace::encode(record))
    }

    pub fn flush(&mut self) -> io::Result<()> {
        self.out.flush()
    }
}

impl Drop for TraceWriter {
    fn drop(&mut self) {
        let _ = self.out.flush();
    }
}
