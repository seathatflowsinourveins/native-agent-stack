#!/usr/bin/env bash
# Parameterized upstream embedded example, not an E2E harness.
# Source: bytedance/deer-flow@v2.1.0 README.md:1658-1663;
# backend/packages/harness/deerflow/client.py:179-217,1193-1223.
set -euo pipefail
if (( $# != 1 )); then printf 'Usage: %s "public research query"\n' "$0" >&2; exit 2; fi
tool_root="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack"
run_root="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/research/deer-flow"
mkdir -p -m 0700 -- "$run_root"
run="$(mktemp -d "$run_root/run.XXXXXXXX")"
mkdir -m 0700 -- "$run/home"
cd -- "$run"
# Native ChatOpenAI default_headers join gateway metadata to this run.
# OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:open-sse/handlers/chatCore.ts:1087-1090,1133.
"$tool_root/deer-flow/backend/.venv/bin/python" - "$config_root/deer-flow-config.yaml" "$run/config.yaml" "deerflow-${run##*/}" <<'CONFIG'
import sys
import yaml
from pathlib import Path
source, target, session = sys.argv[1:]
config = yaml.safe_load(Path(source).read_text())
model, = [model for model in config["models"] if model["name"] == "gpt-runtime"]
model["default_headers"] = {"x-omniroute-session-id": session}
Path(target).write_text(yaml.safe_dump(config))
CONFIG
# Upstream imports its generated project .env. An explicit empty JINA_API_KEY
# survives load_dotenv(override=False), so its example key is never sent.
env -i HOME="$run/home" PATH="$PATH" LANG="${LANG:-C.UTF-8}" JINA_API_KEY= \
  DEER_FLOW_PROJECT_ROOT="$tool_root/deer-flow" DEER_FLOW_HOME="$run/state" \
  DEER_FLOW_CONFIG_PATH="$run/config.yaml" \
  timeout 1500 "$tool_root/deer-flow/backend/.venv/bin/python" - "$1" <<'PY'
import os
import re
import sys
from pathlib import Path
from deerflow.client import DeerFlowClient

client = DeerFlowClient(config_path=os.environ["DEER_FLOW_CONFIG_PATH"], model_name="gpt-runtime")
answer = client.chat(sys.argv[1])
Path("answer.md").write_text(answer, encoding="utf-8")
# These are local integration assertions; chat() above is the upstream example.
if not answer.strip() or not re.search(r"https?://[^\s)\]>]+", answer):
    raise SystemExit("Embedded DeerFlow returned no cited answer; retained answer.md for inspection")
print(answer)
PY
printf 'run directory: %s\n' "$run"
