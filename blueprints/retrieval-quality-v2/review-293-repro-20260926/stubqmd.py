#!/usr/bin/env python3
"""Stub of the qmd CLI surface run.py uses; behaviour comes from SCENARIO (a JSON file)."""
import json, os, sys, time, pathlib
SCENARIO = json.load(open(os.environ.get("STUB_SCENARIO") or pathlib.Path(__file__).with_suffix(".json")))
argv = sys.argv[1:]
log = SCENARIO.get("log")
if log:
    with open(log, "a") as fh:
        fh.write(json.dumps({"argv": argv, "cwd": os.getcwd(),
                             "env": {k: os.environ.get(k) for k in SCENARIO.get("log_env", [])}}) + "\n")
index = None
if "--index" in argv:
    i = argv.index("--index"); index = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
if argv[:1] == ["--version"]:
    print("qmd 2.8.3 (stub)"); sys.exit(0)
cmd = argv[0]
beh = SCENARIO.get(cmd, {})
if beh.get("sleep"):
    time.sleep(beh["sleep"])
if cmd == "collection":
    print("Indexed: n new"); sys.exit(0)
if cmd == "update":
    sys.exit(0)
if cmd == "status":
    print("QMD Status\n\nDocuments\n  Total:    33 files indexed\n"); sys.exit(0)
if cmd == "pull":
    root = pathlib.Path(SCENARIO["model_dir"]); root.mkdir(parents=True, exist_ok=True)
    for uri in SCENARIO["models"]:
        p = root / uri.rsplit("/", 1)[1]; p.write_bytes(b"stub-model:" + uri.encode())
        print(f"- {uri} -> {p} (1 KB, cached/checked)")
    sys.exit(0)
if cmd == "embed":
    print("Embedded 3 chunks from 33 documents in 1s"); sys.exit(0)
if cmd in ("search", "query"):
    q = argv[1]
    out = SCENARIO.get(cmd, {}).get("responses", {}).get(q)
    if out is None:
        out = SCENARIO.get(cmd, {}).get("default", "[]")
    sys.stdout.write(out if isinstance(out, str) else json.dumps(out)); sys.exit(0)
sys.exit(3)
