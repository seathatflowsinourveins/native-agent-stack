#!/usr/bin/env python3
"""Effort and status OmniRoute recorded for given correlation ids, from call_logs (read-only).

Based on the session's effort_window.py, which selects the same effort columns, keyed by correlation id instead
of a time window: other gateway clients call the same models in the same window. OmniRoute lines below were
first relayed by the gateway owner and then read from the pinned commit object (`git show dd6e9607e:<path>`),
2026-09-27:
- the request id is `correlationId || generateRequestId()` (OmniRoute@dd6e9607e:src/sse/handlers/chat.ts:436)
  and is written to call_logs.correlation_id (src/lib/usage/callLogs.ts:713, 786, 801);
- it is returned as the X-Correlation-Id response header (src/sse/handlers/chatHelpers.ts:1172-1186; for a
  slow-path stream, src/app/api/v1/chat/completions/route.ts:298, 313-314);
- the effort columns (src/lib/db/schemaColumns.ts:278-285) are filled only when the response carried encrypted
  reasoning, from the client and upstream request bodies (src/lib/usage/callLogs.ts:634-653); otherwise they
  are NULL, so a NULL is no observation of effort, never "no effort".

Selects only correlation_id, timestamp, status, model, reasoning_effort_requested and reasoning_effort_upstream:
no account, connection, token or path column. The database is opened with SQLite's mode=ro URI parameter.

Usage: call_logs_by_correlation.py <db_path> <ids_json> [--rows]
<ids_json> maps an arm label to its correlation ids, as `analyze_r02.py ids` writes it. The JSON output has, per
arm, the matched row count, counts by (status, model, requested, upstream), rows per id and the unmatched ids;
--rows adds every matched row. Correlation ids are private run data: keep the output out of the repository.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

COLUMNS = ("correlation_id", "timestamp", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream")
QUERY = ("SELECT correlation_id, timestamp, status, model, reasoning_effort_requested, reasoning_effort_upstream "
         "FROM call_logs WHERE correlation_id IN ({}) ORDER BY timestamp")
BATCH = 500


def lookup(db_path, ids):
    """Rows for the given ids, as dicts of COLUMNS."""
    unique = sorted(set(ids))
    connection = sqlite3.connect(Path(db_path).expanduser().resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = []
        for start in range(0, len(unique), BATCH):
            part = unique[start:start + BATCH]
            rows += connection.execute(QUERY.format(",".join("?" * len(part))), part).fetchall()
    finally:
        connection.close()
    return [dict(zip(COLUMNS, row)) for row in rows]


def summarize(arms, rows, include_rows=False):
    by_id = {}
    for row in rows:
        by_id.setdefault(row["correlation_id"], []).append(row)
    report = {}
    for arm, ids in sorted(arms.items()):
        matched = [row for identifier in ids for row in by_id.get(identifier, [])]
        entry = {
            "ids": len(ids),
            "rows": len(matched),
            "by_status_model_requested_upstream": [
                {"status": status, "model": model, "requested": requested, "upstream": upstream, "count": count}
                for (status, model, requested, upstream), count in sorted(
                    Counter((row["status"], row["model"], row["reasoning_effort_requested"],
                             row["reasoning_effort_upstream"]) for row in matched).items(),
                    key=lambda item: tuple("" if value is None else str(value) for value in item[0]))],
            "rows_per_id": dict(sorted(Counter(len(by_id.get(identifier, [])) for identifier in ids).items())),
            "unmatched": sorted(identifier for identifier in ids if identifier not in by_id),
        }
        if include_rows:
            entry["matched_rows"] = matched
        report[arm] = entry
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("db_path")
    parser.add_argument("ids_json")
    parser.add_argument("--rows", action="store_true", help="include every matched row")
    args = parser.parse_args(argv)
    arms = json.loads(Path(args.ids_json).read_text())
    if not isinstance(arms, dict) or not all(isinstance(ids, list) and all(isinstance(value, str) for value in ids)
                                             for ids in arms.values()):
        raise SystemExit("ids_json must map an arm label to a list of correlation id strings")
    rows = lookup(args.db_path, [identifier for ids in arms.values() for identifier in ids])
    print(json.dumps(summarize(arms, rows, args.rows), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
