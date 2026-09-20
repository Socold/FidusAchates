//! Reduced trace writer (only with the `research-trace` feature).
//!
//! Writes the 8-byte magic then fixed-size records from `fidus_core::trace`.
//! Buffered so that writing does not slow capture.

use fidus_core::record::Record;
use fidus_core::trace;
use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

pub struct TraceWriter {
    out: BufWriter<File>,
}

impl TraceWriter {
    pub fn create(path: &Path) -> io::Result<Self> {
        let mut out = BufWriter::new(File::create(path)?);
        out.write_all(trace::MAGIC)?;
        Ok(Self { out })
    }

    pub fn write(&mut self, record: &Record) -> io::Result<()> {
        self.out.write_all(&trace::encode(record))
    }
}

impl Drop for TraceWriter {
    fn drop(&mut self) {
        let _ = self.out.flush();
    }
}
