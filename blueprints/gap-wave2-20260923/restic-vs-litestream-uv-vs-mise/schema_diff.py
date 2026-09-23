"""Fix-round correction helper (2026-09-23) for restic-vs-litestream-uv-vs-mise.json.

The original receipt attributed the observed byte-level divergence between
the Litestream-monitored source copy and its pre-replication hash to
"SQLite incrementing header change-counter/version-valid-for fields on
WAL-mode connection open, independent of any logical write". A fix-round
review found the receipt's own fidelity check (row counts only) did not
test the actual, simpler and more consequential explanation: Litestream
adds its own tracking tables to the schema of any database it replicates.
This script settles that with a plain sqlite_master lookup, read-only, on
the exact three files the original receipt already produced.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def tables(path: str) -> list[str]:
    con = sqlite3.connect(f"file:{path}?immutable=1", uri=True)
    try:
        return [r[0] for r in con.execute(
            "select name from sqlite_master where type='table' order by name"
        )]
    finally:
        con.close()


def main() -> None:
    paths = {
        "aim_store_copy_post_litestream_run": sys.argv[1],
        "litestream_restore": sys.argv[2],
        "restic_restore": sys.argv[3],
    }
    result = {label: tables(path) for label, path in paths.items()}
    litestream_only = sorted(
        (set(result["aim_store_copy_post_litestream_run"]) | set(result["litestream_restore"]))
        - set(result["restic_restore"])
    )
    output = {
        "table_lists": result,
        "tables_present_only_in_litestream_touched_files": litestream_only,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
