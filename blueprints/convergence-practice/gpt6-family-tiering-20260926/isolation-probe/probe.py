#!/usr/bin/env python3
"""Loopback probe of the tools the frozen `codex exec` command offers, with and without the isolation overrides.

Run inside a private network namespace, so no case can reach a real provider, and with no credential:

  bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --tmpfs /mnt --bind WORK WORK \
    --unshare-net --unshare-pid --unshare-ipc --die-with-parent --new-session --chdir WORK \
    env -i PATH=<node dir>:/usr/bin:/bin python3 WORK/probe.py <codex 0.157.1> WORK WORK/results.json

WORK holds copies of probe.py and fake_tool_calls.py. Every case gets a fresh CODEX_HOME, HOME, TMPDIR and working
directory under WORK/<case>, and its own fake_tool_calls.py server on 127.0.0.1 (a closed port for the unreachable
cases). The fake asks Codex to call scripted tools and then answers {"filings": []}. Recorded per case: exit, event
and item types, the response items of Codex's session record (rollout), the tools the first request offers, code
mode's nested tools as the model sees them, the tool outputs Codex returned, search requests, error messages and the
top-level entries Codex created under CODEX_HOME, HOME and the working directory (names only, never contents). Paths
are replaced by <case>.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

codex, work, results_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
FAKE = work / "fake_tool_calls.py"
# The committed argv's options before the per-call ones; the model is set per case.
COMMITTED = ["exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only"]
ISOLATION = ["-c", "agents.enabled=false", "-c", 'web_search="disabled"', "-c", "features.shell_tool=false",
             "-c", "features.unified_exec=false", "-c", "features.view_image=false", "-c", "features.goals=false",
             "-c", "features.sleep_tool=false", "-c", "features.hooks=false", "-c", "features.plugins=false",
             "-c", "features.apps=false", "-c", "features.unbounded_connection_retries=false",
             "-c", 'cli_auth_credentials_store="file"']
PROVIDER = ["-c", 'model_provider="fakeprov"', "-c", 'model_providers.fakeprov.name="fake"',
            "-c", 'model_providers.fakeprov.wire_api="responses"',
            "-c", "model_providers.fakeprov.request_max_retries=0",
            "-c", "model_providers.fakeprov.stream_max_retries=0",
            "-c", "model_providers.fakeprov.supports_standalone_web_search=true"]
SCHEMA = {"type": "object", "properties": {"filings": {"type": "array", "items": {"type": "string"}}},
          "required": ["filings"], "additionalProperties": False}
LIST_TOOLS = {"name": "exec", "input": "text(JSON.stringify(Object.keys(tools).sort()))"}
RUN_SHELL = {"name": "exec",
             "input": 'const r = await tools.exec_command({cmd: "pwd"}); text(JSON.stringify(r).slice(0, 300))'}
WEB = {"namespace": "web", "name": "run", "arguments": {"search_query": [{"q": "codex fake query"}]}}
SPAWN = {"namespace": "collaboration", "name": "spawn_agent", "arguments": {"message": "list files"}}
ASTRA, SOL, LUNA = "gpt-6-astra", "gpt-6-sol", "gpt-6-luna"
# Extra overrides per case: none (the committed command), the isolation overrides, or the multi_agent feature alone.
OVERRIDES = {"none": [], "isolation": ISOLATION, "multi_agent_feature_off": ["-c", "features.multi_agent=false"]}
# (case, model, overrides, scripted calls, provider reachable)
CASES = [
    ("committed-web", ASTRA, "none", [WEB], True),
    ("committed-code-mode", ASTRA, "none", [LIST_TOOLS, RUN_SHELL], True),
    ("multi-agent-feature-off", ASTRA, "multi_agent_feature_off", [], True),
    ("isolated-web", ASTRA, "isolation", [WEB], True),
    ("isolated-code-mode", ASTRA, "isolation", [LIST_TOOLS, RUN_SHELL], True),
    ("isolated-collaboration", ASTRA, "isolation", [SPAWN], True),
    ("isolated-plain-astra", ASTRA, "isolation", [], True),
    ("isolated-plain-sol", SOL, "isolation", [LIST_TOOLS], True),
    ("isolated-plain-luna", LUNA, "isolation", [LIST_TOOLS], True),
    ("committed-provider-unreachable", ASTRA, "none", [], False),
    ("isolated-provider-unreachable", ASTRA, "isolation", [], False),
]
TIMEOUT, UNREACHABLE_TIMEOUT = 120, 60


def top_entries(root):
    return sorted(path.name + ("/" if path.is_dir() else "") for path in root.iterdir())


def rollout_items(codex_home):
    counts = {}
    for rollout in sorted(codex_home.glob("sessions/**/rollout-*.jsonl")):
        for line in rollout.read_text(errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") == "response_item" and isinstance(entry.get("payload"), dict):
                kind = str(entry["payload"].get("type"))
                counts[kind] = counts.get(kind, 0) + 1
    return counts


results = {"schema_version": 1, "kind": "codex_exec_isolation_probe", "codex": "codex-cli 0.157.1",
           "committed_options": COMMITTED, "isolation_overrides": ISOLATION, "cases": []}
for number, (name, model, overrides, calls, reachable) in enumerate(CASES):
    case = work / name
    for sub in ("codex-home", "home", "tmp", "cwd"):
        (case / sub).mkdir(parents=True)
    (case / "schema.json").write_text(json.dumps(SCHEMA))
    (case / "calls.json").write_text(json.dumps(calls))
    requests = case / "requests.jsonl"
    port = 18100 + number
    server = None
    if reachable:  # otherwise nothing listens on the port, so every connection is refused
        server = subprocess.Popen([sys.executable, str(FAKE), str(port), str(requests), str(case / "calls.json")],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=open(case / "server.err", "wb"))
        time.sleep(0.8)
    argv = [codex, *COMMITTED, "-m", model, "-c", 'model_reasoning_effort="max"', *OVERRIDES[overrides],
            *PROVIDER, "-c", f'model_providers.fakeprov.base_url="http://127.0.0.1:{port}/v1"',
            "--output-schema", str(case / "schema.json"), "-o", str(case / "reply.json"), "--json",
            "Return the JSON object the schema requires."]
    env = {"PATH": os.environ["PATH"], "CODEX_HOME": str(case / "codex-home"), "HOME": str(case / "home"),
           "TMPDIR": str(case / "tmp")}
    started = time.monotonic()
    with open(case / "events.jsonl", "wb") as out, open(case / "stderr.txt", "wb") as err:
        try:
            code = subprocess.run(argv, cwd=case / "cwd", env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                  timeout=TIMEOUT if reachable else UNREACHABLE_TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    seconds = round(time.monotonic() - started, 2)
    if server is not None:
        server.terminate()
        server.wait(timeout=10)

    def scrub(text):
        return str(text).replace(str(case), "<case>").replace(str(work), "<work>")

    events = []
    for line in (case / "events.jsonl").read_text(errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append({"type": "<non-json line>"})
    bodies = [json.loads(line) for line in requests.read_text().splitlines()] if requests.exists() else []
    responses = [entry["body"] or {} for entry in bodies if entry["path"].rstrip("/").endswith("/responses")]
    offered = []
    for item in (responses[0] if responses else {}).get("input", []):
        if item.get("type") == "additional_tools":
            for tool in item.get("tools", []):
                inner = [t.get("name") for t in tool.get("tools", [])] if isinstance(tool.get("tools"), list) else []
                offered.append(f"{tool.get('type')}:{tool.get('name')}" + (f"[{','.join(inner)}]" if inner else ""))
    outputs = []
    for item in (responses[-1] if responses else {}).get("input", []):
        if item.get("type") in ("function_call_output", "custom_tool_call_output"):
            output = item.get("output")
            outputs.append(scrub(output if isinstance(output, str) else json.dumps(output))[:400])
    record = {
        "case": name, "model": model, "overrides": overrides, "scripted_calls": calls, "exit": code,
        "seconds": seconds, "event_types": [event.get("type") for event in events],
        "json_item_types": sorted({(event.get("item") or {}).get("type") for event in events
                                   if str(event.get("type", "")).startswith("item.")} - {None}),
        "rollout_response_items": rollout_items(case / "codex-home"),
        "offered_tools_first_request": offered, "tool_outputs_returned_to_model": outputs,
        "search_requests": sum(entry["path"].rstrip("/").endswith("/alpha/search") for entry in bodies),
        "responses_requests": len(responses),
        "error_messages": [scrub(event.get("message") or (event.get("error") or {}).get("message"))[:300]
                           for event in events if event.get("type") in ("error", "turn.failed")],
        "turn_completed_usage": [event.get("usage") for event in events if event.get("type") == "turn.completed"],
        "reply_file": (case / "reply.json").read_text() if (case / "reply.json").exists() else None,
        "created_in_codex_home": top_entries(case / "codex-home"), "created_in_home": top_entries(case / "home"),
        "created_in_cwd": top_entries(case / "cwd"),
        "daemon_package_present": (case / "codex-home/packages/app-server-daemon").exists(),
        "stderr_tail": scrub((case / "stderr.txt").read_text(errors="replace")[-400:]),
    }
    results["cases"].append(record)
    print(json.dumps({key: record[key] for key in ("case", "exit", "seconds", "json_item_types",
                                                   "rollout_response_items", "offered_tools_first_request",
                                                   "search_requests", "tool_outputs_returned_to_model",
                                                   "error_messages")}), flush=True)

results_path.write_text(json.dumps(results, indent=2) + "\n")
print("DONE")
