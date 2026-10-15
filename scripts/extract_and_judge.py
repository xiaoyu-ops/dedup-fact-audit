#!/usr/bin/env python3
"""Fact extraction and method-blind support judging for duplicate families.

extract: one call per family lists atomic facts over the union of its documents.
judge:   a separate call labels every (fact, document) cell S/C/N. Documents are shown under
         letters in a fixed per-family shuffled order, with no version order or policy information.

usage: python scripts/extract_and_judge.py {extract|judge} FAMILIES.jsonl OUTDIR --model MODEL [--workers 4]
Writes one JSON per family under OUTDIR/<stage>/ and skips families already written.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dedup_audit.llm import call_model
from dedup_audit.prompts import EXTRACT_PROMPT, JUDGE_PROMPT, docs_block, letters


def fname(fam):
    return fam["family"].replace(":", "_") + ".json"


def extract(fam, outdir, model):
    vs = fam["versions"]
    data = call_model(EXTRACT_PROMPT.format(docs=docs_block(vs, letters(len(vs)))), model)
    facts = [f.strip() for f in data["facts"] if isinstance(f, str) and f.strip()]
    return {"family": fam["family"], "facts": facts, "model": model}


def judge(fam, outdir, model):
    ex = json.load(open(os.path.join(outdir, "extract", fname(fam))))
    vs = fam["versions"]
    order = list(range(len(vs)))
    random.Random(int(hashlib.sha256(fam["family"].encode()).hexdigest()[:8], 16)).shuffle(order)
    labs = letters(len(vs))
    shown = [vs[i] for i in order]
    facts = "\n".join(f"F{i + 1}: {t}" for i, t in enumerate(ex["facts"]))
    data = call_model(JUDGE_PROMPT.format(facts=facts, docs=docs_block(shown, labs)), model)
    lab2vid = {lab: shown[k]["vid"] for k, lab in enumerate(labs)}
    matrix, missing = {}, 0
    for i in range(len(ex["facts"])):
        row = data["labels"].get(f"F{i + 1}", {})
        matrix[str(i)] = {}
        for lab, vid in lab2vid.items():
            v = str(row.get(lab, "")).strip().upper()[:1]
            if v not in ("S", "C", "N"):
                v, missing = "?", missing + 1
            matrix[str(i)][str(vid)] = v
    return {"family": fam["family"], "n_facts": len(ex["facts"]), "matrix": matrix, "missing_cells": missing,
            "shown_order_vids": [v["vid"] for v in shown], "model": model}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["extract", "judge"])
    ap.add_argument("families")
    ap.add_argument("outdir")
    ap.add_argument("--model", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    fams = [json.loads(l) for l in open(a.families)]
    fams = [f for f in fams if all(len(v["text"]) >= 200 for v in f["versions"])]
    od = os.path.join(a.outdir, a.stage)
    os.makedirs(od, exist_ok=True)
    todo = [f for f in fams if not os.path.exists(os.path.join(od, fname(f)))]
    fn = extract if a.stage == "extract" else judge
    print(f"{a.stage}: {len(fams)} families, {len(todo)} to do", flush=True)
    with cf.ThreadPoolExecutor(a.workers) as pool:
        futs = {pool.submit(fn, f, a.outdir, a.model): f for f in todo}
        for fu in cf.as_completed(futs):
            f = futs[fu]
            try:
                json.dump(fu.result(), open(os.path.join(od, fname(f)), "w"), ensure_ascii=False, indent=1)
            except Exception as e:
                with open(os.path.join(a.outdir, f"{a.stage}_errors.log"), "a") as lg:
                    lg.write(f"{f['family']}\t{type(e).__name__}: {str(e)[:300]}\n")


if __name__ == "__main__":
    main()
