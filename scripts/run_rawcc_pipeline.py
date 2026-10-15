#!/usr/bin/env python3
"""FineWeb-style pipeline on raw Common Crawl WARC files with DataTrove (Section 4, Appendix E).

Inputs: the 128 WARC paths in data/panels/rawcc_warc_files.txt (CC-MAIN-2025-26; shuffled with seed 20261024),
downloaded under RAW_DIR as 00000.warc.gz ... 00127.warc.gz in that order.

usage: python scripts/run_rawcc_pipeline.py RAW_DIR WORK_DIR [--workers 8]
"""
import argparse
from pathlib import Path

from datatrove.executor.local import LocalPipelineExecutor
from datatrove.pipeline.dedup.minhash import (MinhashConfig, MinhashDedupBuckets, MinhashDedupCluster,
                                              MinhashDedupFilter, MinhashDedupSignature)
from datatrove.pipeline.extractors import Trafilatura
from datatrove.pipeline.filters import (C4QualityFilter, FineWebQualityFilter, GopherQualityFilter,
                                        GopherRepetitionFilter, LanguageFilter, URLFilter)
from datatrove.pipeline.readers import JsonlReader, WarcReader
from datatrove.pipeline.writers import JsonlWriter
from datatrove.utils.hashing import HashConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir")
    ap.add_argument("work_dir")
    ap.add_argument("--files", type=int, default=128)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    raw, work = Path(a.raw_dir), Path(a.work_dir)
    manifest = work / "paths.txt"
    work.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(f"{i:05d}.warc.gz" for i in range(a.files)) + "\n")

    # 1) extraction and filtering, following the published FineWeb recipe
    LocalPipelineExecutor(pipeline=[
        WarcReader(str(raw), paths_file=str(manifest), default_metadata={"dump": "CC-MAIN-2025-26"}),
        URLFilter(),
        Trafilatura(favour_precision=True),
        LanguageFilter(languages=["en"], language_threshold=0.65),
        GopherRepetitionFilter(),
        GopherQualityFilter(),
        C4QualityFilter(filter_no_terminal_punct=False),
        FineWebQualityFilter(),
        JsonlWriter(str(work / "processed")),
    ], tasks=a.files, workers=min(a.workers, a.files), logging_dir=str(work / "logs/processed")).run()

    # 2) MinHash deduplication with the FineWeb configuration (word 5-grams, 14 buckets x 8 hashes)
    cfg = MinhashConfig(n_grams=5, num_buckets=14, hashes_per_bucket=8, seed=1,
                        hash_config=HashConfig(hash_fc="sha1", precision=64))
    m = work / "minhash"
    stages = [
        ([JsonlReader(str(work / "processed")), MinhashDedupSignature(output_folder=str(m / "signatures"), config=cfg)], 8, "signatures"),
        ([MinhashDedupBuckets(input_folder=str(m / "signatures"), output_folder=str(m / "buckets"), config=cfg)], 14, "buckets"),
        ([MinhashDedupCluster(input_folder=str(m / "buckets"), output_folder=str(m / "remove_ids"), config=cfg,
                              save_cluster_id=True, save_cluster_size=True)], 1, "clusters"),
        ([JsonlReader(str(work / "processed")),
          MinhashDedupFilter(input_folder=str(m / "remove_ids"), load_cluster_ids=True, load_cluster_sizes=True,
                             exclusion_writer=JsonlWriter(str(m / "removed"))),
          JsonlWriter(str(m / "retained"))], 8, "filter"),
    ]
    for pipeline, tasks, name in stages:
        LocalPipelineExecutor(pipeline=pipeline, tasks=tasks, workers=min(a.workers, tasks),
                              logging_dir=str(m / "logs" / name)).run()


if __name__ == "__main__":
    main()
