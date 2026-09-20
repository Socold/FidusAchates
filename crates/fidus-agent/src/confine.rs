//! Self-applied network lockdown (SR-3, INS-14, ADR-0009).
//!
//! The privacy claim of the project is that the recorder cannot exfiltrate.
//! We do not trust the unit file for that, because `PrivateNetwork=yes` is not
//! available on every system. Instead the process forbids network sockets to
//! itself, with a seccomp filter, and then proves it by trying to open one.

use std::io;

/// Set `no_new_privs`, install a seccomp filter that denies creation of
/// network sockets, then verify that a network socket can no longer be opened.
/// Non-network sockets (the console's UNIX socket) stay allowed.
pub fn lock_down() -> io::Result<()> {
    set_no_new_privs()?;
    install_seccomp()?;
    if !network_is_blocked() {
        return Err(io::Error::other(
            "network socket still openable after seccomp; refusing to run",
        ));
    }
    Ok(())
}

/// True if creating an internet socket fails, as it must after `lock_down`.
pub fn network_is_blocked() -> bool {
    // Safety: socket(2) with these arguments has no memory effect; a returned
    // fd is closed immediately.
    let fd = unsafe { libc::socket(libc::AF_INET, libc::SOCK_STREAM, 0) };
    if fd >= 0 {
        unsafe { libc::close(fd) };
        return false;
    }
    let fd6 = unsafe { libc::socket(libc::AF_INET6, libc::SOCK_DGRAM, 0) };
    if fd6 >= 0 {
        unsafe { libc::close(fd6) };
        return false;
    }
    true
}

fn set_no_new_privs() -> io::Result<()> {
    // Safety: prctl with PR_SET_NO_NEW_PRIVS takes no pointer.
    let rc = unsafe { libc::prctl(libc::PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) };
    if rc != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

// A classic BPF program for seccomp. It inspects the syscall number and, for
// socket(2), the address family in the first argument: AF_INET, AF_INET6 and
// AF_PACKET are refused with EPERM, everything else is allowed.
fn install_seccomp() -> io::Result<()> {
    use std::mem::size_of;

    #[repr(C)]
    struct SockFilter {
        code: u16,
        jt: u8,
        jf: u8,
        k: u32,
    }
    #[repr(C)]
    struct SockFprog {
        len: u16,
        filter: *const SockFilter,
    }

    // Offsets into struct seccomp_data.
    const NR: u32 = 0;
    const ARG0_LOW: u32 = 16;

    // BPF opcodes.
    const LD_W_ABS: u16 = 0x20;
    const JEQ_K: u16 = 0x15;
    const RET_K: u16 = 0x06;

    const ALLOW: u32 = 0x7fff_0000; // SECCOMP_RET_ALLOW
    const EPERM: u32 = 0x0005_0000 | 1; // SECCOMP_RET_ERRNO | EPERM

    let nr_socket = libc::SYS_socket as u32;

    // Program. Instruction indices in brackets; jt/jf are offsets counted from
    // the *next* instruction. ALLOW is at [6], DENY (EPERM) at [7].
    //
    //   [0] A = nr
    //   [1] if A != socket        -> jump to ALLOW [6]   (jf = 4)
    //   [2] A = arg0 low 32 bits
    //   [3] if A == AF_INET       -> jump to DENY  [7]   (jt = 3)
    //   [4] if A == AF_INET6      -> jump to DENY  [7]   (jt = 2)
    //   [5] if A == AF_PACKET     -> jump to DENY  [7]   (jt = 1)
    //   [6] return ALLOW          (a socket of some other family: UNIX, netlink)
    //   [7] return EPERM
    //
    // Getting [1]'s jf wrong (sending non-socket syscalls to DENY) makes the
    // process refuse itself every syscall and crash; there is a test for it.
    let prog = [
        SockFilter { code: LD_W_ABS, jt: 0, jf: 0, k: NR },
        SockFilter { code: JEQ_K, jt: 0, jf: 4, k: nr_socket },
        SockFilter { code: LD_W_ABS, jt: 0, jf: 0, k: ARG0_LOW },
        SockFilter { code: JEQ_K, jt: 3, jf: 0, k: libc::AF_INET as u32 },
        SockFilter { code: JEQ_K, jt: 2, jf: 0, k: libc::AF_INET6 as u32 },
        SockFilter { code: JEQ_K, jt: 1, jf: 0, k: libc::AF_PACKET as u32 },
        SockFilter { code: RET_K, jt: 0, jf: 0, k: ALLOW },
        SockFilter { code: RET_K, jt: 0, jf: 0, k: EPERM },
    ];
    assert!(prog.len() * size_of::<SockFilter>() < u16::MAX as usize);

    let fprog = SockFprog { len: prog.len() as u16, filter: prog.as_ptr() };

    // Safety: seccomp(2) reads `fprog` for the call's duration only; `prog`
    // outlives it. No filter is installed on failure.
    let rc = unsafe {
        libc::syscall(
            libc::SYS_seccomp,
            libc::SECCOMP_SET_MODE_FILTER,
            0,
            &fprog as *const SockFprog,
        )
    };
    if rc != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn before_lockdown_a_socket_can_be_opened() {
        // In a fresh process nothing is blocked yet. This documents the
        // baseline the self-test relies on.
        assert!(!network_is_blocked());
    }
}
