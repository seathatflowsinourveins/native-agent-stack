#!/usr/bin/env bash
# One Tavily Research (pro) cross-check for one sweep layer. Key: kernel keyring only (never a file or argv).
set -uo pipefail
S="$(cd "$(dirname "$0")" && pwd)"; SP="$(dirname "$S")"; lid="$1"; out="$S/tavily/$lid.json"
[ -s "$out" ] && { echo "skip $lid"; exit 0; }
q=$(python3 - "$S/inputs/$lid.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
w = "; ".join(f"{x.get('component_id')} ({x.get('repository')}, pin {x.get('pin')})" for x in d.get("winners", []))
print(f"As of late September 2026, for this software layer of an open-source agentic engineering and US-equities research stack (Linux/WSL2 RTX 4090 workstation and macOS arm64), identify the strongest CURRENT open-source candidates (maintained, 2025-2026 releases) that could beat or complement the current choices, judged on merit (measured quality, SOTA-ness, maintenance, license, platform fit), and say whether each current choice still earns its place. Layer: {d['title']} ({d['catalog']}/{d['layer_id']}). Requirement: {d['requirement']} Current choices: {w or 'none selected'}. For each candidate give the GitHub repository URL, latest release and date, license, and the concrete advantage or gap, citing primary sources (GitHub, official docs, model cards).")
PY
)
python3 "$SP/kernel_keyring.py" exec tavily_api_key TAVILY_API_KEY -- tvly research run --model pro --json --citation-format numbered --timeout 1500 --client-name native-agent-stack -o "$out" "$q" < /dev/null > "$S/tavily/$lid.stdout" 2> "$S/tavily/$lid.stderr"
echo "$lid rc=$?"
