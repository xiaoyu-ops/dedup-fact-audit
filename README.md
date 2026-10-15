# What Does Deduplication Delete? — Code and Data

This repository accompanies the paper *What Does Deduplication Delete? A Fact-Level Framework for Auditing
Information Loss in Web Corpora*. It contains the auditing code, fact inventories, support judgments, human
labels, question sets, and result tables. `supplementary.pdf` is the supplementary material cited in the paper
(Supplement S1–S6).

## Quick check

```bash
python scripts/reproduce_tables.py
```

This recomputes from the released labels: human agreement (inter-annotator κ = 0.92; model vs. adjudicated
human κ = 0.84) and the model-human confusion matrix; Keep-One family-level loss on AP and FineWeb; the
representative and threshold effects R and H; the raw-crawl estimates (85.4% of removed pages carry a fact their
cluster's retained page does not support; 45.3% excluding page-level facts); and matched-budget losses summed
from per-family counts. Re-deriving the matched-budget outputs themselves requires the rebuilt panel texts.

## Repository layout

```
data/
  panels/         document identifiers for each panel (no article or page text)
    ap_documents.jsonl          NewsEdits AP entry and version ids, timestamps (4,245 documents, 1,017 families)
    fineweb_documents.jsonl     FineWeb ids, URLs, crawl times (2,406 pages, 1,009 families)
    ccnews_documents.jsonl      cc_news row ids, URLs, domains, dates (1,436 articles, 500 families)
    rawcc_audit_pages.jsonl     audited removed pages and their retained representatives (WARC record ids, URLs, strata, weights)
    rawcc_warc_files.txt        the 128 CC-MAIN-2025-26 WARC files processed
  inventories/    atomic facts: FineWeb 25,432 and raw crawl 2,937 (emails and phone numbers masked);
                  AP 43,010 and CC-News 14,932 with quotation facts withheld (text set to null)
  support/        S/C/N support judgments per (family, fact, document)
  human_labels/   round 1 (250 single-annotated cells) and round 2 (240 double-annotated, adjudicated cells)
  questions/      retrieval-QA questions (AP 511, FineWeb 532, AP outdated-value 114; the paper's
                  outdated-answer analysis uses the 73 of them in matched-budget test families, in_test_split)
  results/        result tables behind the paper's figures and tables, incl. per-question QA outcomes
src/dedup_audit/  library: prompts, policies, metrics, budget controller, retrieval, corpus-level loss, QA, calibration
scripts/          rebuild panels, extract and judge, evaluate policies, raw-crawl pipeline, reproduce tables
supplementary.pdf
```

## Data formats

* `support/*.jsonl`: one line per cell, `{"family_id", "fact_id", "document_id", "label"}` with label
  `S` (stated or entailed), `C` (contradicted), or `N` (not mentioned). Raw-crawl cells use `page_id`.
  A fact is *outdated* if the latest document of its family contradicts it; loss is computed over supported,
  non-outdated facts.
* `inventories/*.jsonl`: `{"family_id", "fact_id", "fact"}`.
* `human_labels/round2_double_annotated.csv`: annotators are anonymized as A and B; `final_label` is the
  consensus or joint adjudication; `model_label` is the primary judge label; `N`/`n`/`weight` give the
  sampling-stratum design weights.
* `questions/*.jsonl`: question, short gold answer, source family and document; outdated-value questions
  also give the superseded answer.

## Notes on result files

* `results/*_document_policies.csv`: `reduction` is relative to the panel's raw word count; the paper reports
  removal relative to exact-deduplicated words, i.e. `1 - (1 - reduction) / (1 - reduction_exact)`.
* Method code `D` in matched-budget files is Sub-doc merge; `one_first` is Keep-One-Earliest;
  `minhash@t` / `minhash_latest@t` are MinHash-Earliest/Latest at threshold t.
* `panels/rawcc_audit_pages.jsonl`: `stratum_planned_sample` is the planned sample (88, 105, 112, 195; 500 pages),
  `stratum_audited` the pages completed before the budget ran out (39, 56, 27, 114), and `weight` the stratum
  population divided by the audited pages, as used for the paper's estimates.
* `results/qa_per_question.jsonl`: one row per question x policy x retriever; `correct` for independent
  questions, `answer_category` (latest / outdated / other) for outdated-value questions.
* Prompts for extraction, judging, fact types, QA answering and scoring, and question writing are in
  `src/dedup_audit/prompts.py` and `src/dedup_audit/qa.py`. The raw-crawl audit applies the extraction prompt
  to one removed page at a time.
* Model identifiers are listed in Appendix C of the paper (as exposed by the providers, September–October 2026).

## Rebuilding the panels

Article and page text is not redistributed. `scripts/build_panels.py` reconstructs the panels from the
original datasets (NewsEdits AP database, `HuggingFaceFW/fineweb` CC-MAIN-2025-26, `vblagoje/cc_news`) and
checks every document against the released identifiers. The rebuilt families are the input to
`extract_and_judge.py` and `evaluate_document_policies.py`.

## Re-running model calls

`scripts/extract_and_judge.py` uses the prompts in `src/dedup_audit/prompts.py` (verbatim from Appendix A)
through `src/dedup_audit/llm.py`, which calls the OpenAI or Anthropic API (set `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY`). The models used in each stage are listed in Appendix C of the paper. Model outputs are
not deterministic, so re-running extraction or judging gives labels close to, but not identical with, the
released ones; all reported numbers are computed from the released labels.

## Fact inventories for AP and CC-News

AP and CC-News facts are released except those typed as quotations or containing quoted or attributed speech,
which may reproduce copyrighted article text; for these, `fact` is null and `withheld` is `quotation`.
Support judgments, identifiers, and human labels cover all facts. Withheld texts are available on request for
research use.

## Licenses

Code: MIT (`LICENSE`). Our annotations: CC BY 4.0. Third-party sources keep their own terms; see `DATA_LICENSE.md`.
