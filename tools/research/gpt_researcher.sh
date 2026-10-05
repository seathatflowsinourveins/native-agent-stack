#!/usr/bin/env bash
# GPT Researcher, the research runtime's default gatherer, for both clients of the new WSL distribution.
#
#   bash tools/research/gpt_researcher.sh "<short current-month query>"
#   bash tools/research/gpt_researcher.sh --preflight-only
#
# Either client runs it through its own shell (wave-2 synthesis X18). It follows the wave-2 research ruling
# (2026-10-03; evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json, layers.gpt-runtimes, changes 2-5):
# - The configuration is tools/research/gpt-researcher.config.json beside this file: the measured session-80 values
#   without the key. Each run gets its own copy, in its own directory, with base_url set to the gateway below and one
#   x-omniroute-session-id value, the join key of the gateway's call log
#   (OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:open-sse/handlers/chatCore.ts:1087-1090,1133).
# - The run starts from an empty environment (env -i). Upstream's Config lets an environment variable override a file
#   setting (gpt_researcher/config/config.py L63-76 at 0957c301), so nothing inherited may reach it.
# - The key is the gateway's placeholder, inline: the destination gateway is keyless on loopback, the credential runner
#   cannot rename the gateway entry's OMNIROUTE_API_KEY, and OPENAI_API_KEY must not be set in any shell
#   (adoption/credential-inventory.json, must_not_be_set).
# - A preflight in upstream's own Config fails closed, before any network call: Config falls back to its built-in
#   defaults (the tavily retriever and other models) when the file is missing (config.py L158-170).
# - Only --report_type research_report runs; detailed_report reaches the embeddings route (research change 5).
# - The research run keeps a 1500-second watchdog. Its timer is resolved before the scrub, from the caller's PATH, and run
#   by absolute path, since the scrubbed PATH (/usr/bin:/bin) has no timeout on macOS: GNU coreutils' timeout, else
#   gtimeout, the name Homebrew's coreutils gives it there. With neither, the research run fails closed (exit 1) before it
#   starts; --preflight-only does not need one.
# No credential is read or printed. It prints the upstream CLI's output, then "run directory: <path>".
# GPTR_CONFIG_SOURCE names another configuration to copy (the tests use it); the preflight holds any copy to the same rule.
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
gateway="http://127.0.0.1:21128/v1"
tool_root="${XDG_DATA_HOME:-$HOME/.local/share}/new-wsl-native-stack/tools"
checkout="$tool_root/gpt-researcher"
python="$checkout/.venv/bin/python"
config_source="${GPTR_CONFIG_SOURCE:-$here/gpt-researcher.config.json}"
if (( $# != 1 )) || [[ -z "$1" ]]; then
  printf 'Usage: %s "<short current-month query>" | --preflight-only\n' "$0" >&2
  exit 2
fi
query="$1"
if [[ ! -x "$python" || ! -f "$checkout/cli.py" ]]; then
  printf 'GPT Researcher is not installed under %s (install plan row research-harnesses).\n' "$checkout" >&2
  exit 1
fi
# type -P searches PATH for an executable file only (no alias, function or builtin); a relative PATH entry is anchored here.
timer="$(type -P timeout || type -P gtimeout || true)"
if [[ -n "$timer" && "$timer" != /* ]]; then
  timer="$PWD/$timer"
fi
run="${XDG_STATE_HOME:-$HOME/.local/state}/new-wsl-native-stack/research/gptr/$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$run" "$run/home"
"$python" - "$config_source" "$run/config.json" "$gateway" "gptr-${run##*/}" <<'PY'
import json
import sys

source, target, gateway, session = sys.argv[1:5]
with open(source, encoding="utf-8") as handle:
    config = json.load(handle)
kwargs = config.setdefault("LLM_KWARGS", {})
kwargs.pop("api_key", None)
kwargs["base_url"] = gateway
kwargs["default_headers"] = {"x-omniroute-session-id": session}
with open(target, "w", encoding="utf-8") as handle:
    json.dump(config, handle, indent=1)
PY
cd "$run"
scrub=(env -i HOME="$run/home" PATH="/usr/bin:/bin" LANG=C.UTF-8 CONFIG_PATH="$run/config.json"
       OPENAI_BASE_URL="$gateway" OPENAI_API_KEY="local-loopback")
"${scrub[@]}" "$python" - "$gateway" "$checkout" <<'PY'
import os
import sys

gateway, checkout = sys.argv[1:3]
path = os.environ.get("CONFIG_PATH", "")
if not os.path.isfile(path):
    sys.exit("preflight failed: CONFIG_PATH is not an existing file")
sys.path.insert(0, checkout)
from gpt_researcher.config import Config  # upstream's own reading of the file and the environment

config = Config(path)
problems = []
if config.retrievers != ["duckduckgo"]:
    problems.append(f"retrievers {config.retrievers!r}, not ['duckduckgo']")
if getattr(config, "context_filter", None) != "keyword":
    problems.append(f"context filter {getattr(config, 'context_filter', None)!r}, not 'keyword'")
wanted = {"fast": ("openai", "cx/gpt-6.1-sol-high"), "smart": ("openai", "cx/gpt-6.1-sol"),
          "strategic": ("openai", "cx/gpt-6.1-sol")}
for role, pair in wanted.items():
    found = (getattr(config, f"{role}_llm_provider", None), getattr(config, f"{role}_llm_model", None))
    if found != pair:
        problems.append(f"{role} model {found!r}, not {pair!r}")
kwargs = getattr(config, "llm_kwargs", None) or {}
if kwargs.get("reasoning_effort") != "xhigh":
    problems.append("gateway research reasoning_effort must be xhigh on OmniRoute 3.8.51")
base_url = kwargs.get("base_url")
if not base_url == os.environ.get("OPENAI_BASE_URL") == gateway:
    problems.append(f"base_url {base_url!r} and OPENAI_BASE_URL {os.environ.get('OPENAI_BASE_URL')!r} are not {gateway!r}")
if problems:
    sys.exit("preflight failed: " + "; ".join(problems))
PY
if [[ "$query" == --preflight-only ]]; then
  printf 'preflight passed\nrun directory: %s\n' "$run"
  exit 0
fi
if [[ -z "$timer" ]]; then
  printf 'No supported timer for the 1500-second watchdog of the research run: neither timeout (GNU coreutils) nor gtimeout (Homebrew coreutils) is on PATH. The research did not start.\n' >&2
  exit 1
fi
status=0
"${scrub[@]}" "$timer" 1500 "$python" "$checkout/cli.py" "$query" --report_type research_report --tone objective --no-pdf --no-docx \
  || status=$?
printf 'run directory: %s\n' "$run"
exit "$status"
