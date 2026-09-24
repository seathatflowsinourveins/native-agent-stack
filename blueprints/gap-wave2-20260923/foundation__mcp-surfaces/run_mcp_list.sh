#!/usr/bin/env bash
# Gap 5 (foundation/mcp-surfaces, wave 2): which MCP servers load from project configuration alone.
#
# Each CLI runs inside `unshare -rnm` (user+net+mount namespace): no network at all (so no registry,
# marketplace or live-service contact is possible), $HOME re-mounted read-only (so the project
# checkout and real config cannot be written), and only this run's temp root writable. Claude and Codex
# get fresh temp CLAUDE_CONFIG_DIR / CODEX_HOME / HOME, so no user-scope server, plugin or marketplace
# entry exists; anything listed must come from the project files.
#
# Usage: run_mcp_list.sh OUT_DIR
set -uo pipefail
OUT=$(realpath "$1"); mkdir -p "$OUT"
CACHE=$HOME/.cache/gap-wave2-20260923/mcp-surfaces
T=$CACHE/runs/mcplist-$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$T"
CLAUDE_BIN=$(readlink -f $HOME/.local/bin/claude)
CODEX_BIN=$(readlink -f $HOME/.local/share/codex-ecosystem/bin/codex)
PROJECT=$HOME/code/agent-lab
ECO=$HOME/.local/share/codex-ecosystem

# scratch projects -----------------------------------------------------------
mkdir -p "$T/scratch-empty" "$T/scratch-config/.claude" "$T/scratch-config/.codex"
cat > "$T/scratch-config/.mcp.json" <<EOF
{"mcpServers": {"scratch-jcodemunch": {"type": "stdio", "command": "$ECO/bin/jcodemunch-mcp",
  "env": {"CODE_INDEX_PATH": "$T/code-index", "JCODEMUNCH_SHARE_SAVINGS": "0"}}}}
EOF
echo '{"enabledMcpjsonServers": ["scratch-jcodemunch"]}' > "$T/scratch-config/.claude/settings.local.json"
cat > "$T/scratch-config/.codex/config.toml" <<EOF
[mcp_servers.scratch-jcodemunch]
command = "$ECO/bin/jcodemunch-mcp"
[mcp_servers.scratch-jcodemunch.env]
CODE_INDEX_PATH = "$T/code-index"
JCODEMUNCH_SHARE_SAVINGS = "0"
EOF

run() {  # label cwd trusted(0/1) cli [approve-claude-servers-csv]
  local label=$1 cwd=$2 trusted=$3 cli=$4 approve=${5:-} H="$T/home-$1-$4"
  mkdir -p "$H/.claude-config" "$H/.codex"
  if [ -n "$approve" ]; then  # local client approval state only (addendum 04:23:01Z)
    python3 -c "import json,sys; json.dump({'projects': {sys.argv[1]: {'hasTrustDialogAccepted': True, 'enabledMcpjsonServers': sys.argv[2].split(',')}}}, open(sys.argv[3], 'w'))" "$cwd" "$approve" "$H/.claude-config/.claude.json"
  fi
  if [ "$trusted" = 1 ]; then
    printf '[projects."%s"]\ntrust_level = "trusted"\n' "$cwd" > "$H/.codex/config.toml"
  else
    : > "$H/.codex/config.toml"
  fi
  local cmd
  if [ "$cli" = claude ]; then cmd="$CLAUDE_BIN mcp list"; else cmd="$CODEX_BIN mcp list --json"; fi
  local start end rc
  start=$(date -u +%FT%TZ)
  unshare -rnm bash -c "mount --rbind $HOME $HOME && mount -o remount,bind,ro $HOME \
      && mount --bind '$T' '$T' && mount -o remount,bind,rw '$T' && cd '$cwd' && \
      env -i HOME='$H' USER=$USER LANG=C.UTF-8 TERM=dumb PATH='$ECO/bin:/usr/bin:/bin' \
        CLAUDE_CONFIG_DIR='$H/.claude-config' CODEX_HOME='$H/.codex' \
        DISABLE_AUTOUPDATER=1 DISABLE_TELEMETRY=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
        timeout 240 $cmd" > "$T/$label-$cli.out" 2> "$T/$label-$cli.err"
  rc=$?
  end=$(date -u +%FT%TZ)
  # sanitize host paths; codex --json can echo env values, so values of env maps are redacted
  python3 - "$T/$label-$cli.out" "$OUT/5-$label-$cli.stdout.txt" <<'PY'
import sys, re, json
s = open(sys.argv[1], errors="replace").read()
try:
    d = json.loads(s)
    for srv in (d if isinstance(d, list) else []):
        for k in ("env",):
            if isinstance(srv.get("transport", {}).get(k), dict):
                srv["transport"][k] = {kk: "<redacted>" for kk in srv["transport"][k]}
            if isinstance(srv.get(k), dict):
                srv[k] = {kk: "<redacted>" for kk in srv[k]}
    s = json.dumps(d, indent=1)
except Exception:
    pass
import os
open(sys.argv[2], "w").write(s.replace(os.path.expanduser("~"), "$HOME"))
PY
  sed "s#$HOME#\$HOME#g" "$T/$label-$cli.err" > "$OUT/5-$label-$cli.stderr.txt"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$label" "$cli" "$rc" "$start" "$end" "$(echo "$cwd" | sed "s#$HOME#\$HOME#")" >> "$OUT/5-mcp-list-index.tsv"
}

[ -s "$OUT/5-mcp-list-index.tsv" ] || printf 'label\tcli\texit\tstarted\tended\tcwd\n' > "$OUT/5-mcp-list-index.tsv"
if [ "${ONLY_APPROVED:-0}" != 1 ]; then
  for cli in claude codex; do
    run project "$PROJECT" 1 $cli
    run scratch-empty "$T/scratch-empty" 1 $cli
    run scratch-config "$T/scratch-config" 1 $cli
  done
  run project-untrusted "$PROJECT" 0 codex
fi
run project-approved "$PROJECT" 1 claude serena,ai-memory,socraticode
run scratch-config-approved "$T/scratch-config" 1 claude scratch-jcodemunch
# prove no registry/plugin/marketplace state was created in the temp client homes
{ echo "T=$T" | sed "s#$HOME#\$HOME#g"; ( cd "$T" && find . -maxdepth 4 \( -name 'plugins' -o -name 'marketplaces*' -o -name 'known_marketplaces.json' \) | sort ); echo "(end; empty list = no plugin/marketplace state)"; } >> "$OUT/5-registry-state-find.txt"
cat "$OUT/5-mcp-list-index.tsv"
