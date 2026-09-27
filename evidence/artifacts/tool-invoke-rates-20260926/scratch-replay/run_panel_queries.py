"""Run every Loki target of dashboard panels with id >= 28 as an instant query (read-only).

Usage: run_panel_queries.py <loki base url> <dashboard json> <range, e.g. 1h> [unix seconds for "time"]
Prints per target: HTTP status, result type, series count and at most 6 (labels -> value) pairs.
Label values printed are Loki label values of the bounded name fields; no log lines are fetched.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

base, dashboard, window = sys.argv[1], sys.argv[2], sys.argv[3]
at = float(sys.argv[4]) if len(sys.argv) > 4 else time.time()
model = json.load(open(dashboard))
model = model.get("dashboard", model)  # a Grafana API response wraps the model
panels = [p for p in model["panels"] if p["id"] >= 28 and p.get("targets")]
if not panels:
    print("FAIL no invoke-rate panels (id >= 28) in this dashboard")
    sys.exit(1)
failures = 0
for panel in panels:
    for target in panel["targets"]:
        expr = target["expr"].replace("$__auto", window)
        query = urllib.parse.urlencode({"query": expr, "time": f"{at:.3f}"})
        try:
            with urllib.request.urlopen(f"{base}/loki/api/v1/query?{query}", timeout=60) as response:
                status, body = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            status, body = error.code, {"error": error.read().decode(errors="replace")[:300]}
        if status != 200:
            failures += 1
            print(f"FAIL panel {panel['id']}{target['refId']} HTTP {status} {body.get('error', '')}")
            continue
        result = body["data"]["result"]
        pairs = [(r.get("metric", {}), r["value"][1]) for r in result][:6]
        print(f"ok   panel {panel['id']}{target['refId']} {body['data']['resultType']} series={len(result)} "
              + "; ".join(f"{json.dumps(m, sort_keys=True)}={float(v):.4g}" for m, v in pairs))
print(f"targets={sum(len(p['targets']) for p in panels)} failures={failures}")
sys.exit(1 if failures else 0)
