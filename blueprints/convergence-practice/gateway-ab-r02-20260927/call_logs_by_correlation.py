#!/usr/bin/env python3
"""Effort and status OmniRoute recorded for given correlation ids, from call_logs (read-only), as a settled snapshot.

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
  primary key (open-sse/handlers/chatCore/attemptLogging.ts:549-557, 611).

No attempt order. The gateway starts each attempt's save without awaiting it (attemptLogging.ts:557-618), stamps
the row's timestamp after awaited lookups (src/lib/usage/callLogs.ts:538, 597, 602, 680) and inserts it only after
an awaited artifact write (:759, 824). So neither timestamp nor insertion order shows which attempt came last, and
this script reports an id's rows without numbering them or marking one as final; the query orders them only to
make the output stable. analyze_r02.py takes each call's terminal row from the client's own outcome.

Settled snapshot. The gateway drains pending saves with waitForCallLogSaves (callLogs.ts:878-896), in-process and,
outside its tests, only from graceful shutdown (closeCallLogSaves, :898-910, with a 2 s default budget, called
from src/lib/gracefulShutdown.ts:114, 129); its own tests wait up to 10 s (tests/unit/call-log-save-drain.test.ts:
39). A reader of the shared running gateway cannot call it, so this script reads the rows, waits
--settle-seconds (default 30, fifteen times the shutdown budget) and reads again until two consecutive reads are
equal, for at most --max-wait-seconds (default 600). Run it after both runs have finished. A save whose error the
gateway swallows (attemptLogging.ts:618) never lands, and no snapshot can show it. The output records the reads,
whether they settled, the interval and the bound; analyze_r02.py treats an unsettled snapshot or an interval
under 30 s as an integrity problem. The exit code is 3 when the reads did not settle.

Selects only correlation_id, timestamp, status, model, reasoning_effort_requested and reasoning_effort_upstream:
no account, connection, token or path column. The database is opened with SQLite's mode=ro URI parameter.

Usage: call_logs_by_correlation.py <db_path> <ids_json> [--rows] [--settle-seconds S] [--max-wait-seconds S]
<ids_json> maps an arm label to its correlation ids, as `analyze_r02.py ids` writes it. The JSON output has the
snapshot record and, per arm, the id, matched-id and row counts, rows per id, the ids with more than one row,
counts by (status, model, requested, upstream) over all rows, and the unmatched ids; --rows adds every matched
row, which analyze_r02.py needs. Correlation ids are private run data: keep the output out of the repository.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys
import time

COLUMNS = ("correlation_id", "timestamp", "status", "model", "reasoning_effort_requested",
           "reasoning_effort_upstream")
# Every selected column orders the rows, so equal reads compare equal; the order is not an attempt order.
QUERY = ("SELECT correlation_id, timestamp, status, model, reasoning_effort_requested, reasoning_effort_upstream "
         "FROM call_logs WHERE correlation_id IN ({}) ORDER BY correlation_id, timestamp, status, model, "
         "reasoning_effort_requested, reasoning_effort_upstream")
BATCH = 500
SETTLE_SECONDS = 30
MAX_WAIT_SECONDS = 600
EXIT_UNSETTLED = 3


def lookup(db_path, ids):
    """Rows for the given ids, as dicts of COLUMNS, in the query's order."""
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


def settled_lookup(db_path, ids, interval=SETTLE_SECONDS, max_wait=MAX_WAIT_SECONDS, sleep=time.sleep,
                   clock=time.monotonic):
    """lookup() repeated every `interval` seconds until two consecutive reads are equal or the next read would
    pass `max_wait` seconds; returns the last read and the snapshot record."""
    deadline = clock() + max_wait
    rows, reads = lookup(db_path, ids), 1
    settled = False
    while not settled and clock() + interval <= deadline:
        sleep(interval)
        again, reads = lookup(db_path, ids), reads + 1
        settled, rows = again == rows, again
    return rows, {"reads": reads, "settled": settled, "interval_seconds": interval, "max_wait_seconds": max_wait}


def row_counts(rows):
    return [{"status": status, "model": model, "requested": requested, "upstream": upstream, "count": count}
            for (status, model, requested, upstream), count in sorted(
                Counter((row["status"], row["model"], row["reasoning_effort_requested"],
                         row["reasoning_effort_upstream"]) for row in rows).items(),
                key=lambda item: tuple("" if value is None else str(value) for value in item[0]))]


def summarize(arms, rows, include_rows=False):
    by_id = {}
    for row in rows:
        by_id.setdefault(row["correlation_id"], []).append(row)
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
            "ids_with_several_rows": [identifier for identifier in unique if len(by_id.get(identifier, [])) > 1],
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
    parser.add_argument("--settle-seconds", type=float, default=SETTLE_SECONDS)
    parser.add_argument("--max-wait-seconds", type=float, default=MAX_WAIT_SECONDS)
    args = parser.parse_args(argv)
    arms = json.loads(Path(args.ids_json).read_text())
    if not isinstance(arms, dict) or not all(isinstance(ids, list) and all(isinstance(value, str) for value in ids)
                                             for ids in arms.values()):
        raise SystemExit("ids_json must map an arm label to a list of correlation id strings")
    rows, snapshot = settled_lookup(args.db_path, [identifier for ids in arms.values() for identifier in ids],
                                    args.settle_seconds, args.max_wait_seconds)
    print(json.dumps({"snapshot": snapshot, "arms": summarize(arms, rows, args.rows)}, indent=2))
    return 0 if snapshot["settled"] else EXIT_UNSETTLED


if __name__ == "__main__":
    sys.exit(main())
