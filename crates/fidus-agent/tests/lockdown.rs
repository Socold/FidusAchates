//! Integration test of the network lockdown, on the real binary.
//!
//! The seccomp filter is the most security-critical code in the agent and a
//! unit test cannot exercise it (installing a filter changes the test process
//! for good). So we spawn the built binary's `selftest` command: exit 0 means
//! the lockdown is installed and effective (sockets and io_uring refused).
//! Exit 2 means the environment forbids seccomp (a container); the test is
//! then skipped rather than faked. Anything else is a failure.

use std::process::Command;

#[test]
fn the_real_binary_locks_itself_down() {
    let out = Command::new(env!("CARGO_BIN_EXE_fidus-agent"))
        .arg("selftest")
        .output()
        .expect("spawn fidus-agent");
    match out.status.code() {
        Some(0) => {}
        Some(2) => {
            eprintln!(
                "skipped: seccomp unavailable in this environment ({})",
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
        other => panic!(
            "lockdown selftest failed with {:?}: {}",
            other,
            String::from_utf8_lossy(&out.stderr)
        ),
    }
}
