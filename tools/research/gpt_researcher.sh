#!/usr/bin/env bash
# GPT Researcher, the research runtime's default gatherer, for both clients of the new WSL distribution.
#
#   bash tools/research/gpt_researcher.sh "<short current-month query>"
#   bash tools/research/gpt_researcher.sh --preflight-only
#
# Either client runs it through its own shell (wave-2 synthesis X18). It follows the wave-2 research ruling
# (2026-10-03; evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json, layers.gpt-runtimes, changes 2-5):
# - tools/research/gpt-researcher.config.json preserves session 80's measured profile without its key, with the
#   dated compatibility amendments in integration-resolutions.json:repair_round_4.research_configuration_amendment
#   (unsuffixed smart/strategic aliases and explicit xhigh follow #637; this is not a new measurement).
#   Each run gets its own copy, in its own directory, with base_url set to the gateway below and one
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
# - A source guard fails closed after the CLI exits 0. Upstream's CLI writes one report under outputs/ in its working
#   directory (the run directory), headed by YAML frontmatter whose sources_count is len(researcher.visited_urls)
#   (cli.py L209-245, L225, L241 and L332-336 at 0957c301; skills/researcher.py L813-834 adds a URL to that set when it is
#   selected for scraping). Without exactly one report, a sources_count line or with sources_count 0, the run exits 3: a
#   report written from no sources reads as a success but is not research evidence (run 20261005T222529Z-1387309).
# - The retriever stays duckduckgo (diagnosis of that run, 2026-10-05). At 0957c301, which is also main, it calls ddgs
#   text() with region 'wt-wt' and ddgs's default backend 'auto', and exposes neither to configuration
#   (gpt_researcher/retrievers/duckduckgo/duckduckgo.py L30-52); ddgs 9.16.0, the newest release, reads only DDGS_PROXY
#   (ddgs/ddgs.py L53). Its keyless engines throttle a busy host, and an HTTP 429, 202 or 403 yields no results and no
#   error (ddgs/base.py L65-70), so a failed search reports wikipedia's DNS error for wt.wikipedia.org instead
#   (engines/wikipedia.py L35-39; 'wt-wt' is no ddgs region, deedy5/ddgs#417). Probed here that day: brave 429,
#   duckduckgo 202, google and mojeek 403, yahoo alone with results; arxiv, openalex and semantic_scholar gave five
#   off-topic results, none and a 429, so adding them would hide a dead web search behind scholarly hits. The durable
#   keyless route owed is SearXNG through the searx retriever, after its service and the 30-query measurement
#   (docs/decisions/2026-10-01-new-wsl-definitive-defaults.md L80).
# No credential is read or printed. It prints the upstream CLI's output, then "run directory: <path>", then the report's
# "sources_count: <n>". Exit status: 0 with at least one source; 2 for usage; 1 when GPT Researcher, the preflight or the
# timer is missing or fails; 3 when the source guard fails; otherwise the CLI's own status (124 from the watchdog).
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
if (( status != 0 )); then
  exit "$status"
fi
# The source guard (see above), in the same scrubbed environment; any failure of it, its own included, exits 3.
"${scrub[@]}" "$python" - "$run/outputs" <<'PY' || exit 3
import re
import sys
from pathlib import Path

outputs = Path(sys.argv[1])
reports = sorted(outputs.glob("*.md")) if outputs.is_dir() else []
if len(reports) != 1:
    sys.exit(f"source guard failed: {len(reports)} reports in {outputs}, not one, so the run's sources cannot be counted")
lines = reports[0].read_text(encoding="utf-8", errors="replace").splitlines()
end = lines.index("---", 1) if lines[:1] == ["---"] and "---" in lines[1:] else 0
counts = [int(found.group(1)) for line in lines[1:end] if (found := re.fullmatch(r"sources_count: (\d+)", line.strip()))]
if len(counts) != 1:
    sys.exit(f"source guard failed: {reports[0]} has no single sources_count line in a closed frontmatter, so its sources "
             "cannot be counted")
count = counts[0]
if count == 0:
    sys.exit(f"source guard failed: GPT Researcher retrieved 0 sources (sources_count: 0 in {reports[0]}). A report written "
             "from no sources is not research evidence. The keyless search engines behind the duckduckgo retriever were "
             "probably throttling this host; retry later.")
print(f"sources_count: {count}")
PY
