#!/usr/bin/env bash
# Round 4, second review fix (preregistration round4_review_fix2, 15:45:21Z): rerun the gap-8 remote arm with the
# committed r4_openhands.py against a fresh loopback agent-server, and evaluate the GPU stop rule for that stop.
# Starts the unit's loopback vLLM (serve.sh, pasta namespace, only 127.0.0.1:28431 forwarded), the agent-server on
# 127.0.0.1:28432, runs one RemoteConversation, then stops both. Outputs go to $R with a -fix2 suffix.
# Usage: r4_fix2_remote.sh   (whole run bounded to 20 minutes by the caller's timeout)
set -uo pipefail
C=$HOME/.cache/gap-wave2-20260923/agent-sdks
R=$C/round4
H=$(cd "$(dirname "$0")" && pwd)
SNAP=models--Qwen--Qwen3-4B-Instruct-2507-FP8
gpu() { nvidia-smi --query-gpu=memory.used --format=csv,noheader; }
apps() { nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv; }
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

git -C "$H" hash-object "$H/r4_openhands.py" > "$R/r4_openhands-hash-fix2.txt"
gpu > "$R/gpu-before-fix2.txt"; apps > "$R/compute-apps-before-fix2.txt"
ss -ltnH | awk '{print $4}' | sort > "$R/fix2-listeners-before.txt"
pgrep -af "$SNAP" > "$R/vllm-procs-before-fix2.txt" || echo "none" > "$R/vllm-procs-before-fix2.txt"

stamp > "$R/vllm-start-fix2.txt"
ECOSYSTEM_JOB_MEMORY_HIGH=10G ECOSYSTEM_JOB_MEMORY_MAX=14G ECOSYSTEM_JOB_SECONDS=1500 ECOSYSTEM_JOB_TASKS_MAX=1024 \
  setsid "$HOME/codex-ecosystem/bin/ecosystem-bounded-run" "$R/serve.sh" > "$R/vllm-fix2.log" 2>&1 &
for _ in $(seq 1 120); do
  curl -sf http://127.0.0.1:28431/health > /dev/null && break; sleep 5
done
curl -sf http://127.0.0.1:28431/health > /dev/null || { echo "vllm not healthy" >&2; }
stamp > "$R/vllm-ready-fix2.txt"
gpu > "$R/gpu-during-fix2.txt"; apps > "$R/compute-apps-during-fix2.txt"

mkdir -p "$R/oh-server-cwd-fix2" "$R/oh-server-home-fix2" "$R/oh-ws-remote-fix2" "$R/oh-home"
(cd "$R/oh-server-cwd-fix2" && setsid env -i PATH="$C/oh-agent-server/bin:/usr/bin:/bin" HOME="$R/oh-server-home-fix2" \
  OPENHANDS_SUPPRESS_BANNER=1 LITELLM_LOCAL_MODEL_COST_MAP=True \
  "$C/oh-agent-server/bin/agent-server" --host 127.0.0.1 --port 28432 > "$R/oh-agent-server-fix2.console" 2>&1 &
  echo $! > "$R/oh-agent-server-fix2.pid")
for _ in $(seq 1 60); do
  ss -ltnH | awk '{print $4}' | grep -qx '127.0.0.1:28432' && break; sleep 2
done
sleep 3
ss -ltnH | awk '{print $4}' | sort > "$R/fix2-listeners-during.txt"

env -i PATH=/usr/bin:/bin HOME="$R/oh-home" OPENHANDS_SUPPRESS_BANNER=1 LITELLM_LOCAL_MODEL_COST_MAP=True \
  "$C/openhands/bin/python" "$H/r4_openhands.py" remote "$R/oh-ws-remote-fix2" "$R/oh-persist-remote-unused" \
  "$R/openhands-remote-fix2.json" http://127.0.0.1:28432 2> "$R/openhands-remote-fix2.stderr"
echo "r4_openhands exit $?" > "$R/openhands-remote-fix2.exit"

kill -TERM -- "-$(cat "$R/oh-agent-server-fix2.pid")" 2>/dev/null || kill -TERM "$(cat "$R/oh-agent-server-fix2.pid")"
VPID=""  # the api-server process (pasta's own argv also carries the vllm command line, so skip it)
for p in $(pgrep -f "vllm serve .*$SNAP"); do [ "$(cat /proc/$p/comm 2>/dev/null)" != pasta ] && { VPID=$p; break; }; done
echo "${VPID:-none}" > "$R/vllm-pid-fix2.txt"
[ -n "$VPID" ] && kill -TERM "$VPID"
for _ in $(seq 1 60); do pgrep -f "$SNAP" > /dev/null || break; sleep 2; done
stamp > "$R/vllm-stop-fix2.txt"
sleep 10
gpu > "$R/gpu-after-fix2.txt"; apps > "$R/compute-apps-after-fix2.txt"
pgrep -af "$SNAP" > "$R/vllm-procs-after-fix2.txt" || echo "none" > "$R/vllm-procs-after-fix2.txt"
pgrep -af "agent-server --host 127.0.0.1 --port 28432" > "$R/oh-server-procs-after-fix2.txt" || echo "none" > "$R/oh-server-procs-after-fix2.txt"
ss -ltnH | awk '{print $4}' | sort > "$R/fix2-listeners-after.txt"
echo done
