#!/usr/bin/env python3
"""Does the lane's top-level `--search` reach `codex exec`? Web-search cases against fake_websearch.py.

Usage: accept_codex_ws.py <codex-executable> <arm-dir> <results.json>

Same lane argv as accept_codex.py (gpt-6-astra, effort max, --output-schema, -o, --json, --ignore-user-config,
--skip-git-repo-check, -s read-only; stdin /dev/null) with the fake provider marked
supports_standalone_web_search=true, which makes Codex's web-search extension (the `web` namespace tool `run`)
available for a non-OpenAI provider. The fake model calls web.run twice (a search_query, then an open of a literal
URL) and then answers. Codex sends each call to POST <base_url>/alpha/search with settings.external_web_access:
false for web_search mode "cached" (the default) and true for "live".

  W1 `codex --search exec ...`          W2 `codex exec ...` (no flag)          W3 `codex exec -c web_search="live" ...`
Recorded per case: exit, event types, web_search item actions and whether they carry `results`, the web tool offer
in the first request, and the settings.external_web_access of every search request.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

codex, arm, results_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
here = Path(__file__).resolve().parent
PORT = 18091
schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "probe": {"type": "string"}},
          "required": ["ok", "probe"], "additionalProperties": False}
prompt = "Search the web for the probe, open the documentation page, then return the JSON object the schema requires."
provider = ["-c", 'model_provider="fakeprov"',
            "-c", 'model_providers.fakeprov.name="fake"',
            "-c", f'model_providers.fakeprov.base_url="http://127.0.0.1:{PORT}/v1"',
            "-c", 'model_providers.fakeprov.wire_api="responses"',
            "-c", "model_providers.fakeprov.request_max_retries=0",
            "-c", "model_providers.fakeprov.stream_max_retries=0",
            "-c", "model_providers.fakeprov.supports_standalone_web_search=true"]
CASES = [("W1-search-flag", True, []), ("W2-no-flag", False, []), ("W3-config-live", False, ["-c", 'web_search="live"'])]
results = {"codex": codex.replace(str(arm), "<arm>"), "cases": []}

for name, search, extra in CASES:
    case = arm / name
    case.mkdir(parents=True)
    (case / "empty").mkdir()
    (case / "codex-home").mkdir()
    (case / "schema.json").write_text(json.dumps(schema))
    requests = case / "requests.jsonl"
    server = subprocess.Popen([sys.executable, str(here / "fake_websearch.py"), str(PORT), str(requests)],
                              stdout=subprocess.DEVNULL, stderr=open(case / "server.err", "wb"), stdin=subprocess.DEVNULL)
    time.sleep(0.8)
    argv = [codex] + (["--search"] if search else []) + [
        "exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only", "-m", "gpt-6-astra",
        "-c", 'model_reasoning_effort="max"'] + provider + extra + [
        "--output-schema", str(case / "schema.json"), "-o", str(case / "last.json"), "--json", prompt]
    env = dict(os.environ, CODEX_HOME=str(case / "codex-home"))
    started = time.monotonic()
    with open(case / "events.jsonl", "wb") as out, open(case / "stderr.txt", "wb") as err:
        try:
            code = subprocess.run(argv, cwd=case / "empty", env=env, stdin=subprocess.DEVNULL, stdout=out,
                                  stderr=err, timeout=180).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    duration = round(time.monotonic() - started, 2)
    server.terminate()
    server.wait(timeout=10)
    events = []
    for line in (case / "events.jsonl").read_text(errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append({"type": "<non-json line>"})
    reqs = [json.loads(l) for l in requests.read_text().splitlines()] if requests.exists() else []
    first = next((r["body"] for r in reqs if r["path"].rstrip("/").endswith("/responses")), {}) or {}
    offered = []
    for item in first.get("input", []):
        if item.get("type") == "additional_tools":
            for tool in item.get("tools", []):
                entry = tool.get("name") or tool.get("type")
                inner = [t.get("name") for t in tool.get("tools", [])] if isinstance(tool.get("tools"), list) else []
                offered.append(f"{tool.get('type')}:{entry}" + (f"[{','.join(inner)}]" if inner else ""))
    searches = [r["body"] for r in reqs if r["path"].rstrip("/").endswith("/alpha/search")]
    web_items = [e.get("item") for e in events
                 if e.get("type") == "item.completed" and (e.get("item") or {}).get("type") == "web_search"]
    record = {
        "case": name, "argv": [a.replace(str(arm), "<arm>") for a in argv], "exit": code, "duration_s": duration,
        "event_types": [e.get("type") for e in events],
        "offered_tools_first_request": offered,
        "search_requests": len(searches),
        "search_settings_external_web_access": [((s or {}).get("settings") or {}).get("external_web_access")
                                                for s in searches],
        "search_commands": [(s or {}).get("commands") for s in searches],
        "web_search_items_completed": [{"action": (i.get("action") or {}).get("type") if isinstance(i.get("action"), dict)
                                        else i.get("action"), "query": i.get("query"),
                                        "has_results": "results" in i, "results": i.get("results")}
                                       for i in web_items],
        "turn_completed_usage": [e.get("usage") for e in events if e.get("type") == "turn.completed"],
        "last_message_file": (case / "last.json").read_text() if (case / "last.json").exists() else None,
        "stderr_tail": (case / "stderr.txt").read_text(errors="replace")[-400:].replace(str(arm), "<arm>"),
        "provider_requests": [(r["method"], r["path"]) for r in reqs],
    }
    results["cases"].append(record)
    print(json.dumps({k: record[k] for k in ("case", "exit", "offered_tools_first_request", "search_requests",
                                             "search_settings_external_web_access", "web_search_items_completed",
                                             "turn_completed_usage", "last_message_file")}), flush=True)

results_path.write_text(json.dumps(results, indent=2) + "\n")
print("DONE")
