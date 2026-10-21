"""Usage-aware identity: the category each window is judged in, dwell times,
the C01/C04/C05 habits, and per-usage templates in the engine."""

from fidus_lab.context import (
    CATEGORIES,
    ContextEvent,
    ContextTracker,
    attach,
    read_events,
    write_events,
)
from fidus_lab.engine import IdentityEngine
from fidus_lab.experts import KeystrokeTemplate
from fidus_lab.experts.habits import dwell_bin, dwells, repertoire, switch_intervals
from fidus_lab.learning import Enrolled, fit_contexts
from fidus_lab.segment import Segment, segment_trace
from fidus_lab.synth import Typist

OFFICE = CATEGORIES.index("office")
GAME = CATEGORIES.index("game")

# Me writing (quick, short holds) and me playing (long holds, slower rhythm).
WRITING = dict(hold_mu=11.4, hold_sigma=0.25, gap_mu=11.5, gap_sigma=0.3)
PLAYING = dict(hold_mu=12.2, hold_sigma=0.3, gap_mu=12.3, gap_sigma=0.35)


def typed(params, n, seed, category, keys=40):
    segs, t = [], 0
    for i in range(n):
        recs = Typist(seed=seed + i, **params).type_segment(keys, start_us=t)
        for s in segment_trace(recs):
            s.category = category
            segs.append(s)
        t = recs[-1].time_us + 10_000_000
    return segs


def test_game_is_appended_so_stored_indices_keep_their_meaning():
    assert CATEGORIES[:7] == ("browser", "terminal", "development", "office",
                              "communication", "media", "other")
    assert CATEGORIES[7] == "game"


def test_tracker_measures_dwell_and_it_survives_storage(tmp_path):
    t = ContextTracker()
    evs = [t.tick(0, "browser"), t.tick(40_000_000, "office"), t.tick(41_000_000, "game")]
    assert [e.dwell_us for e in evs] == [None, 40_000_000, 1_000_000]
    assert t.current == GAME
    path = tmp_path / "c.jsonl"
    write_events(path, evs)
    with open(path, "a") as fh:
        fh.write('{"t":5,"c":1,"p":0,"r":null}\n')  # written before dwell existed
    back = list(read_events(path))
    assert back[:3] == evs and back[3].dwell_us is None


def test_attach_gives_the_category_in_focus_at_the_segment_end():
    a = Segment(start_us=10, end_us=20)
    b = Segment(start_us=30, end_us=40)
    c = Segment(start_us=0, end_us=4)
    attach([a, b, c], [ContextEvent(5, OFFICE), ContextEvent(35, GAME, previous=OFFICE)])
    assert a.category == OFFICE and not a.context   # focused before it started
    assert b.category == GAME and len(b.context) == 1
    assert c.category is None


def test_c01_c04_c05_extractors():
    seg = Segment(start_us=0, end_us=1, context=[
        ContextEvent(0, OFFICE, previous=None),
        ContextEvent(1, GAME, previous=OFFICE, dwell_us=3_000_000),
        ContextEvent(2, OFFICE, previous=GAME, dwell_us=900_000_000),
    ])
    assert repertoire(seg) == [OFFICE, GAME, OFFICE]
    assert switch_intervals(seg) == [0, 4]
    assert dwells(seg) == [OFFICE * 5 + 0, GAME * 5 + 4]
    assert dwell_bin(29_999_999) == 1 and dwell_bin(30_000_000) == 2


def test_fit_contexts_needs_enough_of_a_usage():
    few = typed(WRITING, 5, seed=1, category=OFFICE)
    assert fit_contexts(few) == ({}, {})
    many = typed(WRITING, 40, seed=1, category=OFFICE)
    keys, _ = fit_contexts(many)
    assert set(keys) == {OFFICE}


def detected(engine, segs):
    return any(engine.step(s).alarmed for s in segs)


def test_per_usage_templates_catch_an_impostor_borrowing_another_usage():
    # Enrolled on me writing and me playing, as two usages.
    enrol = typed(WRITING, 40, seed=100, category=OFFICE) + typed(PLAYING, 40, seed=300, category=GAME)
    enrolled = Enrolled.fit(enrol)
    assert set(enrolled.context_keystroke) == {OFFICE, GAME}
    # Someone typing a document with my gaming rhythm.
    impostor = typed(PLAYING, 15, seed=700, category=OFFICE)
    with_usage = enrolled.engine()
    assert detected(with_usage, impostor)
    # And it still knows me in each usage.
    me = typed(WRITING, 15, seed=900, category=OFFICE) + typed(PLAYING, 15, seed=950, category=GAME)
    assert not detected(enrolled.engine(), me)


def test_unknown_usage_falls_back_to_the_global_templates():
    enrol = typed(WRITING, 40, seed=100, category=OFFICE)
    eng = Enrolled.fit(enrol).engine()
    seg = typed(WRITING, 1, seed=5, category=None)[0]
    d = eng.step(seg)
    assert d.quality > 0 and isinstance(eng.genuine, KeystrokeTemplate)
    assert IdentityEngine(genuine=KeystrokeTemplate()).context_keystroke == {}


def test_chatting_in_a_game_is_still_me():
    # My game usage holds both: playing, and typing in the game's chat.
    enrol = (typed(WRITING, 40, seed=100, category=OFFICE)
             + typed(PLAYING, 40, seed=300, category=GAME)
             + typed(WRITING, 40, seed=500, category=GAME))
    enrolled = Enrolled.fit(enrol)
    assert len(enrolled.context_keystroke[GAME]) == 2
    assert not detected(enrolled.engine(), typed(WRITING, 15, seed=900, category=GAME))
    # Writing like I play is still caught in an office application.
    assert detected(enrolled.engine(), typed(PLAYING, 15, seed=700, category=OFFICE))
