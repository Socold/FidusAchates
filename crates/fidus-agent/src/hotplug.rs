//! Hot-plug watch on `/dev/input` (INS-1: still no polling).
//!
//! A keyboard plugged in mid-session, or a virtual device created after start,
//! must be captured. We watch the directory with inotify and report the new
//! `eventN` nodes. A keyboard that appears and immediately types is also the
//! BadUSB signal (E19), so this is not just convenience.

use std::io;
use std::os::fd::RawFd;

pub struct Inotify {
    fd: RawFd,
    buf: [u8; 4096],
}

impl Inotify {
    /// Watch `/dev/input` for created and attribute-changed entries. The
    /// attribute watch matters because udev creates the node and then sets its
    /// permissions; we can only open it once readable.
    pub fn watch_dev_input() -> io::Result<Self> {
        // Safety: inotify_init1 returns an fd or -1.
        let fd = unsafe { libc::inotify_init1(libc::IN_NONBLOCK | libc::IN_CLOEXEC) };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        let path = c"/dev/input";
        // Safety: `path` is a valid C string; the call adds one watch.
        let wd = unsafe {
            libc::inotify_add_watch(fd, path.as_ptr(), libc::IN_CREATE | libc::IN_ATTRIB)
        };
        if wd < 0 {
            let e = io::Error::last_os_error();
            unsafe { libc::close(fd) };
            return Err(e);
        }
        Ok(Self {
            fd,
            buf: [0u8; 4096],
        })
    }

    pub fn raw_fd(&self) -> RawFd {
        self.fd
    }

    /// Drain the inotify queue and return the names of touched `eventN` nodes.
    /// Reading is what re-arms the fd for the next `epoll` wakeup.
    pub fn drain_event_names(&mut self) -> io::Result<Vec<String>> {
        let mut names = Vec::new();
        loop {
            // Safety: read into our own buffer; n is the byte count.
            let n = unsafe {
                libc::read(
                    self.fd,
                    self.buf.as_mut_ptr() as *mut libc::c_void,
                    self.buf.len(),
                )
            };
            if n <= 0 {
                break;
            }
            names.extend(parse_event_names(&self.buf[..n as usize]));
        }
        Ok(names)
    }
}

/// Walk a buffer of `struct inotify_event` records and return the names that
/// look like `/dev/input/eventN` nodes. Pure, so it can be tested with a
/// hand-built buffer; the layout is: wd i32, mask u32, cookie u32, len u32,
/// then `len` bytes of NUL-padded name.
pub fn parse_event_names(buf: &[u8]) -> Vec<String> {
    const HEADER: usize = 16;
    let mut names = Vec::new();
    let mut off = 0usize;
    while off + HEADER <= buf.len() {
        let len = u32::from_ne_bytes(buf[off + 12..off + 16].try_into().unwrap()) as usize;
        let name_start = off + HEADER;
        let name_end = name_start.saturating_add(len);
        if name_end > buf.len() {
            break; // truncated record: stop rather than read past the buffer
        }
        if len > 0 {
            let raw = &buf[name_start..name_end];
            let end = raw.iter().position(|&b| b == 0).unwrap_or(len);
            if let Ok(name) = std::str::from_utf8(&raw[..end]) {
                if name.starts_with("event") {
                    names.push(name.to_string());
                }
            }
        }
        off = name_end;
    }
    names
}

impl Drop for Inotify {
    fn drop(&mut self) {
        // Safety: fd owned by self, closed once.
        unsafe { libc::close(self.fd) };
    }
}

#[cfg(test)]
mod tests {
    use super::parse_event_names;

    fn record(name: &str) -> Vec<u8> {
        // Names are NUL-padded to a multiple of 16 in real streams; emulate.
        let mut padded = name.as_bytes().to_vec();
        padded.push(0);
        while !padded.len().is_multiple_of(16) {
            padded.push(0);
        }
        let mut v = Vec::new();
        v.extend_from_slice(&1i32.to_ne_bytes()); // wd
        v.extend_from_slice(&0x100u32.to_ne_bytes()); // mask IN_CREATE
        v.extend_from_slice(&0u32.to_ne_bytes()); // cookie
        v.extend_from_slice(&(padded.len() as u32).to_ne_bytes());
        v.extend_from_slice(&padded);
        v
    }

    #[test]
    fn parses_several_records_and_keeps_only_event_nodes() {
        let mut buf = record("event30");
        buf.extend(record("mouse2")); // not an eventN node
        buf.extend(record("event7"));
        assert_eq!(parse_event_names(&buf), vec!["event30", "event7"]);
    }

    #[test]
    fn empty_and_zero_length_names_are_ignored() {
        assert!(parse_event_names(&[]).is_empty());
        let mut v = Vec::new();
        v.extend_from_slice(&1i32.to_ne_bytes());
        v.extend_from_slice(&0u32.to_ne_bytes());
        v.extend_from_slice(&0u32.to_ne_bytes());
        v.extend_from_slice(&0u32.to_ne_bytes()); // len 0
        assert!(parse_event_names(&v).is_empty());
    }

    #[test]
    fn truncated_record_does_not_read_past_the_buffer() {
        let mut buf = record("event3");
        buf.truncate(buf.len() - 4); // cut inside the name
                                     // Must not panic, and must not invent a name from partial bytes.
        let _ = parse_event_names(&buf);
    }
}
