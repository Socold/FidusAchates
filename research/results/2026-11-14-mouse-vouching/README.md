# How much the pointer may vouch for me without a population

**What this is.** A first real guest recorded a mouse-only session on my machine
and the engine never raised an alarm. This measures why (the wide fallback
reference) and what the cap on vouching added to the pointer and pointing-habit
experts does, on my own data and on Balabit. Written up in
[research/articles/2026-11-14-mouse-vouching.md](../../articles/2026-11-14-mouse-vouching.md).

## Reproducing

```
cd lab
python3 -m fidus_lab.vouch_eval --data ~/.local/share/fidusachates \
  --balabit ../.cache/corpora/balabit \
  --out ../research/results/2026-11-14-mouse-vouching
```

The own-data part needs the daemon's store and its keyring key, so it only runs
on my machine; it writes aggregates only (counts, rates, mean evidence per
signal), no trace, template or timing. The Balabit part takes about two minutes
per cap. Code in `fidus_lab.vouch_eval`, tested in `tests/test_pointer.py`.

## Protocol

Own data: my last 4000 segments, the oldest 75 % enrolled, the newest 25 %
held out and cut into replay sessions (`split_sessions`). One guest session
(14 active minutes over 38, mouse and wheel only, no key press, recorded with
consent on 2026-11-11), cut the same way into 6 replay sessions. Impostors
simulated from my held-out sessions as in the learning curve. No population
reference anywhere: this is the fallback being measured. Each cap is applied to
both the pointer expert and the B signals of the habits expert.

Balabit: the protocol of [2026-10-21-public-corpora](../2026-10-21-public-corpora/README.md),
pointer expert only, wide fallback, EER averaged over the 10 users.

## Results

Mean evidence per voting segment, no cap (negative = "the owner"):

| Signal | Me (held out) | Guest |
|---|---|---|
| B01 velocity | -50.5 | -60.2 |
| B09 pause before click | -14.1 | -12.7 |
| B10 click duration | -15.1 | -14.7 |
| B06 pointing time | -13.9 | -9.8 |
| B13 wheel interval | -24.8 | +3.3 |
| B07, B08, B15, B25 | between -3.6 and -0.1 | between -1.2 and -0.1 |

Own data, per cap:

| Cap (dB) | My false alarms / h | Me recognised | Median time to recognise | Guest sessions alarmed | First guest alarm | Simulated detected |
|---|---|---|---|---|---|---|
| none | 1.24 | 100 % | 14 s | 0 / 6 | | 15 % |
| 6 | 1.49 | 100 % | 26 s | 0 / 6 | | 20 % |
| 3 | 1.49 | 96 % | 34 s | 0 / 6 | | 24 % |
| 2 | 1.98 | 93 % | 34 s | 1 / 6 | 177 s | 24 % |
| **1 (default)** | **2.48** | **87 %** | **34 s** | **3 / 6** | **46 s** | **37 %** |
| 0.5 | 3.22 | 87 % | 35 s | 4 / 6 | 46 s | 41 % |
| 0 | 5.21 | 87 % | 35 s | 6 / 6 | 20 s | 50 % |

Balabit, pointer only, mean EER over 10 users:

| Cap (dB) | 1 segment | 3 segments | 5 segments | Session |
|---|---|---|---|---|
| none | 0.377 | 0.328 | 0.310 | 0.286 |
| 2 | 0.452 | 0.436 | 0.417 | 0.377 |
| 1 | 0.453 | 0.436 | 0.425 | 0.391 |
| 0.5 | 0.453 | 0.439 | 0.425 | 0.385 |

## Caveats

- One guest, one session, one usage. The cap was chosen on this session; nothing here
  says how a second person would fare.
- My held-out data and the guest's come from the same mouse, the same screen,
  different days. On Balabit the impostors are other people on other machines
  over RDP, which is the opposite case.
- False alarms are counted on my held-out data with the same engine and
  thresholds as the learning curve; both rows are far from the 0.2 per hour
  target, with or without the cap.
