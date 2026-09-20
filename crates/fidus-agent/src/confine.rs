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

/// True if creating an internet socket fails and io_uring cannot be set up,
/// as both must after `lock_down`.
pub fn network_is_blocked() -> bool {
    if !io_uring_is_blocked() {
        return false;
    }
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

/// io_uring_setup must be refused: ENOSYS by our filter, or EPERM when the
/// system itself has io_uring disabled (kernel.io_uring_disabled). Before any
/// of that, a null params pointer yields EFAULT, so the errno tells them apart.
fn io_uring_is_blocked() -> bool {
    // Safety: the kernel validates the pointer; a null one never dereferences.
    let rc = unsafe { libc::syscall(libc::SYS_io_uring_setup, 1u32, std::ptr::null::<u8>()) };
    if rc >= 0 {
        unsafe { libc::close(rc as i32) };
        return false;
    }
    matches!(
        io::Error::last_os_error().raw_os_error(),
        Some(libc::ENOSYS) | Some(libc::EPERM)
    )
}

fn set_no_new_privs() -> io::Result<()> {
    // Safety: prctl with PR_SET_NO_NEW_PRIVS takes no pointer.
    let rc = unsafe { libc::prctl(libc::PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) };
    if rc != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

// A classic BPF program for seccomp. Three things, in order:
//   1. Refuse any syscall not from the native ABI. On x86_64 a 32-bit call via
//      int 0x80 uses a different syscall table, where "socket" has another
//      number; without this check the filter could be bypassed by switching
//      ABI. Such a call is killed, not merely refused.
//   2. Refuse io_uring_setup, because an io_uring ring can create sockets
//      (IORING_OP_SOCKET) without ever calling socket(2).
//   3. For socket(2), refuse the internet and packet families with EPERM,
//      allowing UNIX sockets (the console IPC) and the rest.
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
    const ARCH: u32 = 4;
    const ARG0_LOW: u32 = 16;

    // BPF opcodes.
    const LD_W_ABS: u16 = 0x20;
    const JEQ_K: u16 = 0x15;
    const RET_K: u16 = 0x06;

    const ALLOW: u32 = 0x7fff_0000; // SECCOMP_RET_ALLOW
    const EPERM: u32 = 0x0005_0000 | 1; // SECCOMP_RET_ERRNO | EPERM
    const ENOSYS: u32 = 0x0005_0000 | 38; // SECCOMP_RET_ERRNO | ENOSYS
    const KILL_PROCESS: u32 = 0x8000_0000; // SECCOMP_RET_KILL_PROCESS

    #[cfg(target_arch = "x86_64")]
    const ARCH_NATIVE: u32 = 0xC000_003E; // AUDIT_ARCH_X86_64
    #[cfg(target_arch = "aarch64")]
    const ARCH_NATIVE: u32 = 0xC000_00B7; // AUDIT_ARCH_AARCH64
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    compile_error!("seccomp filter: add the AUDIT_ARCH constant for this architecture");

    let nr_socket = libc::SYS_socket as u32;
    let nr_io_uring_setup = libc::SYS_io_uring_setup as u32;

    // Program. Indices in brackets; jt/jf are offsets from the *next*
    // instruction. ALLOW [9], EPERM [10], KILL [11], ENOSYS [12].
    //
    //   [0]  A = arch
    //   [1]  if A != native          -> KILL   [11]  (jf = 9)
    //   [2]  A = nr
    //   [3]  if A == io_uring_setup  -> ENOSYS [12]  (jt = 8)
    //   [4]  if A != socket          -> ALLOW  [9]   (jf = 4)
    //   [5]  A = arg0 low 32 bits
    //   [6]  if A == AF_INET         -> EPERM  [10]  (jt = 3)
    //   [7]  if A == AF_INET6        -> EPERM  [10]  (jt = 2)
    //   [8]  if A == AF_PACKET       -> EPERM  [10]  (jt = 1)
    //   [9]  return ALLOW
    //   [10] return EPERM
    //   [11] return KILL_PROCESS
    //   [12] return ENOSYS
    //
    // A wrong jump here can make the process refuse itself every syscall; the
    // integration test runs the real binary's self-test to catch that.
    let prog = [
        SockFilter {
            code: LD_W_ABS,
            jt: 0,
            jf: 0,
            k: ARCH,
        },
        SockFilter {
            code: JEQ_K,
            jt: 0,
            jf: 9,
            k: ARCH_NATIVE,
        },
        SockFilter {
            code: LD_W_ABS,
            jt: 0,
            jf: 0,
            k: NR,
        },
        SockFilter {
            code: JEQ_K,
            jt: 8,
            jf: 0,
            k: nr_io_uring_setup,
        },
        SockFilter {
            code: JEQ_K,
            jt: 0,
            jf: 4,
            k: nr_socket,
        },
        SockFilter {
            code: LD_W_ABS,
            jt: 0,
            jf: 0,
            k: ARG0_LOW,
        },
        SockFilter {
            code: JEQ_K,
            jt: 3,
            jf: 0,
            k: libc::AF_INET as u32,
        },
        SockFilter {
            code: JEQ_K,
            jt: 2,
            jf: 0,
            k: libc::AF_INET6 as u32,
        },
        SockFilter {
            code: JEQ_K,
            jt: 1,
            jf: 0,
            k: libc::AF_PACKET as u32,
        },
        SockFilter {
            code: RET_K,
            jt: 0,
            jf: 0,
            k: ALLOW,
        },
        SockFilter {
            code: RET_K,
            jt: 0,
            jf: 0,
            k: EPERM,
        },
        SockFilter {
            code: RET_K,
            jt: 0,
            jf: 0,
            k: KILL_PROCESS,
        },
        SockFilter {
            code: RET_K,
            jt: 0,
            jf: 0,
            k: ENOSYS,
        },
    ];
    assert!(prog.len() * size_of::<SockFilter>() < u16::MAX as usize);

    let fprog = SockFprog {
        len: prog.len() as u16,
        filter: prog.as_ptr(),
    };

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
