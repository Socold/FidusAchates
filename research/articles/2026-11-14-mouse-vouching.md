# A stranger's hand that looked more like mine than mine

*14 November 2026. Numbers and code: [research/results/2026-11-14-mouse-vouching](../results/2026-11-14-mouse-vouching/README.md).*

For weeks the learning curve said the same thing: without guests, the numbers
mean little, because the engine has nobody to compare me with. On 11 November
I finally had one. A guest used my machine for about forty minutes, with
consent, in guest mode, and never touched the keyboard: mouse and wheel only,
fourteen minutes of actual activity.

The engine never raised an alarm. Worse, it was confident: the guest's segments scored
around -68 dB, firmly on my side, while my own pointer segments score around
-84 dB. On pointer speed alone the guest scored -60 dB per segment, more like me
than I am (-50 dB).

## Why

Without guest data the pointer expert has no idea what other people look like.
It compares each observation with my own model and with a "wide" reference: the
same distribution, centred on my median, three times as spread. That reference
is a straw man. Anyone moving the same mouse on the same screen produces
speeds, pauses and click durations near the middle of my distribution, and near
the middle my narrow model beats the wide one every time. So every ordinary
hand earns evidence for me. The keystroke expert has the same construction;
it was not tested here because the guest did not type.

The only pointer signal that went the other way was the wheel: the guest's scrolling cadence
(+3 dB per segment) is not mine (-25 dB for me).

## What I changed

A signal compared with the wide fallback may still accuse in full, but it may
only vouch up to a cap, per signal and per segment. With a real population
reference, nothing changes. The cap applies to the pointer expert and to the
pointing habits (B06, B07, B08, B15, B25), defaults to 1 dB, and can be turned
off.

On my data, at 1 dB, the guest now raises an alarm in 3 of 6 replay
sessions, the first after 46 seconds, and the share of simulated impostors
caught goes from 15 % to 37 %. The price is real: my own false alarms double
(1.24 to 2.48 per hour), and I am recognised in 87 % of my sessions instead of
all of them, in 34 seconds instead of 14, because the mouse can no longer
vouch for me on its own.

## And the outside check disagrees

On Balabit (10 people, mouse only), the same cap makes things worse: the
session-level EER goes from 0.29 to 0.39. There, impostors are other people on
other machines through RDP, and a genuine user's pointer really is closer to
their own model than to anyone else's. The strong vouching was carrying the
separation, and capping it throws that away.

So the two results do not contradict each other so much as describe two
different threats. When the intruder uses my own mouse, vouching from a straw
man reference is a blind spot; when the comparison is between different
machines, it is most of the signal. FidusAchates is about the first case,
someone at my desk or a remote hand driving my pointer, which is why the cap is
on by default. It is a stopgap. The real answer is the one the learning curve
has been asking for since October: a population reference built from more than
one guest, and guests who type as well as point.

## What next

- A second guest, and a session from the first one with typing.
- The same question for the keystroke fallback, which is built the same way.
- A calibrated fallback instead of a cap: a reference whose expected evidence
  for a typical other person on my hardware is zero, if such a thing can be
  estimated without other people.
