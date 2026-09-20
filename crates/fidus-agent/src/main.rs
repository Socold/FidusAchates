//! FidusAchates recorder (work package 1).
//!
//! The only component that reads `/dev/input`. It captures events, hands each
//! one to `fidus-core` for reduction to classes, and (with the `research-trace`
//! feature) writes reduced records to a trace. It never touches the network,
//! and enforces that itself before doing anything else.

mod confine;
mod device;
mod evdev;
mod hotplug;
mod loop_;
mod signal;
#[cfg(feature = "research-trace")]
mod writer;

use std::process::ExitCode;

fn main() -> ExitCode {
    let mut args = std::env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "help".into());

    // Self-confinement comes first, before any device is opened, so that a bug
    // in capture cannot precede the network lockdown (SR-3, INS-14).
    if matches!(command.as_str(), "record" | "devices" | "doctor") {
        if let Err(e) = confine::lock_down() {
            eprintln!("fidus-agent: could not confine the process: {e}");
            return ExitCode::FAILURE;
        }
    }

    let result = match command.as_str() {
        "record" => loop_::run(args.collect()),
        "devices" => device::list_command(),
        "doctor" => doctor(),
        "help" | "--help" | "-h" => {
            print_help();
            Ok(())
        }
        other => {
            eprintln!("fidus-agent: unknown command '{other}'");
            print_help();
            return ExitCode::FAILURE;
        }
    };

    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("fidus-agent: {e}");
            ExitCode::FAILURE
        }
    }
}

fn print_help() {
    eprintln!(
        "fidus-agent (recorder)\n\
         \n\
         Commands:\n\
         \x20 record [--trace FILE]   capture and reduce input events\n\
         \x20 devices                 list readable input devices and provenance\n\
         \x20 doctor                  check prerequisites\n\
         \n\
         The recorder reads /dev/input and keeps only behavioural classes and\n\
         timings. It has no network access, by construction."
    );
}

fn doctor() -> std::io::Result<()> {
    println!("fidus-agent doctor");

    let confined = confine::network_is_blocked();
    println!(
        "  network sockets blocked : {}",
        if confined {
            "yes"
        } else {
            "NO (self-test failed)"
        }
    );

    let devices = device::discover()?;
    let readable = devices.iter().filter(|d| d.readable).count();
    println!(
        "  input devices           : {} total, {} readable",
        devices.len(),
        readable
    );
    if readable == 0 {
        println!("  hint: add yourself to the 'input' group, or install the capture helper");
    }

    #[cfg(feature = "research-trace")]
    println!("  build                   : research-trace ENABLED (writes reduced traces)");
    #[cfg(not(feature = "research-trace"))]
    println!("  build                   : release (no event-writing code)");

    Ok(())
}
