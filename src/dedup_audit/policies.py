"""Deduplication policies applied within a duplicate family.

A family is a dict {"family": id, "versions": [{"vid", "created", "version", "title", "text"}, ...]}.
Document policies return the set of retained vids. Sub-document policies return output texts
(lists of version-like dicts) that are judged against the same fact inventory.
"""
import collections
import hashlib
import random
import re

THRESHOLDS = (0.9, 0.8, 0.7, 0.5, 0.3)
MERGE_SIMILARITY = 0.5  # sentence Jaccard cutoff for the sub-document merge


# ---------- text utilities ----------
def norm(t):
    return re.sub(r"\s+", " ", t.lower()).strip()


def shingles(t, k=5):
    w = re.findall(r"\w+", t.lower())
    return {" ".join(w[i:i + k]) for i in range(max(1, len(w) - k + 1))}


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def order_key(v):
    return (v.get("created") or "", v.get("version") or 0, v["vid"])


def words(v):
    return len(v["text"].split())


def exact_unique(vs):
    """Drop documents whose normalized title+body repeats an earlier one (input order)."""
    seen, out = set(), []
    for v in vs:
        k = norm(v["title"] + " " + v["text"])
        if k not in seen:
            seen.add(k)
            out.append(v)
    return out


def latest(vs):
    """Latest by timestamp; falls back to the longest document when any timestamp is missing."""
    if all(v.get("created") for v in vs):
        return max(vs, key=order_key)
    return max(vs, key=lambda v: (words(v), v["vid"]))


def longest(vs):
    return max(vs, key=lambda v: (words(v), v["vid"]))


def groups(vs, t):
    """Single-linkage components of word 5-gram Jaccard >= t within the family."""
    sh = [shingles(v["title"] + " " + v["text"]) for v in vs]
    parent = list(range(len(vs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(vs)):
        for j in range(i + 1, len(vs)):
            if jaccard(sh[i], sh[j]) >= t:
                parent[find(i)] = find(j)
    out = collections.defaultdict(list)
    for i in range(len(vs)):
        out[find(i)].append(vs[i])
    return list(out.values())


# ---------- document policies ----------
def document_policies(fam_id, vs):
    out = {"keep_all": {v["vid"] for v in vs}}
    out["exact"] = {v["vid"] for v in exact_unique(sorted(vs, key=order_key))}
    for t in THRESHOLDS:
        cl = groups(vs, t)
        out[f"minhash@{t}"] = {min(c, key=order_key)["vid"] for c in cl}
        out[f"minhash_latest@{t}"] = {max(c, key=order_key)["vid"] for c in cl}
    out["one_first"] = {min(vs, key=order_key)["vid"]}
    out["one_latest"] = {max(vs, key=order_key)["vid"]}
    out["one_longest"] = {longest(vs)["vid"]}
    rng = random.Random(int(hashlib.sha256(fam_id.encode()).hexdigest()[:8], 16))
    out["one_random"] = {rng.choice(vs)["vid"]}
    return out


# ---------- policies used at matched budgets ----------
def representative_outputs(vs, t, how):
    """Latest or Longest representative within each threshold-t group."""
    pick = latest if how == "latest" else longest
    return exact_unique([pick(g) for g in groups(vs, t)])


def subdoc_merge(vs, t):
    """Sub-doc merge: latest representative per group plus sentences from other members whose
    word 5-gram Jaccard with every sentence of the original representative is below 0.5."""
    sh = [[shingles(s) for s in sentences(v["text"])] for v in vs]
    out = []
    for g in groups(vs, t):
        rep = latest(g)
        ri = vs.index(rep)
        add = []
        for v in sorted(g, key=order_key):
            if v["vid"] == rep["vid"]:
                continue
            i = vs.index(v)
            add += [s for s, h in zip(sentences(v["text"]), sh[i])
                    if not any(jaccard(h, z) >= MERGE_SIMILARITY for z in sh[ri])]
        out.append({**rep, "text": rep["text"] + ("\n" + "\n".join(add) if add else "")})
    return exact_unique(out)


def sentence_exact(vs):
    """Remove repeated sentences, scanning exact-unique documents latest first."""
    kept, seen = [], set()
    for v in sorted(exact_unique(sorted(vs, key=order_key)), key=order_key, reverse=True):
        for s in sentences(v["text"]):
            if norm(s) not in seen:
                seen.add(norm(s))
                kept.append(s)
    return [{**latest(vs), "title": "", "text": "\n".join(kept)}]


def c4_style(vs):
    """C4-style: drop the first sentence of any three-sentence window already seen (latest first)."""
    return _window_dedup(vs, "c4")


def dolma_style(vs):
    """Dolma-style: drop newline-delimited paragraphs already seen (latest first)."""
    return _window_dedup(vs, "dolma")


def _window_dedup(vs, kind):
    ex = exact_unique(sorted(vs, key=order_key))
    seen, kept = set(), []
    for v in sorted(ex, key=order_key, reverse=True):
        if kind == "c4":
            units = sentences(v["text"])
            drop = set()
            for i in range(max(0, len(units) - 2)):
                key = norm(" ".join(units[i:i + 3]))
                if key in seen:
                    drop.add(i)
                seen.add(key)
        else:
            units = [x.strip() for x in v["text"].split("\n") if x.strip()]
            drop = set()
            for i, u in enumerate(units):
                key = norm(u)
                if key in seen:
                    drop.add(i)
                seen.add(key)
        kept.extend(u for i, u in enumerate(units) if i not in drop)
    return [{**latest(ex), "title": "", "text": "\n".join(kept)}]


def matched_budget_output(vs, method, t=None):
    if method in ("latest", "longest"):
        return representative_outputs(vs, t, method)
    if method == "D":
        return subdoc_merge(vs, t)
    if method == "sentence_exact":
        return sentence_exact(vs)
    if method == "c4_3sentence":
        return c4_style(vs)
    if method == "dolma_paragraph":
        return dolma_style(vs)
    raise ValueError(method)
