# A remote hand on the keyboard

*4 November 2026. Numbers and code: [research/results/2026-11-04-input-paths](../results/2026-11-04-input-paths/README.md), section 3.*

There is a story that circulates about remote workers caught because they
were operating a laptop from another continent: the keystrokes arrived with
the latency of a long network path. Whatever the details of that case, the
mechanism is plausible, and it is one of the signals in my catalogue (E11,
remote session timing). So I measured what a remote-desktop hop does to the
key timing a recorder on the target machine sees.

## The model

The person types on their own machine. The remote-desktop client batches input
events into frames of 16 ms and sends one packet per frame. Each packet
crosses the network with a random delay (log-normal; LAN 2 ± 1 ms, WAN
40 ± 10 ms, far 150 ± 40 ms), packets arrive in order, and the server injects
each packet's events back to back, 0.05 ms apart. That is roughly what an X11
or `uinput` injector does. The data is CMU again: 51 people, one password,
400 times each.

## Can the recorder tell?

The cleanest tell is not the latency itself, which the recorder cannot see,
but what jitter does to it. When a packet is late, the next one cannot
overtake it, so key events that were apart at the source land within a
millisecond of each other. A person almost never produces two key
events within a millisecond.

| Path | Mean lag | Share of near-simultaneous events, EER on 1 / 5 repetitions | Hold spread, 5 repetitions | Against my own template, 1 repetition |
|---|---|---|---|---|
| LAN | 11 ms | 0.29 / 0.11 | 0.47 | 0.44 |
| WAN | 49 ms | 0.24 / 0.08 | 0.33 | 0.31 |
| Far | 162 ms | 0.035 / 0.001 | 0.014 | 0.058 |

Over a long path, a single repetition is enough: bursts give an EER of 0.035,
and five repetitions separate perfectly. Over a LAN, the hop is nearly
transparent, as it should be. The interesting middle is a good WAN: 55 keys
already give 0.08, and that is without any model of the person.

## Does the hop hide the person?

A little, and only for an observer who does not know about it. With a clean
template taken locally, a far hop drops identification from 48 % to 9 % on one
repetition, because the jitter blurs holds the way kloak does. An observer who
knows the path and averages 20 repetitions is back at 63 %. Same lesson as
kloak: network jitter is zero-mean noise on top of a stable rhythm.

## What it means for FidusAchates

E11 is worth building, with the near-simultaneous share as its first
statistic: it needs no enrolment, it is cheap, and it is strong exactly where
the threat is (a remote operator far away). Two caveats keep it honest. Under
Wayland, remote-desktop input never reaches `evdev`, so there the right
signals are the shell's (E20, phantom activity; E21, remote session active).
And a careful operator who smooths delivery would erase the bursts; I have
not measured what is left then, beyond the distance to my own template, which
moves as long as the path adds jitter.

## Limits

One ordered stream with independent packet delays is a simplification: real
stacks retransmit, coalesce motion and run their own clocks. CMU is slow,
fixed-text typing, about one event per packet; faster typing packs more
events together and makes bursts more frequent, so these figures are on the
cautious side.
