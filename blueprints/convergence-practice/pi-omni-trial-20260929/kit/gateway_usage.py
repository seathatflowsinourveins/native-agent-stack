#!/usr/bin/env python3
"""Sum gateway-side usage for run ids from OmniRoute call logs (numeric fields only).

    gateway_usage.py RUN_ID [RUN_ID ...] [--entry URL] [--upstream URL] [--limit N]

The entry gateway (20129) logs the client's request; the upstream gateway (20128) logs the provider call. Rows join
on sessionTag (/v1/responses, sent as X-OmniRoute-Session-Id) or correlationId. Per run and per gateway it prints the
request count by HTTP status (failed attempts included), summed tokens.in/out/cacheRead/cacheWrite/reasoning/
compressed, and summed duration. It never prints or keeps the account, connection, key or model-content fields that
call logs carry. A run with no matching row reports zero requests: unknown, not zero usage.
"""
import argparse
import json
import sys
import urllib.request

FIELDS = ["in", "out", "cacheRead", "cacheWrite", "reasoning", "compressed"]


def fetch(base, limit):
    with urllib.request.urlopen(f"{base}/api/usage/call-logs?limit={limit}", timeout=20) as response:
        data = json.loads(response.read())
    return data if isinstance(data, list) else data.get("logs", [])


def totals(rows, run_id):
    out = {"requests": 0, "status": {}, "duration_ms": 0, **{k: 0 for k in FIELDS}, "null_token_rows": 0, "rows": []}
    for row in sorted(rows, key=lambda r: r.get("timestamp") or ""):
        if run_id not in (row.get("sessionTag"), row.get("correlationId")):
            continue
        out["requests"] += 1
        status = str(row.get("status"))
        out["status"][status] = out["status"].get(status, 0) + 1
        out["duration_ms"] += int(row.get("duration") or 0)
        tokens = row.get("tokens") or {}
        if len(out["rows"]) < 200:
            out["rows"].append({"t": str(row.get("timestamp"))[11:23], "status": row.get("status"), "ms": int(row.get("duration") or 0),
                                **{k: (tokens.get(k) if isinstance(tokens.get(k), int) else None) for k in FIELDS}})
        if all(tokens.get(k) is None for k in FIELDS):
            out["null_token_rows"] += 1
        for key in FIELDS:
            out[key] += int(tokens.get(key) or 0)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_ids", nargs="+")
    parser.add_argument("--entry", default="http://127.0.0.1:20129")
    parser.add_argument("--upstream", default="http://127.0.0.1:20128")
    parser.add_argument("--limit", type=int, default=2000)
    a = parser.parse_args()
    logs = {}
    for name, base in (("entry", a.entry), ("upstream", a.upstream)):
        try:
            logs[name] = fetch(base, a.limit)
        except Exception as error:
            logs[name] = None
            print(f"# {name} {base}: {error!r}", file=sys.stderr)
    result = {run_id: {name: (totals(rows, run_id) if rows is not None else None) for name, rows in logs.items()}
              for run_id in a.run_ids}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
