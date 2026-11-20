# Does a forgery keep my texture over a session, on CMU

**What this is.** Whether a forger who is accepted one repetition at a time can
also be told apart over a window of consecutive repetitions, from the
correlations between keys and from how the overall speed drifts. Written up in
[research/articles/2026-11-04-session-texture.md](../../articles/2026-11-04-session-texture.md).

## Reproducing

```
cd lab
python3 -m fidus_lab.session_eval \
  --cmu ../.cache/corpora/cmu/DSL-StrongPasswordData.csv \
  --out ../research/results/2026-11-04-session
```

Seeded, deterministic, under ten seconds. Code in `fidus_lab.session_eval`,
tested in `tests/test_session_texture.py`.

## Protocol

A repetition is its 21 log timings (11 holds, 10 down-down latencies; UD is
DD minus H and adds nothing). Per subject (51 victims), a Gaussian is fitted
on repetitions 0 to 199 with its full covariance, shrunk 10 % towards the
diagonal, and with the diagonal alone.

- `texture` of one repetition: log-likelihood under the full model minus under
  the diagonal model. A window's suspicion is minus its mean.
- `speed_autocorr`: lag-1 autocorrelation, over the window, of the projection
  on the first principal component of the full covariance. Not defined for
  k = 1.

Genuine windows: repetitions 300 to 399, cut into non-overlapping windows of
k = 1, 5, 10, 20, 50. Each forger produces 100 attempts per victim, cut the
same way:

| Forger | Holds |
|---|---|
| `laplace_independent` | the scaled-Manhattan template, independent Laplace noise per feature (the `mimicry_eval` forger) |
| `gauss_diagonal` | the victim's own log-normal marginals, drawn independently |
| `gauss_full` | the stolen full covariance, attempts independent of each other |
| `gauss_full_drift` | the same, attempts following an AR(1) with the victim's training speed autocorrelation |
| `observed_n` | a full-covariance model estimated from n of repetitions 200 to 299, shrinkage `min(1, max(0.1, 21 / n))` |

Each figure is the EER (`metrics.eer_exact`) of genuine against forged windows,
pooled over victims. 0.5 is chance; above 0.5 means the forgery looks more
like the training model than the victim does a session later.

## Results

| Forger | texture k=1 | k=10 | k=50 | speed autocorr k=50 |
|---|---|---|---|---|
| laplace_independent | 0.198 | 0.051 | 0.010 | 0.284 |
| gauss_diagonal | 0.222 | 0.102 | 0.039 | 0.294 |
| observed_5 | 0.333 | 0.271 | 0.216 | 0.314 |
| observed_20 | 0.323 | 0.257 | 0.186 | 0.294 |
| observed_50 | 0.375 | 0.353 | 0.353 | 0.284 |
| gauss_full | 0.481 | 0.612 | 0.657 | 0.294 |
| gauss_full_drift | 0.474 | 0.575 | 0.637 | 0.755 |

Median training speed autocorrelation: 0.52. Full figures in `metrics.json`.

## Limits

One fixed password, so the 21 dimensions are the same keys every time; in free
text the covariance would have to be pooled by digraph class like the keystroke
expert does. CMU records 50 repetitions per session, at least a day apart, so
training is sessions 1 to 4, observation 5 and 6, genuine windows 7 and 8, and
a window of 50 is one sitting. The forgers emit perfect timings.
