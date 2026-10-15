"""Fact-level metrics: non-outdated fact loss, outdated retention, removal rate, family bootstrap."""
import collections
import numpy as np

FIELDS = ["words", "words_kept", "unique", "lost_unique", "outdated", "kept_outdated", "current", "lost_current"]


def family_facts(matrix, latest_vid):
    """matrix: {fact_id: {doc_id: 'S'|'C'|'N'}}. Facts without any S are dropped.
    Returns (supporting doc set, is_outdated, is_current) per fact; outdated = contradicted by the latest document."""
    out = []
    for row in matrix.values():
        sup = {str(d) for d, lab in row.items() if lab == "S"}
        if sup:
            out.append((sup, row.get(str(latest_vid)) == "C", str(latest_vid) in sup))
    return out


def family_counts(facts, retained, words_total, words_kept):
    """Counts for one family given the set of retained document ids (as strings)."""
    r = collections.Counter(words=words_total, words_kept=words_kept)
    for sup, outdated, current in facts:
        kept = bool(sup & retained)
        if outdated:
            r["outdated"] += 1
            r["kept_outdated"] += kept
        else:
            r["unique"] += 1
            r["lost_unique"] += not kept
        if current:
            r["current"] += 1
            r["lost_current"] += not kept
    return [int(r[k]) for k in FIELDS]


def bootstrap_weights(n, B=2000, seed=20261011):
    """Family bootstrap as multinomial resampling weights (B x n)."""
    return np.random.default_rng(seed).multinomial(n, np.full(n, 1 / n), size=B)


def summarize(per_family, B=2000, seed=20261011, alpha=0.05):
    """Pooled rates with pointwise family-bootstrap intervals. per_family: (n_families x 8) counts."""
    a = np.asarray(per_family, dtype=float)
    s = a.sum(0)
    bs = bootstrap_weights(len(a), B, seed) @ a
    out = {k: int(x) for k, x in zip(FIELDS, s)}
    out["families"] = len(a)
    for name, num, den, invert in [("reduction", 1, 0, True), ("loss", 3, 2, False), ("outdated_retention", 5, 4, False)]:
        with np.errstate(divide="ignore", invalid="ignore"):
            v = bs[:, num] / bs[:, den]
        pt = s[num] / s[den] if s[den] else float("nan")
        if invert:
            v, pt = 1 - v, 1 - pt
        v = v[np.isfinite(v)]
        out[name] = pt
        out[name + "_lo"], out[name + "_hi"] = np.quantile(v, [alpha / 2, 1 - alpha / 2]).tolist() if len(v) else (None, None)
    return out


def paired_difference(a, b, B=2000, seed=20261011, alpha=0.05):
    """Paired family-bootstrap interval for loss(a) - loss(b), in percentage points."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    w = bootstrap_weights(len(a), B, seed)
    la, lb = w @ a, w @ b
    d = 100 * (la[:, 3] / la[:, 2] - lb[:, 3] / lb[:, 2])
    pt = 100 * (a[:, 3].sum() / a[:, 2].sum() - b[:, 3].sum() / b[:, 2].sum())
    return pt, *np.quantile(d[np.isfinite(d)], [alpha / 2, 1 - alpha / 2]).tolist()


def representative_threshold_effects(loss):
    """R and H from MinHash-Earliest/Latest loss rates at thresholds 0.3 and 0.5 (Section 5.2)."""
    E3, E5, L3, L5 = loss["minhash@0.3"], loss["minhash@0.5"], loss["minhash_latest@0.3"], loss["minhash_latest@0.5"]
    R = ((E3 - L3) + (E5 - L5)) / 2
    H = ((E3 - E5) + (L3 - L5)) / 2
    return R, H
