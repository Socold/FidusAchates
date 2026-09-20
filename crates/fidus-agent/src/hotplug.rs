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
            let mut off = 0usize;
            let n = n as usize;
            while off + std::mem::size_of::<libc::inotify_event>() <= n {
                // Safety: off is within the bytes just read and aligned to the
                // event stream produced by the kernel.
                let ev = unsafe { &*(self.buf.as_ptr().add(off) as *const libc::inotify_event) };
                let len = ev.len as usize;
                let name_start = off + std::mem::size_of::<libc::inotify_event>();
                if len > 0 && name_start + len <= n {
                    let raw = &self.buf[name_start..name_start + len];
                    let end = raw.iter().position(|&b| b == 0).unwrap_or(len);
                    if let Ok(name) = std::str::from_utf8(&raw[..end]) {
                        if name.starts_with("event") {
                            names.push(name.to_string());
                        }
                    }
                }
                off = name_start + len;
            }
        }
        Ok(names)
    }
}

impl Drop for Inotify {
    fn drop(&mut self) {
        // Safety: fd owned by self, closed once.
        unsafe { libc::close(self.fd) };
    }
}
