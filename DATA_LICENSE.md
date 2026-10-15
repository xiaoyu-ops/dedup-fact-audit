# Data licenses

Our annotations (support judgments, FineWeb and raw-crawl fact inventories, human labels, questions, and
result tables) are released under CC BY 4.0. They refer to third-party documents, which keep their own terms:

| Source | Terms | What we release |
|---|---|---|
| FineWeb (`HuggingFaceFW/fineweb`, CC-MAIN-2025-26) | ODC-By 1.0; also subject to the Common Crawl terms of use | FineWeb ids, URLs, crawl times; no page text |
| Raw Common Crawl (CC-MAIN-2025-26) | Common Crawl terms of use; rights of the original site owners | WARC record ids, URLs, WARC file list; no page text |
| NewsEdits AP | Built from DiffEngine data shared under CC BY-ND 4.0 | NewsEdits entry and version ids; no article text; fact inventories on request |
| CC-News (`vblagoje/cc_news`) | No license stated; article copyright stays with publishers | Row ids, URLs, domains, dates; no article text; fact inventories on request |

Questions are short and paraphrase source facts; evidence sentences quoting article text were removed.
