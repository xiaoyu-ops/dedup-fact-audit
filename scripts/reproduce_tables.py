#!/usr/bin/env python3
"""Recompute headline numbers of the paper from the released data (no model calls, no source text needed).

usage: python scripts/reproduce_tables.py [--data data]
"""
import argparse
import collections
import csv
import json
from pathlib import Path


def jsonl(p):
    return [json.loads(l) for l in open(p)]


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return po, (po - pe) / (1 - pe)


def keep_one_loss(support, documents, family_key, time_key, which):
    """Family-level non-outdated fact loss when keeping only the earliest or latest document per family."""
    docs = collections.defaultdict(list)
    for d in documents:
        docs[d["family_id"]].append(d)
    cells = collections.defaultdict(lambda: collections.defaultdict(dict))
    for c in support:
        cells[c["family_id"]][c["fact_id"]][str(c["document_id"])] = c["label"]
    unique = lost = 0
    for fam, facts in cells.items():
        ds = sorted(docs[fam], key=lambda d: (d[time_key] or "", float(d.get("version_index", 0) or 0), int(d[family_key])))
        last, first = str(ds[-1][family_key]), str(ds[0][family_key])
        keep = first if which == "earliest" else last
        for row in facts.values():
            if not any(l == "S" for l in row.values()) or row.get(last) == "C":
                continue
            unique += 1
            lost += row.get(keep) != "S"
    return lost, unique


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[1] / "data"))
    D = Path(ap.parse_args().data)

    print("== Human validation (round 2, 240 cells)")
    rows = list(csv.DictReader(open(D / "human_labels/round2_double_annotated.csv")))
    po, k = kappa([(r["label_A"], r["label_B"]) for r in rows])
    print(f"  annotator A vs B: {po:.2%} agreement, kappa={k:.4f}")
    po, k = kappa([(r["model_label"], r["final_label"]) for r in rows])
    print(f"  model vs adjudicated human: {po:.2%} agreement, kappa={k:.4f}")

    print("== Keep-One family-level loss from released support labels")
    ap_docs = jsonl(D / "panels/ap_documents.jsonl")
    ap_sup = jsonl(D / "support/ap_support.jsonl")
    for which in ("earliest", "latest"):
        l, u = keep_one_loss(ap_sup, ap_docs, "newsedits_version_id", "timestamp", which)
        print(f"  AP keep-one-{which}: {l}/{u} = {l / u:.2%}")
    fw_docs = jsonl(D / "panels/fineweb_documents.jsonl")
    fw_sup = jsonl(D / "support/fineweb_support.jsonl")
    for which in ("earliest", "latest"):
        l, u = keep_one_loss(fw_sup, fw_docs, "pool_index", "crawl_timestamp", which)
        print(f"  FineWeb keep-one-{which}: {l}/{u} = {l / u:.2%}")

    print("== Raw Common Crawl audit (stratum-weighted)")
    pages = {p["page_id"]: p for p in jsonl(D / "panels/rawcc_audit_pages.jsonl")}
    by_page = collections.defaultdict(lambda: collections.defaultdict(dict))
    for c in jsonl(D / "support/rawcc_support.jsonl"):
        by_page[c["page_id"]][c["fact_id"]][str(c["document_id"])] = c["label"]
    flags, population = collections.defaultdict(list), {}
    for pid, facts in by_page.items():
        p = pages[pid]
        rep, me = str(p["representative_id"]), str(pid)
        flags[p["stratum"]].append(any(row.get(me) == "S" and row.get(rep) != "S" for row in facts.values()))
        population[p["stratum"]] = int(p["stratum_population"])
    est = sum(population[h] * sum(v) / len(v) for h, v in flags.items()) / sum(population.values())
    print(f"  removed pages with a fact the representative does not support: {est:.1%} ({len(by_page)} pages)")
    for h in sorted(flags, key=lambda h: int(h.rstrip("+").split("-")[0])):
        print(f"    stratum {h:5s}: {len(flags[h])} audited of {population[h]} removed")

    print("== Matched budgets, 20% removal (from results/matched_budget.csv)")
    for r in csv.DictReader(open(D / "results/matched_budget.csv")):
        if r["budget"] == "0.2":
            print(f"  {r['panel']:3s} {r['method']:16s} lost {r['lost_unique']}/{r['unique']} = {float(r['loss']):.2%}")


if __name__ == "__main__":
    main()
