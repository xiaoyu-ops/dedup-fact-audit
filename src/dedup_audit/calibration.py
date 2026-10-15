"""Sensitivity of loss estimates to support-label errors, calibrated on human-labeled cells (Supplement S2).

For each stratum (panel x text type: original document or sub-document merge output), human cells give
counts of true label y in {S, N, C} given model label x. Conditional transition probabilities are drawn
sequentially from Jeffreys posteriors: P(y=S | x) ~ Beta(n_S + .5, n_notS + .5), then
P(y=N | x, y != S) ~ Beta(n_N + .5, n_C + .5). Each draw relabels every cell once, sharing the draw across
identical normalized texts so that all policies see the same corrected labels, and is paired with a
family bootstrap of the evaluated families.
"""
import numpy as np

LABELS = "SNC"


def transition_counts(cells):
    """cells: iterable of (stratum, model_label, human_label). Returns {stratum: 3x3 counts [x][y]}."""
    out = {}
    for stratum, x, y in cells:
        m = out.setdefault(stratum, np.zeros((3, 3)))
        m[LABELS.index(x), LABELS.index(y)] += 1
    return out


def draw_transitions(counts, rng):
    """One posterior draw of P(y | x) per stratum (3x3 row-stochastic matrices)."""
    out = {}
    for stratum, m in counts.items():
        P = np.zeros((3, 3))
        for x in range(3):
            nS, nN, nC = m[x]
            pS = rng.beta(nS + .5, nN + nC + .5)
            pN = rng.beta(nN + .5, nC + .5)
            P[x] = [pS, (1 - pS) * pN, (1 - pS) * (1 - pN)]
        out[stratum] = P
    return out


def relabel(model_labels, strata, transitions, rng):
    """model_labels: array of 'S'/'N'/'C' per text unit cell; strata: aligned stratum keys."""
    u = rng.random(len(model_labels))
    out = np.empty(len(model_labels), dtype="<U1")
    for i, (x, s) in enumerate(zip(model_labels, strata)):
        cdf = np.cumsum(transitions[s][LABELS.index(x)])
        out[i] = LABELS[int(np.searchsorted(cdf, u[i]))]
    return out


def calibrated_intervals(statistic, cells, n_families, draws=2000, seed=20261014):
    """statistic(transitions, rng, family_weights) -> float for one joint draw.
    Returns the median and 2.5/97.5 percentiles over posterior-predictive draws with paired family bootstrap."""
    rng = np.random.default_rng(seed)
    counts = transition_counts(cells)
    vals = []
    for _ in range(draws):
        w = rng.multinomial(n_families, np.full(n_families, 1 / n_families))
        vals.append(statistic(draw_transitions(counts, rng), rng, w))
    vals = np.asarray(vals)
    return float(np.median(vals)), *np.quantile(vals, [0.025, 0.975]).tolist()
