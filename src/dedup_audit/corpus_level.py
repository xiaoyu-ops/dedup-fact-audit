"""Corpus-level loss: is a fact lost within its family still supported elsewhere in the retained corpus?

Candidates come from a SQLite FTS5 index (BM25 ranking, body only) over the retained corpus, excluding the
fact's own family; each candidate is judged with the same S/C/N prompt (one fact, at most 20 documents)."""
import re
import sqlite3
import numpy as np

from .prompts import JUDGE_PROMPT, docs_block, letters


def build_index(path, docs):
    """docs: iterable of {"title", "text", "source", "group", "family"}."""
    db = sqlite3.connect(path)
    db.execute("CREATE VIRTUAL TABLE docs USING fts5(text, title UNINDEXED, source UNINDEXED, grp UNINDEXED, "
               "family UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
    db.executemany("INSERT INTO docs(text,title,source,grp,family) VALUES (?,?,?,?,?)",
                   ((d["text"], d["title"], d["source"], d["group"], d["family"]) for d in docs))
    db.commit()
    return db


def search(db, text, k=20, exclude=()):
    """Top-k BM25 candidates for a fact, skipping excluded groups (the fact's own family)."""
    toks = sorted(set(re.findall(r"\w+", text.lower())))
    query = " OR ".join('"' + x.replace('"', '""') + '"' for x in toks)
    if not query:
        return []
    blocked, limit = set(exclude), max(40, k)
    while True:
        rs = db.execute("SELECT rowid,rank,grp FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?", (query, limit)).fetchall()
        selected = [(i, rank) for i, rank, g in rs if g not in blocked]
        if len(selected) >= k or len(rs) < limit:
            break
        limit *= 2
    out = []
    for i, rank in selected[:k]:
        body, title, source, g, fam = db.execute("SELECT text,title,source,grp,family FROM docs WHERE rowid=?", (i,)).fetchone()
        out.append(dict(rowid=i, score=-rank, title=title, text=body, source=source, group=g, family=fam))
    return out


def support_prompt(fact, candidates):
    labs = letters(len(candidates))
    return JUDGE_PROMPT.format(facts="F1: " + fact, docs=docs_block(candidates, labs)), labs


def corpus_loss(unique, family_lost, audited_weight, rescued_weight):
    """L_corp = L_fam * (1 - q), with q the design-weighted share of audited lost facts found supported elsewhere."""
    u, l, m, r = map(lambda x: np.asarray(x, float), (unique, family_lost, audited_weight, rescued_weight))
    with np.errstate(divide="ignore", invalid="ignore"):
        q = r / m
        rate = (l / u) * (1 - q)
    return np.where((l == 0) & (u > 0), 0.0, rate), q
