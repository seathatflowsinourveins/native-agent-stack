#!/usr/bin/env bash
# Acceptance recipe through Harbor's own job runner and ATIF validator.
# Source: harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:
# docs-mintlify/core-concepts/jobs/configs.mdx:6-11;
# docs-mintlify/core-concepts/agents/atif.mdx:121-128;
# tests/integration/test_hello_user_e2e.py:50-53.
set -euo pipefail
if [[ -v CODEX_AUTH_JSON_PATH || -v CODEX_FORCE_AUTH_JSON ]]; then
  printf 'needs_user: auth-store upload is forbidden; unset CODEX_AUTH_JSON_PATH and CODEX_FORCE_AUTH_JSON and use the OpenAI key runner.\n' >&2
  exit 78
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  printf 'needs_user: the containerized Codex leg requires OPENAI_API_KEY from the per-provider key runner; a ChatGPT native sign-in alone cannot qualify this leg.\n' >&2
  exit 78
fi
export HARBOR_TELEMETRY=off
if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
  printf 'needs_user: supply the rootless Docker runtime directory.\n' >&2
  exit 78
fi
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
if [[ -z "${HARBOR_TELEMETRY_TASKS:-}" || -z "${HARBOR_TELEMETRY_TASKS_REV:-}" || -z "${HARBOR_TELEMETRY_JOB_CONFIG:-}" ]]; then
  printf 'needs_user: supply the versioned native-telemetry Harbor task corpus, its full commit, and its Harbor JSON job config; see harbor-worker-telemetry-contract.md.\n' >&2
  exit 78
fi
[[ "$HARBOR_TELEMETRY_TASKS_REV" =~ ^[0-9a-f]{40}$ ]]
[[ "$(git -C "$HARBOR_TELEMETRY_TASKS" rev-parse HEAD)" == "$HARBOR_TELEMETRY_TASKS_REV" ]]
git -C "$HARBOR_TELEMETRY_TASKS" diff --quiet
git -C "$HARBOR_TELEMETRY_TASKS" diff --cached --quiet
tool_root="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools"
producer_python="$tool_root/agent-runtime-worker/bin/python"
if [[ ! -x "$producer_python" ]]; then
  printf 'needs_user: install the agent-runtime-worker producer before telemetry qualification.\n' >&2
  exit 78
fi
# Read the actual producer package metadata; never qualify a different adapter.
producer_version="$("$producer_python" -c 'from importlib.metadata import version; print(version("openhands-sdk"))')"
export producer_version
python3 - "$HARBOR_TELEMETRY_JOB_CONFIG" <<'PY'
import json
import os
import sys
from pathlib import Path

# Inspect only a public job recipe, never credential files or values.
config = json.loads(Path(sys.argv[1]).read_text())
agents = config.get("agents", [])
assert len(agents) == 3, "the qualification requires all three native adapters"
by_name = {agent["name"]: agent for agent in agents}
assert set(by_name) == {"codex", "openhands-sdk", "deerflow"}
assert by_name["codex"].get("kwargs", {}).get("version") == "0.160.0"
adapter_version = by_name["openhands-sdk"].get("kwargs", {}).get("version")
if adapter_version != os.environ["producer_version"]:
    print("needs_user: Harbor OpenHands adapter version does not match the installed agent-runtime-worker producer; its owner must reconcile and qualify the pin.", file=sys.stderr)
    raise SystemExit(78)
assert by_name["deerflow"].get("kwargs", {}).get("repo_ref") == "v2.1.0"
assert by_name["codex"].get("model_name") == "gpt-6.1-sol"
native = by_name["codex"].get("kwargs", {}).get("config", {})
assert isinstance(native, dict) and native.get("model_provider") == "openai"
assert native.get("model_reasoning_effort") == "max"
assert all(agent.get("model_name") for agent in agents)
assert not config.get("install_only", False)
assert not config.get("verifier", {}).get("disable", False)
PY
umask 077
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/acceptance/harbor"
mkdir -p -- "$state_root"
run="$(mktemp -d "$state_root/worker-telemetry.XXXXXXXX")"
# Native config preserves each adapter's documented routing and artifact settings.
# No provider account, credential store, or collector configuration is copied.
harbor run --config "$HARBOR_TELEMETRY_JOB_CONFIG" -p "$HARBOR_TELEMETRY_TASKS" \
  -e docker --force-build -n 1 -o "$run" --job-name worker-telemetry
python3 - "$run/worker-telemetry" "$tool_root/harbor-v0.23.0" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

root, checkout = map(Path, sys.argv[1:3])
results = list(root.glob("*/result.json"))
assert results, "Harbor returned no retained trial results"
agents, tasks = set(), {}
for path in results:
    result = json.loads(path.read_text())
    agent = result["agent_info"]["name"]
    agents.add(agent)
    tasks.setdefault(result["task_name"], set()).add(agent)
    assert result["exception_info"] is None
    assert result["verifier_result"] is not None
    assert result["verifier_result"]["rewards"] is not None
    assert result["verifier_result"]["rewards"].get("reward") == 1.0
    if agent in {"codex", "openhands-sdk"}:
        expected = "0.160.0" if agent == "codex" else os.environ["producer_version"]
        assert result["agent_info"]["version"] == expected, "container runtime pin mismatch"
    trajectory = path.parent / "agent/trajectory.json"
    assert trajectory.is_file(), "missing native adapter ATIF output"
    subprocess.run(["uv", "run", "--frozen", "--directory", str(checkout), "python", "-m",
                    "harbor.utils.trajectory_validator", str(trajectory)], check=True)
assert agents == {"codex", "openhands-sdk", "deerflow"}
assert all(seen == agents for seen in tasks.values()), "incomplete adapter/task matrix"
print("Harbor telemetry recipe: retained verifier results and ATIF validation passed")
PY
printf 'run directory: %s\n' "$run"
