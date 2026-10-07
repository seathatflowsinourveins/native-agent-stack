#!/usr/bin/env bash
# Native keyless CLI with private artifact integration, not an agent runner.
# bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e:
# README.md:1837-1846; backend/packages/harness/deerflow/tui/cli.py:274-285;
# backend/packages/harness/deerflow/client.py:491-538,1191-1223;
# backend/packages/harness/deerflow/community/ddg_search/tools.py:134-153,190-191.
set -euo pipefail
if (( $# != 1 )); then printf 'Usage: %s "public research query"\n' "$0" >&2; exit 2; fi
tool_root="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack"
config="${DEER_FLOW_CONFIG_PATH:-$config_root/deer-flow-config.yaml}"
run_root="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/research/deer-flow"
mkdir -p -m 0700 -- "$run_root"
run="$(mktemp -d "$run_root/run.XXXXXXXX")"
mkdir -m 0700 -- "$run/home" "$run/tmp"
cd -- "$run"
# Native ChatOpenAI default_headers join gateway metadata to this run.
# OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:open-sse/handlers/chatCore.ts:1087-1090,1133.
"$tool_root/deer-flow/backend/.venv/bin/python" - "$config" "$run/config.yaml" "deerflow-${run##*/}" <<'CONFIG'
import sys
import yaml
from pathlib import Path
source, target, session = sys.argv[1:]
config = yaml.safe_load(Path(source).read_text())
model, = [model for model in config["models"] if model["name"] == "gpt-runtime"]
model["default_headers"] = {"x-omniroute-session-id": session}
Path(target).write_text(yaml.safe_dump(config))
CONFIG
printf 'run directory: %s\n' "$run" >&2
# Empty overrides survive upstream load_dotenv(override=False). No provider
# credential is inherited or injected; the selected DDGS search is keyless.
native_rc=0
if env -i HOME="$run/home" PATH="$PATH" LANG="${LANG:-C.UTF-8}" \
  JINA_API_KEY= TAVILY_API_KEY= TMPDIR="${TMPDIR:-$run/tmp}" \
  DEER_FLOW_PROJECT_ROOT="$tool_root/deer-flow" DEER_FLOW_HOME="$run/state" \
  DEER_FLOW_CONFIG_PATH="$run/config.yaml" \
  timeout 1500 "$tool_root/deer-flow/backend/.venv/bin/deerflow" \
    --recursion-limit 100 --json "$1" >"$run/events.jsonl" 2>"$run/cli.stderr"; then
  :
else
  native_rc=$?
fi
python3 - "$run/events.jsonl" "$native_rc" <<'PY'
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

native_rc = int(sys.argv[2])
events, malformed = [], 0
for line in Path(sys.argv[1]).read_text().splitlines():
    if not line.strip():
        continue
    try:
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("Not an event object")
        events.append(event)
    except (ValueError, TypeError):
        malformed += 1
# Follow native chat(): accumulate text by AI message ID, then use the last
# text-bearing ID. A planner's URLs do not qualify the final answer.
chunks, last_id, calls, urls = defaultdict(list), "", {}, set()
search_successes = search_failures = empty_results = 0
for event in events:
    if event.get("type") != "messages-tuple":
        continue
    data = event.get("data", {})
    if not isinstance(data, dict):
        malformed += 1
        continue
    if data.get("type") == "ai":
        tool_calls = data.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            malformed += 1
            tool_calls = []
        for call in tool_calls:
            if (not isinstance(call, dict) or not isinstance(call.get("id"), str)
                    or not call["id"] or not isinstance(call.get("args", {}), dict)):
                malformed += 1
                continue
            calls[call["id"]] = call
        if isinstance(data.get("content"), str) and data["content"]:
            last_id = data.get("id") or ""
            chunks[last_id].append(data["content"])
    elif (data.get("type") == "tool" and data.get("name") == "web_search"
          and calls.get(data.get("tool_call_id"), {}).get("name") == "web_search"):
        try:
            payload = json.loads(data["content"])
        except (KeyError, ValueError, TypeError):
            search_failures += 1
            continue
        call = calls[data["tool_call_id"]]
        # This exact matched object is DDGS's documented empty-result outcome.
        # It does not establish a successful gatherer or a particular endpoint's failure.
        if (isinstance(payload, dict) and payload.get("error") == "No results found"
                and payload.get("query") == call.get("args", {}).get("query")
                and isinstance(payload.get("query"), str) and payload["query"].strip()):
            empty_results += 1
            continue
        results = payload if isinstance(payload, list) else payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            malformed += 1
            results = []
        qualified = []
        for result in results:
            if not isinstance(result, dict):
                malformed += 1
                continue
            title, url = result.get("title", ""), result.get("url", "")
            snippet = result.get("snippet", result.get("content", ""))
            if not all(isinstance(value, str) for value in (title, url, snippet)):
                malformed += 1
                continue
            if title.strip() and url.startswith(("https://", "http://")) and len(snippet.strip()) >= 20:
                qualified.append(result)
        if qualified:
            search_successes += 1
            urls.update(r["url"].rstrip("/") for r in qualified)
        else:
            search_failures += 1
answer = "".join(chunks[last_id])
Path("answer.md").write_text(answer, encoding="utf-8")
ends = [event.get("data", {}) for event in events if event.get("type") == "end"]
if any(not isinstance(end, dict) for end in ends):
    malformed += 1
usage = ends[0].get("usage", {}) if len(ends) == 1 and isinstance(ends[0], dict) else None
citations = {url.rstrip("/.,]") for url in re.findall(r"https?://[^\s)>]+", answer)}
failures = []
if native_rc:
    failures.append("native_cli_failed")
if malformed or len(ends) != 1:
    failures.append("native_stream_incomplete")
if not isinstance(usage, dict) or type(usage.get("total_tokens")) is not int or usage["total_tokens"] <= 0:
    failures.append("no_positive_terminal_usage")
if not search_successes or not answer.strip() or not (citations & urls):
    failures.append("no_completed_search_and_final_cited_answer")
passed = not failures
# Local integration receipt, including failures. Count only a unique native end
# usage record; a missing end leaves usage unknown rather than summing chunks.
Path("integration-check.json").write_text(json.dumps({
    "native_exit_code": native_rc,
    "integration_exit_code": 0 if passed else native_rc or 1,
    "acceptance_status": "passed" if passed else "failed",
    "gatherer_status": "native_failed" if native_rc else "stream_invalid" if malformed or len(ends) != 1 else "complete",
    "provider_status": "available" if search_successes else "empty_results" if empty_results else "unobserved",
    "matched_search_successes": search_successes, "matched_search_failures": search_failures,
    "matched_provider_empty_results": empty_results,
    "terminal_end_events": len(ends), "malformed_event_lines": malformed,
    "final_answer_citations_in_results": len(citations & urls),
    "native_end_usage": usage, "failure_reasons": failures,
    "answer_status": "final_cited" if passed else "unqualified_last_text",
}, indent=2) + "\n")
if not passed:
    print("Native DeerFlow acceptance failed; provider empty results:", empty_results,
          "; native exit:", native_rc, "; retained events, stderr, answer and integration-check.json", file=sys.stderr)
    raise SystemExit(native_rc or 1)
print(answer)
PY
printf 'run directory: %s\n' "$run"
