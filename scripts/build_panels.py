#!/usr/bin/env python3
"""Rebuild panel texts from the original datasets using the released identifiers.

We do not redistribute article or page text. This script reconstructs FAMILIES.jsonl files
({"family", "versions": [{"vid", "created", "version", "title", "text"}]}) for use with the other scripts.

  AP:      NewsEdits AP SQLite database (table entryversion), selected by version id; HTML is stripped.
  FineWeb: HuggingFaceFW/fineweb, config CC-MAIN-2025-26, selected by FineWeb id; pages of families
           sampled for this study ("fw1k:" prefix) are truncated to 6,000 characters.
  CC-News: vblagoje/cc_news, selected by row index; bodies are truncated to 6,000 characters.
Each rebuilt document is checked against the released URL or identifiers.

usage:
  python scripts/build_panels.py ap      --newsedits-db ap.db           --out ap_families.jsonl
  python scripts/build_panels.py fineweb --fineweb-dir PARQUET_DIR      --out fineweb_families.jsonl
  python scripts/build_panels.py ccnews  --ccnews-dir PARQUET_DIR       --out ccnews_families.jsonl
"""
import argparse
import collections
import glob
import html
import json
import re
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "panels"
TRUNCATE = 6000


def plain(s):
    s = re.sub(r"</(?:p|div|h[1-6])\s*>", "\n\n", s or "", flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n[ \t]+", "\n", html.unescape(s)).strip()


def jsonl(p):
    return [json.loads(l) for l in open(p)]


def write(out, fams):
    with open(out, "w") as f:
        for name, vs in fams.items():
            f.write(json.dumps({"family": name, "versions": vs}, ensure_ascii=False) + "\n")
    print(f"wrote {len(fams)} families to {out}")


def build_ap(db_path, out):
    docs = jsonl(DATA / "ap_documents.jsonl")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    fams = collections.defaultdict(list)
    for d in docs:
        row = db.execute("SELECT id, entry_id, version, created, title, summary FROM entryversion WHERE id=?",
                         (int(d["newsedits_version_id"]),)).fetchone()
        assert row and str(row[1]) == str(d["newsedits_entry_id"]), d
        fams[d["family_id"]].append(dict(vid=row[0], entry=row[1], version=row[2], created=row[3],
                                         title=row[4] or "", text=plain(row[5])))
    write(out, fams)


def parquet_rows(directory, columns):
    import pyarrow.parquet as pq
    for path in sorted(glob.glob(str(Path(directory) / "**" / "*.parquet"), recursive=True)):
        for batch in pq.ParquetFile(path).iter_batches(columns=columns):
            yield from batch.to_pylist()


def build_fineweb(directory, out):
    docs = jsonl(DATA / "fineweb_documents.jsonl")
    want = {d["fineweb_id"]: d for d in docs}
    found = {}
    for r in parquet_rows(directory, ["id", "url", "date", "text"]):
        if r["id"] in want:
            found[r["id"]] = r
    missing = set(want) - set(found)
    assert not missing, f"{len(missing)} pages not found in {directory}"
    fams = collections.defaultdict(list)
    for d in docs:
        r = found[d["fineweb_id"]]
        assert r["url"] == d["url"], d
        text = r["text"][:TRUNCATE] if d["family_id"].startswith("fw1k:") else r["text"]
        fams[d["family_id"]].append(dict(vid=int(d["pool_index"]), entry=int(d["pool_index"]), version=0,
                                         created=r["date"], title=r["url"], text=text))
    write(out, fams)


def build_ccnews(directory, out):
    docs = jsonl(DATA / "ccnews_documents.jsonl")
    want = {int(d["cc_news_row"]): d for d in docs}
    found = {}
    for i, r in enumerate(parquet_rows(directory, ["title", "text", "domain", "date", "url"])):
        if i in want:
            found[i] = r
    fams = collections.defaultdict(list)
    for row, d in sorted(want.items()):
        r = found[row]
        assert r["url"] == d["url"], d
        fams[d["family_id"]].append(dict(vid=row, entry=row, version=0, created=d["publication_date"],
                                         title=r["title"] or "", text=(r["text"] or "")[:TRUNCATE]))
    write(out, fams)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("panel", choices=["ap", "fineweb", "ccnews"])
    ap.add_argument("--newsedits-db")
    ap.add_argument("--fineweb-dir")
    ap.add_argument("--ccnews-dir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.panel == "ap":
        build_ap(a.newsedits_db, a.out)
    elif a.panel == "fineweb":
        build_fineweb(a.fineweb_dir, a.out)
    else:
        build_ccnews(a.ccnews_dir, a.out)


if __name__ == "__main__":
    main()
