#!/usr/bin/env bash
# Retire the leftover mcporter 0.13.13 daemon (literal PID 129979) with the native stop, then
# let the production 0.14.1 binary start its own daemon, recording every step. Home paths print as ~.
set -u
EXPECT_PID=129979
EXPECT_PREFIX=tools/mcporter-0.13.13/
ECO="$HOME/.local/share/codex-ecosystem"
MC="$ECO/bin/mcporter"
CFG="$ECO/config/mcporter.json"
san() { sed "s#$HOME#~#g"; }
status_json() {
  timeout 30 "$MC" daemon status --json 2>&1 | python3 -c '
import json, sys
t = sys.stdin.read()
try:
    d = json.loads(t)
except Exception:
    print("status (non-JSON):", t.strip()[:400]); sys.exit()
print(json.dumps({"pid": d.get("pid"), "protocolVersion": d.get("protocolVersion"),
                  "startedAt": d.get("startedAt"),
                  "servers": [{"connected": s.get("connected"), "activeCalls": s.get("activeCalls"),
                               "lastUsedAt": s.get("lastUsedAt")} for s in d.get("servers", [])]}))
'
}
echo "run_start_utc=$(date -u +%FT%TZ)"
echo "bin_mcporter -> $(readlink "$MC" | san)"
echo "bin_mcporter_version=$("$MC" --version 2>&1)"
echo "command_v_ps=$(command -v ps)"
echo "== before"
status_json
cmd=$(tr '\0' ' ' < /proc/$EXPECT_PID/cmdline 2>/dev/null)
echo "pid $EXPECT_PID cmdline: $(echo "$cmd" | san)"
echo "pid $EXPECT_PID started: $(ps -o lstart= -p $EXPECT_PID) (host local time, UTC-4)"
echo "children: $(pgrep -P $EXPECT_PID | tr '\n' ' ')"
echo "socket: $(stat -c '%n mtime=%y' "$HOME/.mcporter/daemon/user.sock" | san)"
echo "socraticode 9c518b2ee5c8 index/graph lock dirs held: $(ls -d /tmp/socraticode-locks/9c518b2ee5c8-index.lock /tmp/socraticode-locks/9c518b2ee5c8-graph.lock 2>/dev/null | wc -l)"
case "$cmd" in
  *"$EXPECT_PREFIX"*"daemon start"*) echo "assert: pid $EXPECT_PID is the 0.13.13 daemon -> ok" ;;
  *) echo "assert FAILED: pid $EXPECT_PID is not the expected 0.13.13 daemon; stopping"; exit 2 ;;
esac
active=$(timeout 30 "$MC" daemon status --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(s.get("activeCalls",0) for s in d.get("servers",[])))')
[ "$active" = "0" ] || { echo "assert FAILED: activeCalls=$active, not drained; stopping"; exit 3; }
echo "assert: activeCalls total 0 -> ok"
echo "== stop"
echo "\$ mcporter daemon stop"
timeout 60 "$MC" daemon stop 2>&1 | san
echo "stop_exit=${PIPESTATUS[0]}"
for i in $(seq 1 20); do kill -0 $EXPECT_PID 2>/dev/null || break; sleep 0.5; done
echo "pid $EXPECT_PID alive after stop: $(kill -0 $EXPECT_PID 2>/dev/null && echo yes || echo no)"
echo "former children alive: $(for c in 130014 130067; do kill -0 $c 2>/dev/null && echo $c; done | tr '\n' ' ')"
echo "socket present after stop: $([ -S "$HOME/.mcporter/daemon/user.sock" ] && echo yes || echo no)"
echo "== restart through production use"
echo "\$ mcporter --config <codex-ecosystem config/mcporter.json> call socraticode.codebase_health --no-oauth"
timeout 180 "$MC" --config "$CFG" call socraticode.codebase_health --no-oauth > "${OUT:-/tmp}/mc-health.out" 2>&1
echo "call_exit=$?"
echo "call_output_first_line: $(head -1 "${OUT:-/tmp}/mc-health.out" | san | cut -c1-160)"
sleep 2
echo "== after"
status_json
newpid=$(timeout 30 "$MC" daemon status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("pid",""))' 2>/dev/null)
if [ -n "$newpid" ]; then
  echo "new daemon pid $newpid cmdline: $(tr '\0' ' ' < /proc/$newpid/cmdline | san)"
else
  echo "no daemon running after the call"
fi
echo "mcporter daemon processes: $(pgrep -f '[m]cporter.*daemon start' | wc -l)"
echo "run_end_utc=$(date -u +%FT%TZ)"
