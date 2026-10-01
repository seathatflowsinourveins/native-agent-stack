#!/usr/bin/env python3
"""`codex exec` qualification arm against a loopback fake Responses provider (run inside sandbox.sh).

Usage: accept_codex.py <codex-executable> <arm-dir> <results.json>

Each case runs the landscape-sweep lane's argv (tools/sota-convergence/landscape-sweep/codex_job.py codex_argv):
  codex [--search] exec --ignore-user-config --skip-git-repo-check -s read-only -m gpt-6-astra
        -c model_reasoning_effort="max" --output-schema <schema> -o <last.json> --json "<prompt>"  (stdin /dev/null)
plus `-c model_provider=fakeprov` and the fakeprov provider pointing at fake_responses.py on 127.0.0.1:18090.
Nothing leaves the network namespace; CODEX_HOME is a fresh scratch directory per case; no credential is used.

  K1 --search, ok        K2 no --search, ok        K3 -c web_search="live" (no --search), ok
  K4 --search, limit (429 whose message says "You've hit your usage limit")
Recorded per case: exit code, event type sequence, turn.completed usage, -o file, the provider request (model,
reasoning, text.format, tool types and the web search tool spec), and whether the sweep's limit rule
(codex_job.py limit_error: stderr, `error` message, `turn.failed` error.message) fires.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

codex, arm, results_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
here = Path(__file__).resolve().parent
PORT = 18090
LIMIT_PHRASE = re.compile(r"hit your usage limit", re.IGNORECASE)
schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "probe": {"type": "string"}},
          "required": ["ok", "probe"], "additionalProperties": False}
prompt = "Return the JSON object that the output schema requires."
provider = ["-c", 'model_provider="fakeprov"',
            "-c", 'model_providers.fakeprov.name="fake"',
            "-c", f'model_providers.fakeprov.base_url="http://127.0.0.1:{PORT}/v1"',
            "-c", 'model_providers.fakeprov.wire_api="responses"',
            "-c", "model_providers.fakeprov.request_max_retries=0",
            "-c", "model_providers.fakeprov.stream_max_retries=0"]
CASES = [("K1-search-ok", True, [], "ok"), ("K2-no-search-ok", False, [], "ok"),
         ("K3-config-live-ok", False, ["-c", 'web_search="live"'], "ok"), ("K4-search-limit", True, [], "limit")]
results = {"codex": codex.replace(str(arm), "<arm>"), "cases": []}


def limit_rule(stderr: str, events: list) -> bool:
    if LIMIT_PHRASE.search(stderr):
        return True
    for event in events:
        if event.get("type") == "error":
            message = event.get("message")
        elif event.get("type") == "turn.failed" and isinstance(event.get("error"), dict):
            message = event["error"].get("message")
        else:
            continue
        if isinstance(message, str) and LIMIT_PHRASE.search(message):
            return True
    return False


def web_search_tools(tools: list) -> list:
    found = []
    for tool in tools or []:
        text = json.dumps(tool)
        if "web_search" in text or tool.get("type") == "web_search":
            found.append({k: v for k, v in tool.items() if k in ("type", "name", "external_web_access",
                                                                  "indexed_web_access", "search_content_types")})
    return found


for name, search, extra, mode in CASES:
    case = arm / name
    case.mkdir(parents=True)
    (case / "empty").mkdir()
    (case / "schema.json").write_text(json.dumps(schema))
    requests = case / "requests.jsonl"
    server = subprocess.Popen([sys.executable, str(here / "fake_responses.py"), str(PORT), mode, str(requests)],
                              stdout=subprocess.DEVNULL, stderr=open(case / "server.err", "wb"), stdin=subprocess.DEVNULL)
    time.sleep(0.8)
    argv = [codex] + (["--search"] if search else []) + [
        "exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only", "-m", "gpt-6-astra",
        "-c", 'model_reasoning_effort="max"'] + provider + extra + [
        "--output-schema", str(case / "schema.json"), "-o", str(case / "last.json"), "--json", prompt]
    env = dict(os.environ, CODEX_HOME=str(case / "codex-home"))
    (case / "codex-home").mkdir()
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
    stderr = (case / "stderr.txt").read_text(errors="replace")
    usage = [e.get("usage") for e in events if e.get("type") == "turn.completed"]
    failures = [e.get("error") for e in events if e.get("type") == "turn.failed"]
    errors = [e.get("message") for e in events if e.get("type") == "error"]
    reqs = [json.loads(l) for l in requests.read_text().splitlines()] if requests.exists() else []
    posts = [r for r in reqs if r["method"] == "POST" and r["path"].rstrip("/").endswith("/responses")]
    body = posts[0]["body"] if posts else {}
    text_format = (body.get("text") or {}).get("format") if isinstance(body, dict) else None
    record = {
        "case": name, "argv": [a.replace(str(arm), "<arm>") for a in argv], "exit": code, "duration_s": duration,
        "event_types": [e.get("type") for e in events],
        "item_types": sorted({(e.get("item") or {}).get("type") for e in events if e.get("type", "").startswith("item.")}
                             - {None}),
        "turn_completed_usage": usage, "turn_failed_errors": failures, "error_messages": errors,
        "stderr_tail": stderr[-500:].replace(str(arm), "<arm>"),
        "last_message_file": (case / "last.json").read_text() if (case / "last.json").exists() else None,
        "sweep_limit_rule_fires": limit_rule(stderr, events),
        "provider_requests": [(r["method"], r["path"]) for r in reqs],
        "request": {
            "model": body.get("model") if isinstance(body, dict) else None,
            "reasoning": body.get("reasoning") if isinstance(body, dict) else None,
            "text_format_type": (text_format or {}).get("type"),
            "text_format_schema_equal": (text_format or {}).get("schema") == schema,
            "text_format_strict": (text_format or {}).get("strict"),
            "tool_types": sorted({t.get("type", "?") + (":" + t["name"] if t.get("name") else "")
                                  for t in (body.get("tools") or [])}) if isinstance(body, dict) else None,
            "web_search_tools": web_search_tools(body.get("tools") if isinstance(body, dict) else []),
            "stream": body.get("stream") if isinstance(body, dict) else None,
        },
        "events_sha256": hashlib.sha256((case / "events.jsonl").read_bytes()).hexdigest(),
    }
    results["cases"].append(record)
    print(name, "exit", code, "events", record["event_types"], "usage", usage, "limit_rule",
          record["sweep_limit_rule_fires"], "web_search_tools", record["request"]["web_search_tools"],
          "format", record["request"]["text_format_type"], record["request"]["text_format_schema_equal"],
          "reasoning", record["request"]["reasoning"], "last", record["last_message_file"], flush=True)

results_path.write_text(json.dumps(results, indent=2) + "\n")
print("DONE")
