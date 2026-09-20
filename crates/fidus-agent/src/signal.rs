//! Clean shutdown on SIGINT and SIGTERM.
//!
//! The capture loop buffers its trace, so it must flush on exit. A killed
//! process does not, which is why we catch the termination signals, set a flag,
//! and let the loop return normally so the writer's flush runs.

use std::sync::atomic::{AtomicBool, Ordering};

static STOP: AtomicBool = AtomicBool::new(false);

/// Install handlers for SIGINT and SIGTERM. Idempotent.
pub fn install() {
    let h = handler as extern "C" fn(libc::c_int) as libc::sighandler_t;
    // Safety: `handler` is async-signal-safe (it only does an atomic store).
    unsafe {
        libc::signal(libc::SIGINT, h);
        libc::signal(libc::SIGTERM, h);
    }
}

extern "C" fn handler(_sig: libc::c_int) {
    STOP.store(true, Ordering::SeqCst);
}

/// True once a termination signal has been received.
pub fn stop_requested() -> bool {
    STOP.load(Ordering::SeqCst)
}
