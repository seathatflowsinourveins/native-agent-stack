#!/usr/bin/env python3
"""Effort and status OmniRoute recorded for given correlation ids, from call_logs (read-only).

Based on the session's effort_window.py, which selects the same effort columns, keyed by correlation id instead
of a time window: other gateway clients call the same models in the same window. OmniRoute lines below were
first relayed by the gateway owner and then read from the pinned commit object (`git show dd6e9607e:<path>`),
2026-09-27:
- a caller X-Correlation-Id is trimmed, has CR/LF removed and is kept when 1-256 characters long
  (OmniRoute@dd6e9607e:src/app/api/v1/chat/completions/route.ts:292-298, 322;
  src/shared/utils/correlationPreserve.ts:6-12); R02's configs set it for every call;
- the request id is `correlationId || generateRequestId()` (OmniRoute@dd6e9607e:src/sse/handlers/chat.ts:436)
  and is written to call_logs.correlation_id (src/lib/usage/callLogs.ts:713, 786, 801);
- it is returned as the X-Correlation-Id response header (src/sse/handlers/chatHelpers.ts:1172-1187; for a
  slow-path stream, src/app/api/v1/chat/completions/route.ts:298, 313-314);
- the effort columns (src/lib/db/schemaColumns.ts:278-285) are filled only when the response carried encrypted
  reasoning, from the client and upstream request bodies (src/lib/usage/callLogs.ts:634-653); otherwise they
  are NULL, so a NULL is no observation of effort, never "no effort";
- the gateway writes one row per attempt under the same correlation id: each attempt's row gets a fresh
  primary key (open-sse/handlers/chatCore/attemptLogging.ts:549-557, 611), stamped with its write time
  (src/lib/usage/callLogs.ts:680, as toISOString).

Final-row rule. An id's rows are ordered by timestamp and then by SQLite rowid, the insertion order, which the
query uses only to order and never returns. The rows are numbered in that order (`attempt` 1..`attempts`), and the
last one, the last attempt written, is the call's final row (`final`). Several rows for one id are gateway
attempts, never separate calls: promptfoo sends one request per call with maxRetries 0.

Selects only correlation_id, timestamp, status, model, reasoning_effort_requested and reasoning_effort_upstream:
no account, connection, token or path column. The database is opened with SQLite's mode=ro URI parameter.

Usage: call_logs_by_correlation.py <db_path> <ids_json> [--rows]
<ids_json> maps an arm label to its correlation ids, as `analyze_r02.py ids` writes it. The JSON output has, per
arm, the id, matched-id and row counts, rows per id, the retried ids (more than one row), counts by (status,
model, requested, upstream) over the final rows and over all rows, and the unmatched ids; --rows adds every
matched row with its attempt number, attempt count and final flag. Correlation ids are private run data: keep
the output out of the repository.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

COLUMNS = ("correlation_id", "timestamp", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream")
# rowid orders an id's rows by insertion when timestamps tie; it is not selected (the final-row rule above).
QUERY = ("SELECT correlation_id, timestamp, status, model, reasoning_effort_requested, reasoning_effort_upstream "
         "FROM call_logs WHERE correlation_id IN ({}) ORDER BY correlation_id, timestamp, rowid")
BATCH = 500


def lookup(db_path, ids):
    """Rows for the given ids, as dicts of COLUMNS, each id's rows in (timestamp, rowid) order."""
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


def number_attempts(rows):
    """Each id's rows, in lookup order, numbered as attempts; the last is the call's final row."""
    by_id = {}
    for row in rows:
        by_id.setdefault(row["correlation_id"], []).append(row)
    return {identifier: [dict(row, attempt=index + 1, attempts=len(group), final=index == len(group) - 1)
                         for index, row in enumerate(group)]
            for identifier, group in by_id.items()}


def row_counts(rows):
    return [{"status": status, "model": model, "requested": requested, "upstream": upstream, "count": count}
            for (status, model, requested, upstream), count in sorted(
                Counter((row["status"], row["model"], row["reasoning_effort_requested"],
                         row["reasoning_effort_upstream"]) for row in rows).items(),
                key=lambda item: tuple("" if value is None else str(value) for value in item[0]))]


def summarize(arms, rows, include_rows=False):
    by_id = number_attempts(rows)
    report = {}
    for arm, ids in sorted(arms.items()):
        unique = sorted(set(ids))
        matched = [row for identifier in unique for row in by_id.get(identifier, [])]
        entry = {
            "ids": len(unique),
            "duplicate_ids": len(ids) - len(unique),
            "ids_matched": sum(identifier in by_id for identifier in unique),
            "rows": len(matched),
            "rows_per_id": dict(sorted(Counter(len(by_id.get(identifier, [])) for identifier in unique).items())),
            "retried_ids": [identifier for identifier in unique if len(by_id.get(identifier, [])) > 1],
            "final_rows_by_status_model_requested_upstream": row_counts([row for row in matched if row["final"]]),
            "all_rows_by_status_model_requested_upstream": row_counts(matched),
            "unmatched": [identifier for identifier in unique if identifier not in by_id],
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
