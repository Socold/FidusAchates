"""Password entry stays out of the reduced stream: lock screen and prompts
after an elevation or credentials command."""

from fidus_lab.privacy import MAX_ARMED_US, SecretInputFilter
from fidus_lab.trace import DIGRAPH_NONE, Event, EventKind, KeyClass, Record


def key(t, kind, cls=KeyClass.LETTER, digraph=3):
    return Record(t, 0, False, Event(kind, cls, digraph if kind == EventKind.KEY_DOWN else 0))


def press(t, cls=KeyClass.LETTER):
    return [key(t, EventKind.KEY_DOWN, cls), key(t + 50_000, EventKind.KEY_UP, cls)]


def motion(t):
    return Record(t, 1, False, Event(EventKind.MOTION, dx=3, dy=-1))


def run(f, records):
    for r in records:
        f.push(r)
    return f.release(now_us=10**12, flush=True)


def test_nothing_is_dropped_by_default_and_release_waits_for_the_delay():
    f = SecretInputFilter(delay_us=1_000_000)
    recs = press(0) + press(200_000)
    for r in recs:
        f.push(r)
    assert f.release(now_us=500_000) == []          # too recent to judge yet
    assert f.release(now_us=1_300_000) == recs
    assert f.dropped == 0


def test_keys_typed_while_locked_are_dropped_pointer_kept():
    f = SecretInputFilter()
    f.lock_changed(True, at_us=1_000_000)
    f.lock_changed(False, at_us=5_000_000)
    recs = press(500_000) + press(2_000_000) + [motion(2_100_000)] + press(3_000_000, KeyClass.ENTER) + press(6_000_000)
    out = run(f, recs)
    times = [r.time_us for r in out]
    assert 2_000_000 not in times and 3_000_000 not in times
    assert 2_100_000 in times and 500_000 in times and 6_000_000 in times
    # The first key after the dropped span loses its digraph to the password.
    after = [r for r in out if r.time_us == 6_000_000][0]
    assert after.event.digraph == DIGRAPH_NONE


def test_a_prompt_after_sudo_is_dropped_up_to_its_enter():
    f = SecretInputFilter()
    # "sudo dnf upgrade" typed, Enter pressed at 1.00 s, the hook stamps 1.01 s.
    line = press(0) + press(300_000) + [key(1_000_000, EventKind.KEY_DOWN, KeyClass.ENTER)]
    f.arm(1_010_000)
    enter_up = [key(1_060_000, EventKind.KEY_UP, KeyClass.ENTER)]
    password = press(2_000_000) + press(2_200_000, KeyClass.DIGIT) + press(2_400_000) + press(2_600_000, KeyClass.ENTER)
    later = press(5_000_000)
    out = run(f, line + enter_up + password + later)
    times = sorted({r.time_us for r in out})
    assert times == [0, 50_000, 300_000, 350_000, 1_000_000, 5_000_000, 5_050_000]
    assert f.dropped == 9


def test_an_armed_prompt_gives_up_after_a_while():
    f = SecretInputFilter()
    f.arm(0)
    out = run(f, press(1_000) + press(MAX_ARMED_US + 1_000_000))
    assert [r.time_us for r in out] == [MAX_ARMED_US + 1_000_000, MAX_ARMED_US + 1_050_000]
