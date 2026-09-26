#!/usr/bin/env python3
"""Summarize Tavily Research (`tvly research run --model pro`) returns without their text.

  summarize.py --runs DIR --landscape FILE [--output FILE]

DIR holds one sweep run per layer as tavily_layer.sh left it: <layer>.json (the report: status,
created_at, response_time, request_id, sources, content), <layer>.stdout, <layer>.stderr and run.log
("<layer> rc=<status>" per line). FILE is a retained report whose request id is already hashed
(evidence/artifacts/alpaca-platform-landscape-20260926/tavily-research-pro.json).

The summary holds counts per status, response_time and sources-per-report min/median/max, report
sizes in characters, launcher exit statuses and one row per report. It holds no report text, no
source URL, no raw request id (each becomes uuid-sha256:<first 16 hex digits of the SHA-256 of its
UTF-8 bytes>, the length the landscape artifact uses) and no host path: every string passes through
scripts/host_receipts.py sanitize(), and the script exits 1 if a string of the result still matches
one of scripts/validate.py's PRIVATE_CONTENT patterns or contains a raw request id.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.host_receipts import PRIVATE_CONTENT, iter_receipt_strings, sanitize  # noqa: E402

UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")
REPORT_FIELDS = ["content", "created_at", "request_id", "response_time", "sources", "status"]
RUN_LOG_LINE = re.compile(r"([a-z0-9-]+) rc=(\d+)")
# tvly research run -o <path> prints only "Output saved to <path>" on stderr, wrapped at the terminal
# width; the path is not kept.
SAVED_PREFIX = "Outputsavedto"


def request_hash(request_id: str) -> str:
    return "uuid-sha256:" + hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:16]


def spread(values: list[float]) -> dict:
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def summarize(runs: Path, landscape: Path) -> tuple[dict, list[str]]:
    raw_ids, rows = [], []
    for path in sorted(runs.glob("*.json")):
        layer = path.stem
        report = json.loads(path.read_text(encoding="utf-8"))
        request_id = report["request_id"]
        raw_ids.append(request_id)
        stdout = (runs / f"{layer}.stdout").read_bytes()
        stderr = (runs / f"{layer}.stderr").read_text(encoding="utf-8", errors="replace")
        rows.append({
            "layer": sanitize(layer),
            "fields": sorted(report) == REPORT_FIELDS,
            "status": sanitize(report["status"]),
            "created_at": sanitize(report["created_at"]),
            "response_time_s": report["response_time"],
            "sources": len(report["sources"]),
            "content_chars": len(report["content"]),
            "request_id": request_hash(request_id),
            "request_id_is_uuid": bool(UUID.fullmatch(request_id)),
            "stdout_bytes": len(stdout),
            "stderr_is_output_saved_only": "".join(stderr.split()).startswith(SAVED_PREFIX)
            and "".join(stderr.split()).endswith(f"/{layer}.json"),
        })
    launcher = {}
    for line in (runs / "run.log").read_text(encoding="utf-8").splitlines():
        match = RUN_LOG_LINE.fullmatch(line.strip())
        if match:
            launcher[match.group(1)] = int(match.group(2))
    retained = json.loads(landscape.read_text(encoding="utf-8"))
    landscape_row = {
        "report": sanitize(landscape.name),
        "status": sanitize(retained["status"]),
        "model": sanitize(retained["model"]),
        "created_at": sanitize(retained["created_at"]),
        "response_time_s": retained["response_time_s"],
        "sources": len(retained["sources"]),
        "content_chars": len(retained["content"]),
        "request_id": sanitize(retained["request_id"]),  # hashed when the artifact was written
    }
    times = [row["response_time_s"] for row in rows]
    sources = [row["sources"] for row in rows]
    summary = {
        "schema_version": 1,
        "kind": "tavily_research_run_summary",
        "request_id_hash": "uuid-sha256:<first 16 hex digits of the SHA-256 of the request id's UTF-8 bytes>",
        "sweep": {
            "reports": len(rows),
            "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
            "launcher_exit_status_counts": {str(k): v for k, v in sorted(Counter(launcher.values()).items())},
            "launcher_layers_match_reports": sorted(launcher) == [row["layer"] for row in rows],
            "reports_with_expected_fields": sum(row["fields"] for row in rows),
            "request_ids_uuid_shaped": sum(row["request_id_is_uuid"] for row in rows),
            "request_ids_distinct": len(set(raw_ids)),
            "stdout_bytes_total": sum(row["stdout_bytes"] for row in rows),
            "stderr_output_saved_only": sum(row["stderr_is_output_saved_only"] for row in rows),
            "created_at_first": min(row["created_at"] for row in rows),
            "created_at_last": max(row["created_at"] for row in rows),
            "response_time_s": spread(times),
            "sources_per_report": spread(sources),
            "content_chars": spread([row["content_chars"] for row in rows]),
            "runs": [{key: row[key] for key in ("layer", "status", "created_at", "response_time_s", "sources",
                                                "content_chars", "request_id")} for row in rows],
        },
        "landscape": landscape_row,
        "all_reports": {
            "reports": len(rows) + 1,
            "status_counts": dict(sorted(Counter([*(row["status"] for row in rows),
                                                  landscape_row["status"]]).items())),
            "response_time_s": spread([*times, landscape_row["response_time_s"]]),
            "sources_per_report": spread([*sources, landscape_row["sources"]]),
        },
        "privacy": {"report_text": False, "source_urls": False, "raw_request_ids": False, "host_paths": False},
    }
    problems = []
    serialized = json.dumps(summary)
    for text in iter_receipt_strings(summary):
        for description, pattern in PRIVATE_CONTENT:
            if pattern.search(text):
                problems.append(f"a summary string matches {description}")
    problems += ["a raw request id is in the summary" for request_id in raw_ids if request_id in serialized]
    return summary, problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--landscape", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    summary, problems = summarize(args.runs, args.landscape)
    if problems:
        print("\n".join(sorted(set(problems))), file=sys.stderr)
        return 1
    text = json.dumps(summary, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
