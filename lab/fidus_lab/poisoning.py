"""Anti-poisoning for template adaptation (FR-23/24, threat M10).

Continuous adaptation is a way in: a patient impostor can drift the template
towards himself. Three guards, all here:

1. Admission: only a window the engine judged clearly genuine may update.
2. Bounded rate: a per-class update moves at most `max_step` of the way, so no
   single burst can move the template far.
3. Frozen anchor: the enrolment template is kept, and cumulative drift from it
   is watched; too much drift is an alert, not a silent adjustment.
"""

from __future__ import annotations

from dataclasses import dataclass

from .divergence import template_stability
from .experts import KeystrokeTemplate
from .stats import Distribution, LogNormal, LogNormalMixture


def admits(evidence_db: float, threshold_db: float = -5.0) -> bool:
    """A window updates the template only if its evidence is clearly genuine
    (well below zero on the impostor scale)."""
    return evidence_db <= threshold_db


def _blend(old: Distribution, new: Distribution, max_step: float) -> Distribution:
    """Move `old` a bounded step towards `new`. Two mixtures blend component by
    component (components are ordered by mean, so they match), which keeps a
    bimodal model bimodal under adaptation; any other pairing blends the
    envelopes and yields a single log-normal."""
    if isinstance(old, LogNormalMixture) and isinstance(new, LogNormalMixture):
        w = tuple(o + max_step * (n - o) for o, n in zip(old.weights, new.weights, strict=True))
        tot = w[0] + w[1]
        w = (w[0] / tot, w[1] / tot)
        mus = tuple(o + max_step * (n - o) for o, n in zip(old.mus, new.mus, strict=True))
        sg = tuple(
            max(o + max_step * (n - o), LogNormalMixture.SIGMA_FLOOR)
            for o, n in zip(old.sigmas, new.sigmas, strict=True)
        )
        return LogNormalMixture(weights=w, mus=mus, sigmas=sg, n=old.n + new.n)
    mu = old.mu + max_step * (new.mu - old.mu)
    sigma = old.sigma + max_step * (new.sigma - old.sigma)
    return LogNormal(mu=mu, sigma=max(sigma, LogNormal.SIGMA_FLOOR), n=old.n + new.n)


def bounded_update(
    current: KeystrokeTemplate,
    observed: KeystrokeTemplate,
    max_step: float = 0.05,
) -> KeystrokeTemplate:
    """Move `current` a bounded step towards `observed`, per shared class. New
    classes in `observed` are added as-is; classes only in `current` are kept."""
    hold = dict(current.hold)
    for k, v in observed.hold.items():
        hold[k] = _blend(current.hold[k], v, max_step) if k in current.hold else v
    digraph = dict(current.digraph)
    for k, v in observed.digraph.items():
        digraph[k] = _blend(current.digraph[k], v, max_step) if k in current.digraph else v
    return KeystrokeTemplate(hold=hold, digraph=digraph)


@dataclass
class AnchorWatch:
    """Watches drift of the current template from the frozen enrolment anchor."""

    anchor: KeystrokeTemplate
    drift_alert_threshold: float = 0.15

    def drift(self, current: KeystrokeTemplate) -> float:
        return template_stability(self.anchor, current)

    def drifted(self, current: KeystrokeTemplate) -> bool:
        return self.drift(current) >= self.drift_alert_threshold
