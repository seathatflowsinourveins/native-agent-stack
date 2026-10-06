#!/usr/bin/env python3
"""Bridge native hcom status JSON to the existing loopback Loki publisher.

Sources: aannoo/hcom v0.7.27 (2c5f343b), src/commands/list.rs:355;
grafana/loki v3.7.8, docs/sources/reference/loki-http-api.md (JSON push).
This is metadata glue, not a transcript reader or agent runner. Private registry
input may be the native census's canonical_roots and parent map; no paths leave.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.request

from progress import loki_push_url

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")
THREAD = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
CONTEXT = re.compile(r"(?:tool:[A-Za-z0-9_.:-]{1,64}|startup|resume|idle|waiting|)")


def text(value, pattern=IDENTIFIER, fallback="unknown"):
    return value if isinstance(value, str) and pattern.fullmatch(value) else fallback


def natural(value):
    return value if type(value) is int and 0 <= value <= 2**53 else None


def snapshot(native, registry=None):
    if not isinstance(native, list):
        raise ValueError("hcom list must return a JSON array")
    roots = (registry or {}).get("canonical_roots", [])
    known = {}
    for root in roots:
        identity = text(root.get("root_id"), THREAD)
        if identity != "unknown":
            known[identity] = {"identity": identity, "lane": text(root.get("lane")),
                               "name": text(root.get("name")), "client": "codex",
                               "status": "unknown", "status_context": "",
                               "status_age_seconds": None, "unread_count": None,
                               "registered_root": True}
    for row in native:
        if not isinstance(row, dict):
            continue
        identity = text(row.get("session_id"), THREAD)
        if identity == "unknown":
            continue
        previous = known.get(identity, {})
        name = text(row.get("name"))
        known[identity] = dict(previous, identity=identity, name=name,
                               lane=previous.get("lane", name),
                               client=text(row.get("tool")),
                               status=text(row.get("status")),
                               status_context=text(row.get("status_context"), CONTEXT, "omitted"),
                               status_age_seconds=natural(row.get("status_age_seconds")),
                               unread_count=natural(row.get("unread_count")),
                               registered_root=previous.get("registered_root", False))
    return sorted(known.values(), key=lambda row: (row["lane"], row["identity"]))


def payload(rows, now_ns):
    # One stream per identity; fields are selected native metadata only. The
    # timestamp belongs to this observation, not to the lane's last model turn.
    return {"streams": [
        {"stream": {"service_name": "agent-stack-lanes", "record_kind": "hcom",
                    "identity": row["identity"]},
         "values": [[str(now_ns + i), json.dumps(dict(row, observed_unix=now_ns / 1e9),
                                                   separators=(",", ":"))]]}
        for i, row in enumerate(rows)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hcom-bin", default="hcom")
    parser.add_argument("--name", default="gore")
    parser.add_argument("--registry", type=Path,
                        help="private canonical-roots JSON; absent registration is not inferred")
    parser.add_argument("--loki-url", default="http://127.0.0.1:21300/loki/api/v1/push")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    url = loki_push_url(args.loki_url)
    result = subprocess.run([args.hcom_bin, "list", "--json", "--name", args.name],
                            capture_output=True, text=True, timeout=10, check=True)
    registry = json.loads(args.registry.read_text()) if args.registry and args.registry.is_file() else None
    rows = snapshot(json.loads(result.stdout), registry)
    if args.push:
        request = urllib.request.Request(url, json.dumps(payload(rows, time.time_ns())).encode(),
                                         {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 204:
                raise ValueError("Loki did not acknowledge hcom status ingestion")
        print(json.dumps({"status": "published", "records": len(rows)}))
    else:
        print(json.dumps(rows))


if __name__ == "__main__":
    main()
