"""How much the pointer may vouch for me without a population.

Without guest sessions the pointer and pointing-habit experts score against a
wide reference centred on my own model. Anyone on the same mouse lands near
that centre, so the reference says "more like the owner" for nearly every
hand. This bench measures that, and the cap on vouching that answers it:

- on my own data (the daemon's store, read with the keyring key): my
  held-out sessions (false alarms per hour, recognition), every recorded
  guest, and impostors simulated from my held-out data, for each cap;
- per signal, the mean evidence of my segments and of each guest's;
- optionally on the Balabit mouse corpus, pointer only, EER per cap, as an
  outside check that the cap is not tuned to one guest.

Only aggregates are written: no trace, no template, no timing.

    python3 -m fidus_lab.vouch_eval --data ~/.local/share/fidusachates \\
        --balabit ../.cache/corpora/balabit --out ../research/results/<dir>
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .learning import Enrolled, replay, simulate_impostor, split_sessions
from .segment import Segment

DEFAULT_CAPS: tuple[float | None, ...] = (None, 6.0, 3.0, 2.0, 1.0, 0.5, 0.0)


def _engine(enrolled: Enrolled, cap: float | None):
    eng = enrolled.engine()
    eng.pointer_expert.fallback_vouch_cap_db = cap
    eng.habit_expert.fallback_vouch_cap_db = cap
    return eng


def _runs(enrolled: Enrolled, sessions: list[list[Segment]], cap: float | None):
    return [replay(_engine(enrolled, cap), s) for s in sessions]


def cap_row(enrolled: Enrolled, held: list[list[Segment]],
            guests: list[list[list[Segment]]], sims: list[list[Segment]],
            cap: float | None) -> dict:
    mine = _runs(enrolled, held, cap)
    seconds = sum(r.seconds for r in mine)
    rec = [r.recognised_after_s for r in mine if r.recognised_after_s is not None]
    row = {
        "cap_db": cap,
        "owner_false_alarms_per_hour": sum(r.alarms for r in mine) / (seconds / 3600)
        if seconds else None,
        "owner_recognised_share": len(rec) / len(mine) if mine else None,
        "owner_median_time_to_recognise_s": statistics.median(rec) if rec else None,
        "guests": [],
    }
    for g in guests:
        runs = _runs(enrolled, g, cap)
        det = [r.first_alarm_after_s for r in runs if r.first_alarm_after_s is not None]
        row["guests"].append({
            "sessions": len(runs),
            "sessions_alarmed": len(det),
            "alarms": sum(r.alarms for r in runs),
            "first_alarm_s": min(det) if det else None,
        })
    sim = _runs(enrolled, sims, cap)
    row["simulated_detected_share"] = (
        sum(r.first_alarm_after_s is not None for r in sim) / len(sim) if sim else None)
    return row


def per_signal(enrolled: Enrolled, segments: list[Segment], cap: float | None) -> dict:
    eng = _engine(enrolled, cap)
    acc: dict[str, list[float]] = defaultdict(list)
    for seg in segments:
        for k, v in eng.step(seg).contributions.items():
            if k.startswith("B"):
                acc[k].append(v)
    return {k: {"mean_db": statistics.fmean(v), "segments": len(v)}
            for k, v in sorted(acc.items())}


def run_own(data: Path, caps=DEFAULT_CAPS, holdout_share: float = 0.25) -> dict:
    from . import vault
    from .storage import Store

    key = vault.keyring_key()
    if key is not None:
        vault.configure(vault.Vault(key))
    store = Store(data)
    owner, _ = store.load_owner()
    guests_raw = store.load_guest_sessions()
    cut = int(len(owner) * (1 - holdout_share))
    enrolled = Enrolled.fit(owner[:cut])
    held_segs = owner[cut:]
    held = split_sessions(held_segs)
    guests = [split_sessions(g) for g in guests_raw]
    sims = [simulate_impostor(s, seed=i) for i, s in enumerate(held)]
    out = {
        "owner_segments_enrolled": cut,
        "owner_sessions_held_out": len(held),
        "guests": [{"segments": len(g), "sessions": len(s)}
                   for g, s in zip(guests_raw, guests, strict=True)],
        "caps": [cap_row(enrolled, held, guests, sims, c) for c in caps],
        "per_signal_uncapped": {
            "owner": per_signal(enrolled, held_segs, None),
            "guests": [per_signal(enrolled, g, None) for g in guests_raw],
        },
    }
    return out


def run_balabit(root: str, caps=DEFAULT_CAPS) -> dict:
    from . import public_eval

    original = public_eval.IdentityEngine
    out = {}
    try:
        for c in caps:
            def engine(*a, _cap=c, **kw):
                eng = original(*a, **kw)
                eng.pointer_expert.fallback_vouch_cap_db = _cap
                return eng
            public_eval.IdentityEngine = engine
            r = public_eval.run_balabit(root)
            out[str(c)] = {lv: s["mean"] for lv, s in r["eer"].items()}
    finally:
        public_eval.IdentityEngine = original
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.vouch_eval")
    ap.add_argument("--data", help="the daemon's data directory")
    ap.add_argument("--balabit", help="Mouse-Dynamics-Challenge directory")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    res: dict = {}
    if args.data:
        res["own"] = run_own(Path(args.data).expanduser())
    if args.balabit:
        res["balabit_eer"] = run_balabit(args.balabit)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
