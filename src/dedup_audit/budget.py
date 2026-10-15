"""Word-count-only budget controller for matched-removal comparisons (no fact or answer labels are read)."""
import hashlib
import numpy as np

SEED = 20261011
ACTIVATION_SALT = "T11:"  # fixed salt of the family-activation hash; kept for exact reproduction


def activation(family_id):
    return int(hashlib.sha256((ACTIVATION_SALT + family_id).encode()).hexdigest()[:16], 16) / 2 ** 64


def select_parameter(dev, deleted_words, base_words, target, thresholds):
    """Choose the threshold (and, below the method's minimum deletion, a fixed activated subset of families)
    whose development-set removal is closest to the target.
    deleted_words(family, t) -> words removed in that family at parameter t."""
    candidates = []
    for t in thresholds:
        r = sum(deleted_words(f, t) for f in dev) / base_words
        candidates.append(dict(t=t, activation=1.0, dev_reduction=r))
    minimum = min(candidates, key=lambda x: x["dev_reduction"])
    if minimum["dev_reduction"] > target:
        t, deleted = minimum["t"], 0
        candidates.append(dict(t=t, activation=0.0, dev_reduction=0.0))
        for f in sorted(dev, key=lambda f: activation(f["family"])):
            deleted += deleted_words(f, t)
            candidates.append(dict(t=t, activation=float(np.nextafter(activation(f["family"]), 1)),
                                   dev_reduction=deleted / base_words))
    best = min(candidates, key=lambda x: (abs(x["dev_reduction"] - target), -x["t"], -x["activation"]))
    best["attainable"] = target <= max(x["dev_reduction"] for x in candidates) + 1e-12
    return best


def allocate(families, options, budget):
    """Multiple-choice exact subset sum over test families.
    options[f] = list of (key, deleted_words); the identity (0 words) is always available.
    Families are permuted with a fixed seed; returns {family: key or 'identity'} closest to round(base*budget),
    preferring the lower total on ties and, when backtracking, the lowest per-family deletion."""
    import random
    ns = sorted(families)
    random.Random(SEED).shuffle(ns)
    base = sum(families[n] for n in ns)  # families[n] = baseline (exact-deduplicated) words
    target = round(base * budget)
    choices = []
    for n in ns:
        opts = {0: "identity"}
        for key, d in options[n]:
            if d > 0:
                opts.setdefault(d, key)
        choices.append(sorted(opts.items()))
    maximum = sum(max(d for d, _ in c) for c in choices)
    if target > maximum:
        return None
    bits, history = 1, [1]
    for c in choices:
        old, bits = bits, 0
        for d, _ in c:
            bits |= old << d
        history.append(bits)
    gap = 0
    while True:
        found = [x for x in (target - gap, target + gap) if 0 <= x <= maximum and (bits >> x) & 1]
        if found:
            chosen = min(found)
            break
        gap += 1
    remainder, assign = chosen, {}
    for i in range(len(ns) - 1, -1, -1):
        d, key = next((d, k) for d, k in choices[i] if d <= remainder and (history[i] >> (remainder - d)) & 1)
        assign[ns[i]] = key
        remainder -= d
    assert remainder == 0
    return dict(target_words=target, deleted_words=chosen, baseline_words=base, assignments=assign)
