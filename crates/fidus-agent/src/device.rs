//! Discovery of input devices and their provenance.
//!
//! A device is virtual when it has no backing hardware bus. Under Linux, the
//! sysfs path of a real device passes through a physical bus controller, while
//! a `uinput`-created device sits under `/devices/virtual/`. That distinction
//! is what feeds the provenance flag (FR-2) and, later, the Humanity channel.

use fidus_core::record::Provenance;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

pub struct Device {
    pub index: u16,
    pub path: PathBuf,
    pub name: String,
    pub provenance: Provenance,
    pub readable: bool,
}

/// List `/dev/input/event*`, resolving provenance and readability for each.
pub fn discover() -> io::Result<Vec<Device>> {
    let mut out = Vec::new();
    let mut entries: Vec<PathBuf> = fs::read_dir("/dev/input")?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.starts_with("event"))
        })
        .collect();
    entries.sort();

    for path in entries {
        if let Some(d) = describe(&path) {
            out.push(d);
        }
    }
    Ok(out)
}

/// Describe a single `/dev/input/eventN` path, or `None` if it is not an
/// event node. Used by hot-plug to add a device that appeared after start.
pub fn describe(path: &Path) -> Option<Device> {
    let name = path.file_name()?.to_str()?;
    if !name.starts_with("event") {
        return None;
    }
    // The index is the trailing number, so a device keeps the same index
    // whether it is found at startup or by hot-plug.
    let index = name.strip_prefix("event")?.parse::<u16>().ok()?;
    Some(Device {
        index,
        name: event_name(path).unwrap_or_default(),
        provenance: provenance_of(path),
        readable: is_readable(path),
        path: path.to_path_buf(),
    })
}

/// Provenance from the sysfs topology of an `eventN` node.
fn provenance_of(dev_path: &Path) -> Provenance {
    let Some(name) = dev_path.file_name().and_then(|n| n.to_str()) else {
        return Provenance::Hardware;
    };
    // /sys/class/input/eventN is a symlink into the device tree. A virtual
    // device resolves under .../devices/virtual/...
    let link = PathBuf::from(format!("/sys/class/input/{name}"));
    match fs::canonicalize(&link) {
        Ok(real) => {
            if real.components().any(|c| c.as_os_str() == "virtual") {
                Provenance::Virtual
            } else {
                Provenance::Hardware
            }
        }
        Err(_) => Provenance::Hardware,
    }
}

fn event_name(dev_path: &Path) -> Option<String> {
    let name = dev_path.file_name()?.to_str()?;
    let p = format!("/sys/class/input/{name}/device/name");
    fs::read_to_string(p).ok().map(|s| s.trim().to_string())
}

fn is_readable(path: &Path) -> bool {
    use std::os::unix::fs::OpenOptionsExt;
    fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NONBLOCK)
        .open(path)
        .is_ok()
}

pub fn list_command() -> io::Result<()> {
    let devices = discover()?;
    if devices.is_empty() {
        println!("no /dev/input/event* devices found");
        return Ok(());
    }
    for d in &devices {
        println!(
            "  [{:2}] {:8} {:10} {}",
            d.index,
            if d.readable { "readable" } else { "denied" },
            match d.provenance {
                Provenance::Hardware => "hardware",
                Provenance::Virtual => "virtual",
            },
            d.name,
        );
    }
    Ok(())
}
