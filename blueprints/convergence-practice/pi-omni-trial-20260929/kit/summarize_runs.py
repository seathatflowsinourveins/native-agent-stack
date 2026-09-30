#!/usr/bin/env python3
"""Aggregate the per-run results of the pi trial with the gateways' own rows (local integration script).

    summarize_runs.py --state DIR [--json OUT] [--entry URL] [--upstream URL]

Reads DIR/runs/*/result.json (written by run_task.py), joins each run id to the entry and upstream gateways' call logs
(numeric fields only, via gateway_usage.py) and prints, per arm: pass counts, wall time, complete gateway usage, the cache-read
share per request index (pi-reported and gateway-side) and the lane counts. Nothing is gated; failed and timed-out runs are
listed with their usage. A run with no matching gateway row shows requests 0 (unknown, not zero usage).
"""
import argparse
import collections
import json
from pathlib import Path

import gateway_usage as gu


def share(cache, uncached):
    total = (cache or 0) + (uncached or 0)
    return round(cache / total, 3) if total else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--entry", default="http://127.0.0.1:20129")
    parser.add_argument("--upstream", default="http://127.0.0.1:20128")
    parser.add_argument("--limit", type=int, default=5000)
    a = parser.parse_args()
    runs = sorted((json.loads(p.read_text()) for p in (a.state / "runs").glob("*/result.json")), key=lambda r: r["run_id"])
    logs = {}
    for name, base in (("entry", a.entry), ("upstream", a.upstream)):
        try:
            logs[name] = gu.fetch(base, a.limit)
        except Exception as error:
            logs[name] = None
            print(f"# {name}: {error!r}")
    rows, per_arm = [], collections.defaultdict(list)
    for r in runs:
        gw = {name: (gu.totals(data, r["run_id"]) if data is not None else None) for name, data in logs.items()}
        pi = r["pi_reported"]
        # A stack arm staged with x-omniroute-compression: off is the same client stack with the gateway lane off; label it apart.
        label = r["arm"] + ("-gwoff" if r["arm"] != "plain" and (r.get("arm_headers") or {}).get("x-omniroute-compression") == "off" else "")
        row = {"run_id": r["run_id"], "arm": label, "client_arm": r["arm"], "task": r["task"], "attempt": r["attempt"], "passed": r["check"]["passed"],
               "wall_s": r["wall_seconds"], "timed_out": r["timed_out"], "exit": r["exit_code"], "stop": pi["last_stop_reason"],
               "auto_retries": pi.get("auto_retries"), "first_error": (pi.get("first_error") or {}).get("code") or (pi.get("first_error") or {}).get("message"),
               "lanes": pi["lanes"], "tool_errors": pi.get("tool_errors"), "rtk_delta": r.get("rtk_tracker_delta"),
               "pi_usage": pi["usage"], "pi_cache_share": share(pi["usage"]["cacheRead"], pi["usage"]["input"] + pi["usage"]["cacheWrite"]),
               "pi_cache_by_request": [share(q["cacheRead"], q["input"] + q["cacheWrite"]) for q in pi.get("per_request", [])],
               "gateway": {n: (None if v is None else {k: v[k] for k in ("requests", "status", "in", "out", "cacheRead", "cacheWrite", "reasoning", "compressed", "duration_ms")}) for n, v in gw.items()},
               "gateway_cache_by_request": [share(q.get("cacheRead"), (q.get("in") or 0) - (q.get("cacheRead") or 0)) for q in ((gw.get("entry") or {}).get("rows") or [])],
               "arm_headers": r.get("arm_headers"), "gateway_state_before": r.get("gateway_state_before")}
        rows.append(row)
        per_arm[r["arm"]].append(row)
    summary = {}
    for arm, items in per_arm.items():
        by_index = collections.defaultdict(list)
        for it in items:
            for i, v in enumerate(it["pi_cache_by_request"], 1):
                if v is not None:
                    by_index[i].append(v)
        summary[arm] = {"runs": len(items), "passed": sum(1 for i in items if i["passed"]), "wall_s_total": round(sum(i["wall_s"] for i in items), 1),
                        "gateway_in": sum(((i["gateway"].get("entry") or {}).get("in") or 0) for i in items),
                        "gateway_cacheRead": sum(((i["gateway"].get("entry") or {}).get("cacheRead") or 0) for i in items),
                        "gateway_out": sum(((i["gateway"].get("entry") or {}).get("out") or 0) for i in items),
                        "mean_pi_cache_share_by_request_index": {str(k): round(sum(v) / len(v), 3) for k, v in sorted(by_index.items())}}
    out = {"runs": rows, "per_arm": summary}
    for arm, s in summary.items():
        print(f"{arm}: {s['passed']}/{s['runs']} passed, wall {s['wall_s_total']}s, gateway in {s['gateway_in']} cacheRead {s['gateway_cacheRead']} out {s['gateway_out']}")
        print(f"   mean pi cache share by request index: {s['mean_pi_cache_share_by_request_index']}")
    for r in rows:
        print(f"  {r['arm']:9s} {r['task']:18s} a{r['attempt']} passed={r['passed']} stop={r['stop']} retries={r['auto_retries']} entry_rows={(r['gateway'].get('entry') or {}).get('requests')} "
              f"pi_cache={r['pi_cache_share']} err={r['first_error']}")
    if a.json:
        a.json.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
