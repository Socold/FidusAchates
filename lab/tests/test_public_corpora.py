"""Ingestion and protocols for the public corpora, on tiny synthetic files in
the CMU and Balabit shapes. No real data is shipped or read here."""

import random

from fidus_lab.corpus import (
    balabit_sessions,
    cmu_class_features,
    cmu_columns,
    cmu_digraph_classes,
    cmu_keys,
    cmu_pair_features,
    cmu_records,
    digraph_class,
    load_balabit_labels,
    load_balabit_session,
    load_cmu,
)
from fidus_lab.experts.keystroke import _hold_times
from fidus_lab.metrics import eer_exact
from fidus_lab.public_eval import (
    balabit_user_eers,
    cmu_keystroke_expert,
    cmu_manhattan,
    cmu_same_class_rollover,
    cmu_split,
    run_balabit,
    windows,
)
from fidus_lab.segment import Segment
from fidus_lab.trace import DIGRAPH_NONE, EventKind, KeyClass, has_digraph

# The real CMU header shape: H, then DD and UD to the next key, Return last.
KEYS = ["period", "t", "i", "e", "five", "Shift.r", "o", "a", "n", "l", "Return"]


def _header():
    cols = []
    for a, b in zip(KEYS, KEYS[1:], strict=False):
        cols += [f"H.{a}", f"DD.{a}.{b}", f"UD.{a}.{b}"]
    return ["subject", "sessionIndex", "rep", *cols, "H.Return"]


def _cmu_csv(tmp_path, subjects=3, reps=12, seed=0):
    r = random.Random(seed)
    header = _header()
    rows = [",".join(header)]
    for s in range(subjects):
        hold, gap = 0.08 + 0.03 * s, 0.15 + 0.06 * s
        for rep in range(reps):
            vals = []
            for _ in KEYS[:-1]:
                h = abs(r.gauss(hold, 0.01))
                dd = abs(r.gauss(gap, 0.02))
                vals += [h, dd, dd - h]
            vals.append(abs(r.gauss(hold, 0.01)))
            rows.append(",".join([f"s{s:03d}", "1", str(rep), *(f"{v:.4f}" for v in vals)]))
    p = tmp_path / "cmu.csv"
    p.write_text("\n".join(rows) + "\n")
    return str(p)


def test_digraph_class_matches_the_recorder():
    # The cases of biomech.rs: relation in bits 0-2, row distance in bits 3-4.
    assert digraph_class("f", "j") == 5 | (0 << 3)   # alternating, same row
    assert digraph_class("f", "r") == 2 | (1 << 3)   # same finger, one row
    assert digraph_class("f", "d") & 7 == 3          # same hand adjacent
    assert digraph_class("f", "s") & 7 == 4          # same hand distant
    assert digraph_class("f", "f") & 7 == 1          # repeat
    assert digraph_class("4", "v") >> 3 == 2         # two rows or more
    assert digraph_class("f", " ") == DIGRAPH_NONE
    assert digraph_class(None, "f") == DIGRAPH_NONE


def test_cmu_password_classes():
    cols = [c for c in _header() if c.startswith(("H.", "DD.", "UD."))]
    assert cmu_keys(cols) == KEYS
    classes = cmu_digraph_classes(cols)
    assert len(classes) == 10
    # five -> Shift.r is five -> r (the modifier is skipped): same left index.
    assert classes[4] & 7 == 2
    # l -> Return leaves the main block: no class, as live.
    assert classes[-1] == DIGRAPH_NONE
    assert all(has_digraph(c) for c in classes[:-1])


def test_cmu_records_rebuild_the_timing(tmp_path):
    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    s = load_cmu(path)[0]
    vals = dict(zip(cols, s.features, strict=True))
    recs = cmu_records(s, cols)
    assert [r.time_us for r in recs] == sorted(r.time_us for r in recs)
    downs = [r for r in recs if r.event.kind == EventKind.KEY_DOWN]
    assert len(downs) == 11
    assert downs[1].time_us - downs[0].time_us == round(vals["DD.period.t"] * 1e6)
    assert downs[0].event.key_class == KeyClass.PUNCTUATION
    assert downs[4].event.key_class == KeyClass.DIGIT
    assert downs[-1].event.key_class == KeyClass.ENTER
    assert downs[0].event.digraph == DIGRAPH_NONE
    # Pair mode: a distinct tag per classed pair, all accepted as digraphs.
    pair = [r.event.digraph for r in cmu_records(s, cols, pair_digraphs=True)
            if r.event.kind == EventKind.KEY_DOWN]
    tagged = [d for d in pair if has_digraph(d)]
    assert len(tagged) == len(set(tagged)) == 9


def test_cmu_feature_views(tmp_path):
    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    s = load_cmu(path)[0]
    assert len(cmu_pair_features(s, cols)) == 11 + 9
    # Four key classes and six distinct digraph classes in this password.
    assert len(cmu_class_features(s, cols)) == 4 + 6


def test_cmu_protocol_split_and_detectors(tmp_path):
    path = _cmu_csv(tmp_path)
    samples = load_cmu(path)
    split = cmu_split(samples, n_train=8, n_impostor=2)
    train, gen, imp = split["s000"]
    assert len(train) == 8 and len(gen) == 4 and len(imp) == 4
    assert all(s.subject != "s000" for s in imp)
    # Distinct synthetic subjects are separable by every view.
    assert cmu_manhattan(samples, n_train=8, n_impostor=2).mean < 0.2
    cols = cmu_columns(path)
    assert cmu_keystroke_expert(samples, cols, n_train=8, n_impostor=2).mean < 0.2
    assert cmu_keystroke_expert(samples, cols, pair_digraphs=True,
                                n_train=8, n_impostor=2).mean < 0.2


def test_rollover_and_the_expert_hold_matcher(tmp_path):
    path = _cmu_csv(tmp_path)
    cols = cmu_columns(path)
    s = load_cmu(path)[0]
    # A rep where every next key goes down before the previous one is up.
    vals = dict(zip(cols, s.features, strict=True))
    for a, b in zip(KEYS, KEYS[1:], strict=False):
        vals[f"H.{a}"] = 0.2
        vals[f"DD.{a}.{b}"] = 0.1
    s.features = [vals[c] for c in cols]
    assert cmu_same_class_rollover([s], cols) == 1.0
    recs = cmu_records(s, cols)
    seg = Segment(recs[0].time_us, recs[-1].time_us, recs)
    holds = [h for kc, h in _hold_times(seg) if kc == KeyClass.LETTER]
    assert len(holds) == 8 and all(abs(h - 200_000) < 2 for h in holds)


def test_eer_exact():
    assert eer_exact([0.0, 0.1], [1.0, 2.0]) == 0.0
    # One impostor below one genuine score: at threshold 4, FAR = FRR = 1/4.
    assert abs(eer_exact([1, 2, 3, 4], [3.5, 5, 6, 7]) - 0.25) < 1e-9


def _balabit_csv(path, r, speed, click_s, t0=0.0, n=40):
    rows = ["record timestamp,client timestamp,button,state,x,y"]
    t, x, y = t0, 500, 400
    for _ in range(n):
        for _ in range(15):
            t += 0.016
            x += int(speed * r.uniform(0.5, 1.5))
            y -= int(speed * r.uniform(0.2, 0.8))
            rows.append(f"{t:.3f},{t:.3f},NoButton,Move,{x},{y}")
        t += r.uniform(0.2, 0.4)
        rows.append(f"{t:.3f},{t:.3f},Left,Pressed,{x},{y}")
        t += click_s * r.uniform(0.8, 1.2)
        rows.append(f"{t:.3f},{t:.3f},Left,Released,{x},{y}")
        t += 0.016
        rows.append(f"{t:.3f},{t:.3f},Scroll,Down,{x},{y}")
        t += 0.5
    path.write_text("\n".join(rows) + "\n")


def test_balabit_session_ingest(tmp_path):
    p = tmp_path / "s"
    p.write_text(
        "record timestamp,client timestamp,button,state,x,y\n"
        "0.0,0.0,NoButton,Move,100,100\n"
        "0.0,0.016,NoButton,Move,103,96\n"
        "0.0,0.010,NoButton,Drag,103,90\n"   # out of order: clamped
        "0.1,0.100,Left,Pressed,103,90\n"
        "0.2,0.200,Left,Released,103,90\n"
        "0.3,0.300,Scroll,Up,103,90\n"
    )
    recs = load_balabit_session(str(p))
    kinds = [r.event.kind for r in recs]
    assert kinds == [EventKind.MOTION, EventKind.MOTION, EventKind.BUTTON_DOWN,
                     EventKind.BUTTON_UP, EventKind.WHEEL]
    assert (recs[0].event.dx, recs[0].event.dy) == (3, -4)
    assert recs[1].time_us == 16_000  # never goes back in time
    assert recs[2].event.button == 0 and recs[4].event.dy == 1
    split = load_balabit_session(str(p), split_axes=True)
    motion = [(r.event.dx, r.event.dy) for r in split if r.event.kind == EventKind.MOTION]
    assert motion == [(3, 0), (0, -4), (0, -6)]


def test_windows_and_user_eers():
    assert windows([1, 2, 3, 4, 5], 2) == [3, 7]
    out = balabit_user_eers([[0, 0, 0]], [[5, 5, 5]], ks=(1, 3))
    assert out == {"k1": 0.0, "k3": 0.0, "session": 0.0}


def test_balabit_end_to_end(tmp_path):
    """Two synthetic users with different speed and click duration; each
    user's test folder holds one session of each, labelled."""
    r = random.Random(3)
    users = {"user1": (6, 0.08), "user2": (20, 0.25)}
    labels = ["filename,is_illegal"]
    for u, (speed, click) in users.items():
        for k in range(2):
            d = tmp_path / "training_files" / u
            d.mkdir(parents=True, exist_ok=True)
            _balabit_csv(d / f"session_{u}_tr{k}", r, speed, click)
        d = tmp_path / "test_files" / u
        d.mkdir(parents=True, exist_ok=True)
        other = users["user2" if u == "user1" else "user1"]
        for k in range(3):
            _balabit_csv(d / f"session_{u}_g{k}", r, speed, click, n=12)
            _balabit_csv(d / f"session_{u}_i{k}", r, *other, n=12)
            labels += [f"session_{u}_g{k},0", f"session_{u}_i{k},1"]
    (tmp_path / "public_labels.csv").write_text("\n".join(labels) + "\n")

    assert load_balabit_labels(str(tmp_path / "public_labels.csv"))["session_user1_i0"]
    assert list(balabit_sessions(str(tmp_path), "training")) == ["user1", "user2"]
    res = run_balabit(str(tmp_path), ks=(1,))
    assert res["counts"]["user1"]["impostor_sessions"] == 3
    assert res["eer"]["session"]["mean"] < 0.2
