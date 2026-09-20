//! Minimal evdev reading: opening a device and parsing `input_event` structs.
//!
//! We do not depend on an evdev crate. The kernel ABI is a fixed-layout struct
//! and a handful of constants (in `fidus_core::codes`), so reading it directly
//! keeps the dependency list to `libc` alone (INS-21) and keeps this file
//! auditable.

use std::fs::{File, OpenOptions};
use std::io::{self, Read};
use std::os::fd::{AsRawFd, RawFd};
use std::os::unix::fs::OpenOptionsExt;
use std::path::Path;

/// One decoded kernel input event.
pub struct InputEvent {
    /// Monotonic microseconds. The kernel timestamps events with the clock
    /// selected on the fd; we select `CLOCK_MONOTONIC` so time is never
    /// wall-clock (privacy) and never runs backwards.
    pub time_us: u64,
    pub etype: u16,
    pub code: u16,
    pub value: i32,
}

/// struct input_event on 64-bit Linux: two `long` for the timeval, then
/// u16, u16, i32. 24 bytes. `sizeof(long)` is 8 here; the size is checked so
/// that a wrong target fails to build rather than misparse.
const EVENT_SIZE: usize = 24;
const _: () = assert!(std::mem::size_of::<libc::c_long>() == 8);

pub struct EvdevReader {
    file: File,
    buf: [u8; EVENT_SIZE * 64],
    filled: usize,
    cursor: usize,
}

impl EvdevReader {
    pub fn open(path: &Path) -> io::Result<Self> {
        let file = OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NONBLOCK)
            .open(path)?;
        // Ask the kernel to timestamp with CLOCK_MONOTONIC.
        set_clock_monotonic(file.as_raw_fd())?;
        Ok(Self {
            file,
            buf: [0u8; EVENT_SIZE * 64],
            filled: 0,
            cursor: 0,
        })
    }

    pub fn raw_fd(&self) -> RawFd {
        self.file.as_raw_fd()
    }

    /// Read one event, or `None` when the fd has no more data ready (EAGAIN).
    pub fn next_event(&mut self) -> io::Result<Option<InputEvent>> {
        if self.cursor + EVENT_SIZE > self.filled {
            self.refill()?;
            if self.filled < EVENT_SIZE {
                return Ok(None);
            }
        }
        let e = parse(&self.buf[self.cursor..self.cursor + EVENT_SIZE]);
        self.cursor += EVENT_SIZE;
        Ok(Some(e))
    }

    fn refill(&mut self) -> io::Result<()> {
        self.cursor = 0;
        self.filled = 0;
        match self.file.read(&mut self.buf) {
            Ok(n) => {
                // The kernel only ever returns whole events.
                self.filled = n - (n % EVENT_SIZE);
                Ok(())
            }
            Err(e) if e.kind() == io::ErrorKind::WouldBlock => Ok(()),
            Err(e) => Err(e),
        }
    }
}

fn parse(b: &[u8]) -> InputEvent {
    let sec = i64::from_ne_bytes(b[0..8].try_into().unwrap());
    let usec = i64::from_ne_bytes(b[8..16].try_into().unwrap());
    let etype = u16::from_ne_bytes(b[16..18].try_into().unwrap());
    let code = u16::from_ne_bytes(b[18..20].try_into().unwrap());
    let value = i32::from_ne_bytes(b[20..24].try_into().unwrap());
    InputEvent {
        time_us: (sec as u64)
            .wrapping_mul(1_000_000)
            .wrapping_add(usec as u64),
        etype,
        code,
        value,
    }
}

fn set_clock_monotonic(fd: RawFd) -> io::Result<()> {
    // EVIOCSCLOCKID with CLOCK_MONOTONIC.
    const EVIOCSCLOCKID: libc::c_ulong = 0x4004_45a0;
    let clk: libc::c_int = libc::CLOCK_MONOTONIC;
    // Safety: the ioctl reads one c_int through the pointer.
    let rc = unsafe { libc::ioctl(fd, EVIOCSCLOCKID, &clk as *const libc::c_int) };
    if rc != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_matches_the_abi_layout() {
        let mut b = [0u8; EVENT_SIZE];
        b[0..8].copy_from_slice(&12i64.to_ne_bytes());
        b[8..16].copy_from_slice(&345_678i64.to_ne_bytes());
        b[16..18].copy_from_slice(&1u16.to_ne_bytes());
        b[18..20].copy_from_slice(&30u16.to_ne_bytes());
        b[20..24].copy_from_slice(&1i32.to_ne_bytes());
        let e = parse(&b);
        assert_eq!(e.time_us, 12_345_678);
        assert_eq!(e.etype, 1);
        assert_eq!(e.code, 30);
        assert_eq!(e.value, 1);
    }
}
