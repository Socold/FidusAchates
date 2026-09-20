//! The capture loop: block on `epoll`, reduce each event, count or write it.
//!
//! No polling: the loop sleeps in `epoll_wait` with no timeout, so with no
//! input the process does not run and the CPU is free to sleep (INS-1, INS-2).
//! It wakes for three things: input on a device, a new device appearing
//! (inotify), or a termination signal (which interrupts the wait).

use crate::confine;
use crate::device::{self, Device};
use crate::evdev::EvdevReader;
use crate::hotplug::Inotify;
use crate::signal;
use fidus_core::record::Provenance;
use fidus_core::reduce::Reducer;
use std::collections::HashSet;
use std::io;
use std::os::fd::RawFd;
use std::path::PathBuf;

// epoll `data` tags: the inotify fd, then device sources by index.
const TAG_INOTIFY: u64 = u64::MAX;

struct Source {
    reader: EvdevReader,
    reducer: Reducer,
    device_index: u16,
    provenance: Provenance,
    path: PathBuf,
    /// Set when the device went away; the slot is kept so epoll tags stay
    /// stable, but it is never read again.
    gone: bool,
}

pub fn run(args: Vec<String>) -> io::Result<()> {
    let trace_path = parse_trace_arg(&args)?;

    #[cfg(not(feature = "research-trace"))]
    if trace_path.is_some() {
        return Err(io::Error::other(
            "this build has no research-trace feature; rebuild with --features research-trace",
        ));
    }

    if !confine::network_is_blocked() {
        return Err(io::Error::other(
            "refusing to capture without network lockdown",
        ));
    }
    signal::install();

    let mut sources: Vec<Source> = Vec::new();
    let mut open_paths: HashSet<PathBuf> = HashSet::new();

    let devices = device::discover()?;
    let epoll = Epoll::new()?;
    for d in &devices {
        add_source(&epoll, &mut sources, &mut open_paths, d)?;
    }
    if sources.is_empty() {
        return Err(io::Error::other(
            "no readable input device; add yourself to the 'input' group or install the helper",
        ));
    }

    let mut hotplug = Inotify::watch_dev_input()?;
    epoll.add(hotplug.raw_fd(), TAG_INOTIFY)?;

    eprintln!(
        "fidus-agent: recording from {} device(s), Ctrl-C to stop",
        sources.len()
    );

    #[cfg(feature = "research-trace")]
    let mut sink = match &trace_path {
        Some(p) => Some(crate::writer::TraceWriter::create(std::path::Path::new(p))?),
        None => None,
    };

    let mut count: u64 = 0;
    let mut events = [libc::epoll_event { events: 0, u64: 0 }; 16];
    while !signal::stop_requested() {
        let n = match epoll.wait(&mut events) {
            Ok(n) => n,
            // A signal interrupted the wait: loop back and check the stop flag.
            Err(ref e) if e.kind() == io::ErrorKind::Interrupted => continue,
            Err(e) => return Err(e),
        };
        for ev in &events[..n] {
            // `epoll_event` is packed, so copy the tag out before use.
            let tag = ev.u64;
            if tag == TAG_INOTIFY {
                for name in hotplug.drain_event_names()? {
                    let path = PathBuf::from("/dev/input").join(&name);
                    // Re-discover so provenance is resolved for the new node.
                    if let Some(d) = device::describe(&path) {
                        if d.readable {
                            let _ = add_source(&epoll, &mut sources, &mut open_paths, &d);
                        }
                    }
                }
                continue;
            }
            let src = &mut sources[tag as usize];
            if src.gone {
                continue;
            }
            loop {
                let input = match src.reader.next_event() {
                    Ok(Some(e)) => e,
                    Ok(None) => break,
                    // The device was unplugged mid-read: retire it without
                    // failing the recorder, and forget its path so the same
                    // device can be captured again when it is plugged back.
                    // Closing the fd removes it from epoll.
                    Err(e) if e.raw_os_error() == Some(libc::ENODEV) => {
                        src.gone = true;
                        open_paths.remove(&src.path);
                        src.reader.close();
                        break;
                    }
                    Err(e) => return Err(e),
                };
                if let Some(_rec) = src.reducer.reduce(
                    input.time_us,
                    src.device_index,
                    src.provenance,
                    input.etype,
                    input.code,
                    input.value,
                ) {
                    count += 1;
                    #[cfg(feature = "research-trace")]
                    if let Some(w) = sink.as_mut() {
                        w.write(&_rec)?;
                    }
                }
            }
        }
    }

    eprintln!("fidus-agent: stopped, {count} reduced events");
    // `sink` drops here, flushing the trace, before the process exits.
    Ok(())
}

fn add_source(
    epoll: &Epoll,
    sources: &mut Vec<Source>,
    open_paths: &mut HashSet<PathBuf>,
    d: &Device,
) -> io::Result<()> {
    if !d.readable || open_paths.contains(&d.path) {
        return Ok(());
    }
    match EvdevReader::open(&d.path) {
        Ok(reader) => {
            let tag = sources.len() as u64;
            epoll.add(reader.raw_fd(), tag)?;
            open_paths.insert(d.path.clone());
            sources.push(Source {
                reader,
                reducer: Reducer::new(),
                device_index: d.index,
                provenance: d.provenance,
                path: d.path.clone(),
                gone: false,
            });
            Ok(())
        }
        Err(e) => {
            eprintln!("fidus-agent: skipping {}: {e}", d.path.display());
            Ok(())
        }
    }
}

fn parse_trace_arg(args: &[String]) -> io::Result<Option<String>> {
    let mut it = args.iter();
    while let Some(a) = it.next() {
        if a == "--trace" {
            return it
                .next()
                .cloned()
                .map(Some)
                .ok_or_else(|| io::Error::other("--trace needs a file path"));
        }
    }
    Ok(None)
}

// A thin epoll wrapper, level-triggered, no timeout.

struct Epoll {
    fd: RawFd,
}

impl Epoll {
    fn new() -> io::Result<Self> {
        // Safety: epoll_create1 takes an int flag and returns an fd.
        let fd = unsafe { libc::epoll_create1(libc::EPOLL_CLOEXEC) };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(Self { fd })
    }

    fn add(&self, fd: RawFd, data: u64) -> io::Result<()> {
        let mut ev = libc::epoll_event {
            events: libc::EPOLLIN as u32,
            u64: data,
        };
        // Safety: epoll_ctl reads one epoll_event for the call.
        let rc = unsafe { libc::epoll_ctl(self.fd, libc::EPOLL_CTL_ADD, fd, &mut ev) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    fn wait(&self, out: &mut [libc::epoll_event]) -> io::Result<usize> {
        // Safety: the kernel writes at most out.len() epoll_events into the
        // buffer, which is exactly an array of libc::epoll_event.
        let n = unsafe { libc::epoll_wait(self.fd, out.as_mut_ptr(), out.len() as i32, -1) };
        if n < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(n as usize)
    }
}

impl Drop for Epoll {
    fn drop(&mut self) {
        // Safety: fd owned by self, closed once.
        unsafe { libc::close(self.fd) };
    }
}
