#!/usr/bin/env python3
"""Build the 12-row TabFQuAD slice the ColPali trial evaluated, from a pinned local snapshot.

Usage: build_slice.py <dataset snapshot dir> <output dir> <slice-expected.json>

Loads the `test` split of the local `vidore/tabfquad_test_subsampled` snapshot with the
datasets library, keeps its first 12 rows, writes them with the library's own to_parquet()
to <output dir>/test.parquet (the layout `vidore-benchmark evaluate-retriever
--dataset-name <dir>` reads), and prints a JSON summary: full-split size, per-row sha256 of
the query text and image bytes, the parquet sha256, and whether the rows match the
fingerprint of the slice the original runs used. Exit 0 only when the row content matches.

This is self-written input preparation (local integration glue). The retrieval and the
metrics come from the unchanged upstream CLI that reads the slice.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from datasets import load_dataset

SLICE_ROWS = 12


def fingerprint(parquet_path: Path) -> list[dict]:
    rows = pq.read_table(parquet_path).to_pylist()
    return [{"row": index,
             "query_sha256": hashlib.sha256(row["query"].encode("utf-8")).hexdigest(),
             "image_sha256": hashlib.sha256(row["image"]["bytes"]).hexdigest()}
            for index, row in enumerate(rows)]


def main() -> int:
    snapshot, output, expected_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    full = load_dataset(str(snapshot), split="test")
    output.mkdir(parents=True, exist_ok=True)
    target = output / "test.parquet"
    full.select(range(SLICE_ROWS)).to_parquet(str(target))
    raw = target.read_bytes()
    rows = fingerprint(target)
    full_images = {hashlib.sha256(item["bytes"]).hexdigest()
                   for item in full.data.column("image").to_pylist()}
    matches = rows == expected["row_fingerprints"]
    summary = {
        "full_split_rows": full.num_rows,
        "full_split_distinct_images": len(full_images),
        "slice_rows": len(rows),
        "slice_distinct_images": len({row["image_sha256"] for row in rows}),
        "parquet_bytes": len(raw),
        "parquet_sha256": hashlib.sha256(raw).hexdigest(),
        "parquet_byte_identical_to_original": hashlib.sha256(raw).hexdigest() == expected["parquet_sha256"],
        "row_content_matches_original_slice": matches,
        "row_fingerprints": rows,
    }
    print(json.dumps(summary, indent=2))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
