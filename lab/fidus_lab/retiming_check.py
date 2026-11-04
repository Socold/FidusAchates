"""Would a re-timed-input cue work on my own typing? Offline, on my traces.

`python -m fidus_lab.retiming_check [--data DIR] [--delays 0,25,50,100]`

On CMU, kloak at 100 ms shows in the spread of the holds (EER 0.047 over five
repetitions, research/results/2026-11-04-input-paths). This asks the same of
my own free text: fit my template on the first 70 % of my typed segments (in
time order), then compare, on the remaining 30 %, the spread of my holds
against the template (`experts.keystroke.hold_dispersion_ratio`, against the
closest of all my modes, per-usage ones included) with and without kloak's
schedule applied to the very same segments. It prints the distribution of the
mean ratio over 5 consecutive segments, which is what a watch would see.

Reads the daemon's store (sealed days need the keyring key, as the daemon
does); writes nothing.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from . import vault
from .experts.keystroke import _hold_times, hold_dispersion_ratio
from .kloak import obfuscate_times
from .learning import Enrolled
from .segment import Segment
from .storage import Store, default_root
from .trace import Record


def _retimed(seg: Segment, max_delay_ms: int, rng: random.Random) -> Segment:
    out, _ = obfuscate_times([r.time_us / 1000 for r in seg.records], max_delay_ms, rng)
    recs = [Record(int(t * 1000), r.device, r.virtual, r.event)
            for t, r in zip(out, seg.records, strict=True)]
    return Segment(start_us=recs[0].time_us, end_us=recs[-1].time_us, records=recs)


def rolling(xs: list[float], n: int = 5) -> list[float]:
    return [sum(xs[i - n:i]) / n for i in range(n, len(xs) + 1)]


def quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[int(q * (len(s) - 1))]


def run(root: Path, delays: list[int], seed: int = 20261104) -> dict:
    segs, _ = Store(root).load_owner(max_segments=10**6)
    typed = [s for s in segs if len(_hold_times(s)) >= 15]
    if len(typed) < 50:
        raise SystemExit(f"only {len(typed)} typed segments: not enough to say anything")
    k = int(len(typed) * 0.7)
    model = Enrolled.fit(typed[:k])
    templates = list(model.modes) + [m for ms in model.context_keystroke.values() for m in ms]
    out = {"typed_segments": len(typed), "train": k, "templates": len(templates), "delays": {}}
    for d in delays:
        rng = random.Random(seed + d)
        ratios = []
        for s in typed[k:]:
            probe = s if d == 0 else _retimed(s, d, rng)
            got = [r for r, n in (hold_dispersion_ratio(probe, t) for t in templates) if n >= 15]
            if got:
                ratios.append(min(got))
        w = rolling(ratios)
        out["delays"][f"{d}ms"] = {q: round(quantile(w, p), 3) for q, p in
                                   (("p10", 0.1), ("p50", 0.5), ("p90", 0.9), ("max", 1.0))}
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidus_lab.retiming_check")
    ap.add_argument("--data", default=str(default_root()))
    ap.add_argument("--delays", default="0,25,50,100")
    args = ap.parse_args(argv)
    key = vault.keyring_key(create=False)
    if key is not None:
        vault.configure(vault.Vault(key))
    res = run(Path(args.data), [int(x) for x in args.delays.split(",")])
    print(f"{res['typed_segments']} typed segments, template on the first {res['train']}, "
          f"{res['templates']} modes")
    for d, q in res["delays"].items():
        print(f"kloak {d:>6}: mean ratio over 5 segments  "
              + "  ".join(f"{k} {v:.2f}" for k, v in q.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
