"""Action sensitivity (work package 9): the acceptance scenarios 9.1 and 9.2,
the parsing of the hook's file, and the hook's classifier itself."""

import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from fidus_lab import ActorLabel, Outcome, SanctionRegistry, Sensitivity, attribute, decide
from fidus_lab.sensitivity import (
    ActionEvent,
    ActionLog,
    follow,
    parse_line,
    sensitivity_of,
)

from .test_attribution import one_segment, robotic_typing

HOOK = Path(__file__).resolve().parents[2] / "contrib" / "shell" / "fidus-actions.bash"


def unsanctioned_segment():
    seg = one_segment(robotic_typing(start=1_000_000))
    assert attribute(seg, SanctionRegistry()).label == ActorLabel.AUTOMATION_UNSANCTIONED
    return seg


def outcome_with(actions):
    seg = unsanctioned_segment()
    log = ActionLog()
    for a in actions:
        log.add(ActionEvent(seg.end_us, a))
    sens, _ = log.sensitivity(seg)
    return decide(ActorLabel.AUTOMATION_UNSANCTIONED, identity_diverged=False, sensitivity=sens)


def test_9_1_benign_read_only_automation_stays_a_tag():
    assert outcome_with(["read", "vcs", "read"]) == Outcome.TAG
    assert outcome_with(["network", "package"]) == Outcome.TAG  # medium is not enough


def test_9_2_elevating_or_mass_deleting_automation_alerts():
    assert outcome_with(["read", "elevation"]) == Outcome.ALERT
    assert outcome_with(["destructive"]) == Outcome.ALERT
    assert outcome_with(["credentials"]) == Outcome.ALERT


def test_actions_outside_the_segment_do_not_count():
    seg = unsanctioned_segment()
    log = ActionLog()
    log.add(ActionEvent(seg.start_us - 10_000_000, "elevation"))
    log.add(ActionEvent(seg.end_us + 60_000_000, "destructive"))
    assert log.sensitivity(seg) == (Sensitivity.LOW, [])


def test_sensitivity_levels():
    assert sensitivity_of([]) == Sensitivity.LOW
    assert sensitivity_of(["files", "other"]) == Sensitivity.LOW
    assert sensitivity_of(["containers"]) == Sensitivity.MEDIUM
    assert sensitivity_of(["read", "elevation"]) == Sensitivity.HIGH


def test_parse_line_maps_wall_clock_to_monotonic_and_rejects_junk():
    ev = parse_line("1000,5 elevation", now_real=1002.5, now_mono_us=50_000_000)
    assert ev == ActionEvent(48_000_000, "elevation")
    assert parse_line("1000.5 read", 1000.5, 7).time_us == 7
    assert parse_line("1000.5 rm -rf /", 1000.5, 7) is None      # not a class
    assert parse_line("1000.5 secret", 1000.5, 7) is None
    assert parse_line("nope read", 1000.5, 7) is None
    assert parse_line("1.0 read", 1_000_000.0, 7) is None         # older than kept
    assert parse_line("x" * 100, 1000.5, 7) is None


def test_follow_tails_only_new_lines(tmp_path):
    path = tmp_path / "fidusachates" / "actions"
    path.parent.mkdir()
    path.write_text(f"{time.time():.6f} destructive\n")  # before the daemon: ignored
    log, stop = ActionLog(), threading.Event()
    th = threading.Thread(target=follow, args=(path, log, stop, lambda: 10**12, 0.05))
    th.start()
    time.sleep(0.15)
    with open(path, "a") as fh:
        fh.write(f"{time.time():.6f} elevation\n{time.time():.6f} bogus\n")
    time.sleep(0.3)
    stop.set()
    th.join()
    assert [e.action for e in log._events] == ["elevation"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="no bash")
@pytest.mark.parametrize("line,cls", [
    ("ls -la", "read"),
    ("sudo dnf upgrade", "elevation"),
    ("rm -rf build", "destructive"),
    ("rm notes.txt", "files"),
    ("git push --force origin main", "destructive"),
    ("git push origin main", "vcs"),
    ("dd if=a of=/dev/sdb", "destructive"),
    ("LANG=C curl https://example.org", "network"),
    ("ssh-keygen -t ed25519", "credentials"),
    ("docker ps", "containers"),
    ("frobnicate", "other"),
])
def test_hook_classifier(line, cls):
    script = (f'eval "$(sed -n "/^__fidus_class()/,/^}}/p" {HOOK})"; '
              f'read -ra w <<<"{line}"; __fidus_class "${{w[@]}}"')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == cls
