#!/usr/bin/env python3
"""Read-only owner record of the two OmniRoute gateways, printed as JSON on stdout (Gate A window start/end/freeze).

Our integration script, not an upstream tool. It writes nothing (no state dir, no file), reads no credential and no
environment: only `systemctl --user show` metadata, the two unit files (hashed), dist/BUILD_SHA, and four GET routes
(/api/settings/compression, /api/context/combos, /api/model-capability-overrides, /api/resilience).

Digest rules (sha256 hex, full length):
  compression, combos, resilience: sha256(json.dumps(body, sort_keys=True))               (same rule as snapshot_gateways.py)
  model_capability_overrides_stable: sha256(json.dumps(sorted (key, modelId, provider, target, value) tuples,
      sort_keys=True, separators=(",", ":")))   -- the route's refreshedAt timestamps are excluded because the gateway's
      own catalog reconciler rewrites them without any write. The same sorted tuples are printed under gateways.<port>.overrides.
Exit status 0 when every field was read, 1 when any field is an error marker (the JSON still prints)."""
import datetime
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

HOME = Path.home()
TOOLS = HOME / ".local/share/codex-ecosystem/tools"
UNIT_DIR = HOME / ".config/systemd/user"
GATEWAYS = {"20128": "omniroute.service", "20129": "omniroute-fw.service"}
ROUTES = {"compression": "/api/settings/compression", "combos": "/api/context/combos", "resilience": "/api/resilience"}


def get(port, route):
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}{route}", method="GET"), timeout=30) as response:
        return json.loads(response.read())


def sha_json(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def stable_overrides(body):
    rows = sorted((o["key"], o["modelId"], o["provider"], o["target"], o["value"]) for o in body["overrides"])
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), [list(row) for row in rows]


def main():
    record = {"schema": "omniroute-gateway-record/2", "taken_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "units": {}, "gateways": {}}
    failed = False
    for port, unit in GATEWAYS.items():
        show = subprocess.run(["systemctl", "--user", "show", unit, "-p", "ActiveState", "-p", "SubState", "-p", "MainPID", "-p", "NRestarts", "-p", "ExecMainStartTimestamp"],
                              capture_output=True, text=True).stdout.splitlines()
        fields = dict(line.split("=", 1) for line in show if "=" in line)
        unit_path = UNIT_DIR / unit
        dropin_dir = UNIT_DIR / (unit + ".d")
        record["units"][unit] = {
            "unit_file_sha256": hashlib.sha256(unit_path.read_bytes()).hexdigest() if unit_path.exists() else "missing",
            "dropins": sorted(p.name for p in dropin_dir.iterdir()) if dropin_dir.is_dir() else [],
            "active_state": fields.get("ActiveState"), "sub_state": fields.get("SubState"), "main_pid": fields.get("MainPID"),
            "n_restarts": fields.get("NRestarts"), "exec_main_start": fields.get("ExecMainStartTimestamp"),
        }
        args = subprocess.run(["ps", "-o", "args=", "-p", fields.get("MainPID", "0")], capture_output=True, text=True).stdout
        prefix = ""
        for part in args.split():
            if "/tools/omniroute-" in part:
                prefix = part.split("/tools/")[1].split("/")[0]
        build = TOOLS / prefix / "lib/node_modules/omniroute/dist/BUILD_SHA" if prefix else None
        gateway = {"prefix": prefix or "error-no-running-prefix", "build_sha": build.read_text().strip() if build and build.exists() else "error-no-build-sha", "routes": {}}
        for name, route in ROUTES.items():
            try:
                gateway["routes"][name] = sha_json(get(port, route))
            except Exception as error:
                gateway["routes"][name] = "error-" + type(error).__name__
        try:
            digest, rows = stable_overrides(get(port, "/api/model-capability-overrides"))
            gateway["routes"]["model_capability_overrides_stable"] = digest
            gateway["overrides_rows"] = len(rows)
            gateway["overrides"] = rows
        except Exception as error:
            gateway["routes"]["model_capability_overrides_stable"] = "error-" + type(error).__name__
        record["gateways"][port] = gateway
    for unit in record["units"].values():
        failed |= unit["unit_file_sha256"] == "missing" or unit["active_state"] != "active"
    for gateway in record["gateways"].values():
        failed |= gateway["prefix"].startswith("error") or gateway["build_sha"].startswith("error") or any(v.startswith("error") for v in gateway["routes"].values())
    print(json.dumps(record, indent=1, sort_keys=True))
    sys.exit(1 if failed else 0)


main()
