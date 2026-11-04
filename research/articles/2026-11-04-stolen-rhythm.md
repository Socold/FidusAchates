# What my typing rhythm is worth to a thief

*4 November 2026. Numbers and code: [research/results/2026-11-04-mimicry](../results/2026-11-04-mimicry/README.md).*

The two previous articles looked at hiding: can someone stop an observer from
recognising how they type. This one turns it around. FidusAchates recognises
me by my rhythm, so the rhythm is a credential. What happens when someone
else gets hold of it? A discussion of keystroke de-anonymisation touched on
this almost in passing (a generative model, or a small mechanical rig, that
reproduces someone else's signature); for a tool like mine it is the central
attack.

## Setup

On the CMU benchmark (51 people, one password, 400 repetitions each), each
person in turn is the victim. The verifier, either the classic scaled
Manhattan detector or my engine's keystroke expert, is trained on the
victim's first 200 repetitions, and its threshold is set where it makes as
many false accepts as false rejects against ordinary impostors. Then forgers
try 200 times each:

- **Zero effort**: other people simply typing, the usual impostor.
- **Stolen template**: the forger has the stored model and draws each
  attempt from it.
- **Observed**: the forger never saw the model, but recorded n of the
  victim's repetitions, which is what any web page measuring keystrokes can
  do, and builds its own model from them. Once with the victim typing
  normally, once with the victim behind kloak.

## Results

| Forger | Scaled Manhattan | My keystroke expert |
|---|---|---|
| Zero effort | 10 % | 13 % |
| Stolen template | 96 % | 89 % |
| 5 repetitions observed (55 keys) | 91 % | 79 % |
| 50 repetitions observed | 94 % | 79 % |
| 50 observed through kloak, forger unaware of kloak | 16 % | 2 % |
| 5 observed through kloak, forger aware of kloak | 52 % | 29 % |
| 50 observed through kloak, forger aware of kloak | 78 % | 56 % |

(Share of forged attempts accepted.)

Two lines matter.

**A stolen template is a stolen credential.** 89 to 96 % of forged attempts
pass, against 10 to 13 % for an ordinary impostor. The forgeries are not
crude: my attribution channel labels none of them automation, because they
carry a human amount of variation. The design already says templates live
in an encrypted database with the key in the system keyring (05-PRIVACY), and
asks for irreversibility in the spirit of ISO/IEC 24745 (PR-10). The research
daemon I run today does neither: `model.json` holds the means and spreads in
plain JSON, mode 0600, and anything running as my user can copy it and forge
me.

**But stealing the template is not even necessary.** Fifty-five keystrokes
recorded by a page are enough to build a forgery that passes 79 % of the time
against my expert. More observations barely help, because five repetitions
already pin the means down. A behavioural template is not a secret in the way
a password is: I leave copies of it on every site that times my keys.

## Does kloak help against forgers?

Against a naive one, completely: the spread seen through kloak is inflated,
so attempts drawn from it are far too noisy, and almost none pass (2 % against
my expert). But that is the forger's mistake, not kloak's strength. kloak
leaves the means in place, and its variance is known (D^2 / 6 on each hold and
gap), so a forger who knows kloak was there simply removes it. With 50
repetitions observed through kloak, that forger passes 78 % of the time
against scaled Manhattan and 56 % against my expert. kloak costs the forger
more observations; it does not stop them.

## What it means for FidusAchates

- **Timing alone cannot be the whole defence.** A forger still has to emit
  the timings: through a virtual input device, which the recorder marks as
  such (E01), through a microcontroller posing as a keyboard (E19 when it is
  plugged in while I work), or through a device between my keyboard and the
  machine, which is the hard case. The provenance signals carry real weight
  here, and the behavioural score must never be read alone.
- **The template needs protecting at rest.** At the least, readable only by
  the daemon and kept out of backups that leave the machine; better, stored
  in a form that verifies without revealing the means (the PR-10 work, which
  now has a measured reason to exist).
- **Consistency over time is the next test.** These forgeries are scored one
  repetition at a time. A forger has to keep the right variance and the
  right correlations between keys over a whole session; whether my engine can
  catch a forgery that is right on average but wrong in its texture is the
  experiment to run next.

## Limits

CMU is one fixed password, which makes forging easy: every attempt is the same
eleven keys, and five repetitions are a near-complete sample. In free text a
forger needs coverage of many key pairs, which my expert pools into classes,
and that pooling helps the forger. The forger here emits perfect timings; a
physical rig adds its own noise, which may help or hurt it.
