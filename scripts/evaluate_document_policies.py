#!/usr/bin/env python3
"""Family-level loss, outdated retention, and removal for all document policies (Appendix B table).

usage: python scripts/evaluate_document_policies.py FAMILIES.jsonl JUDGE_DIR OUT.csv
FAMILIES.jsonl holds rebuilt families with text (see build_panels.py); JUDGE_DIR holds support judgments.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dedup_audit import metrics, policies as P


def main():
    fams = {json.loads(l)["family"]: json.loads(l) for l in open(sys.argv[1])}
    per = {}
    for fn in sorted(os.listdir(sys.argv[2])):
        j = json.load(open(os.path.join(sys.argv[2], fn)))
        f = fams.get(j["family"])
        if f is None:
            continue
        vs = f["versions"]
        facts = metrics.family_facts(j["matrix"], max(vs, key=P.order_key)["vid"])
        exact = P.exact_unique(sorted(vs, key=P.order_key))
        total = sum(P.words(v) for v in exact)  # removal is relative to exact-deduplicated words
        for name, kept in P.document_policies(f["family"], vs).items():
            kept_words = sum(P.words(v) for v in exact if v["vid"] in kept)
            per.setdefault(name, []).append(metrics.family_counts(facts, {str(k) for k in kept}, total, kept_words))
    rows = [dict(policy=name, **metrics.summarize(a)) for name, a in per.items()]
    rows.sort(key=lambda r: r["reduction"])
    with open(sys.argv[3], "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['policy']:22s} removal {r['reduction']:6.1%}  loss {r['loss']:6.2%} [{r['loss_lo']:.2%}, {r['loss_hi']:.2%}]")


if __name__ == "__main__":
    main()
