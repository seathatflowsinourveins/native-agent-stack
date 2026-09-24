#!/usr/bin/env bash
# Gaps 8/14 (environment arm): which broker credential variables reach (A) the
# codex child process launched by the research worker's SDK (openai-codex) and
# (B) a command run under the Codex Linux sandbox with the default
# shell_environment_policy. Canary values are synthetic and generated per run;
# only variable NAMES and canary hit counts are logged. No model call, no broker
# contact, no account access: the SDK child is a stub that records its
# environment, and `codex sandbox` uses a temporary empty CODEX_HOME.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
REPO=${REPO:-$HOME/code/nas-wt-g2-security-supply-chain}
SDK_PY=${SDK_PY:-$HOME/.local/share/codex-ecosystem/tools/equity-worker-sdk/bin/python}
CODEX=${CODEX:-$HOME/.local/share/codex-ecosystem/bin/codex}
OUT=$C/work/worker-env; rm -rf "$OUT"; mkdir -p "$OUT/codex-home" "$OUT/ws"
LOG=$OUT/results.log; : > "$LOG"
CANARY=canary$(python3 -c 'import secrets;print(secrets.token_hex(6))')
BROKER_VARS=(APCA_API_KEY_ID APCA_API_SECRET_KEY APCA_API_BASE_URL ALPACA_API_KEY ALPACA_SECRET_KEY
             TWS_USERNAME TWS_PASSWORD TWS_ACCOUNT IBKR_ACCOUNT_ID)
canary_env=(); for v in "${BROKER_VARS[@]}"; do canary_env+=("$v=$CANARY-$v"); done

cat > "$OUT/stub-codex" <<EOF
#!/bin/sh
# Stub standing in for the codex binary: record which broker variables arrived.
env | cut -d= -f1 | grep -E '^(APCA|ALPACA|TWS|IBKR)_' | sort > "$OUT/\${STUB_LABEL}.names"
exit 0
EOF
chmod 700 "$OUT/stub-codex"

sdk_launch() {  # sdk_launch LABEL ENV-PREFIX...  -> SDK starts the stub exactly as native_worker.py configures it
  local label=$1; shift
  "$@" STUB_LABEL="$label" "$SDK_PY" - "$OUT" <<'EOF'
import sys, time, uuid
from pathlib import Path
from openai_codex.client import CodexClient, CodexConfig
out = Path(sys.argv[1])
cfg = CodexConfig(codex_bin=str(out / "stub-codex"), cwd=str(out / "ws"),
                  env={"CODEX_HOME": str(out / "codex-home"), "CONTEXT_MODE_PROJECT_DIR": str(out / "ws"),
                       "OTEL_RESOURCE_ATTRIBUTES": f"service.instance.id={uuid.uuid4()},ecosystem.client.scope=sdk-worker"})
c = CodexClient(cfg); c.start(); time.sleep(1.0); c.close()
EOF
  echo "A:$label exit=$? broker_vars_in_codex_child=[$(paste -sd, "$OUT/$label.names")]" | tee -a "$LOG"
}
# A1: positive control - launcher environment carries broker canaries.
sdk_launch launcher-with-broker-env env "${canary_env[@]}"
# A2: documented dedicated research environment (no broker variables supplied).
sdk_launch dedicated-research-env env -i PATH=/usr/bin:/bin HOME="$OUT/ws"

# B: Codex Linux sandbox with default shell_environment_policy, canaries in the parent.
probe='env | cut -d= -f1 | grep -E "^(APCA|ALPACA|TWS|IBKR)_" | sort | paste -sd, -; n=0; for f in /proc/[0-9]*/environ; do { tr "\0" "\n" < "$f"; } 2>/dev/null | grep -q "'"$CANARY"'" && n=$((n+1)); done; echo "procs_with_canary_in_environ=$n"'
b=$(env "${canary_env[@]}" CODEX_HOME="$OUT/codex-home" "$CODEX" sandbox -- /bin/sh -c "$probe" 2> "$OUT/sandbox.stderr"); rc=$?
echo "B:codex-sandbox-default-policy exit=$rc broker_vars_in_shell=[$(echo "$b" | sed -n 1p)] $(echo "$b" | sed -n 2p)" | tee -a "$LOG"
# B control: the same /proc probe outside the sandbox must find the canary in its own shell's environ.
ctl=$(env "${canary_env[@]}" /bin/sh -c "$probe"); echo "B:control-unsandboxed broker_vars_in_shell=[$(echo "$ctl" | sed -n 1p)] $(echo "$ctl" | sed -n 2p)" | tee -a "$LOG"
# B2: explicit worker hardening candidate - shell_environment_policy.inherit=none.
b2=$(env "${canary_env[@]}" CODEX_HOME="$OUT/codex-home" "$CODEX" sandbox -c shell_environment_policy.inherit=none -- /bin/sh -c "$probe" 2>> "$OUT/sandbox.stderr"); rc=$?
echo "B2:codex-sandbox-inherit-none exit=$rc broker_vars_in_shell=[$(echo "$b2" | sed -n 1p)] $(echo "$b2" | sed -n 2p)" | tee -a "$LOG"
# B3: the documented default-exclude patterns (*KEY*, *SECRET*, *TOKEN*) switched on explicitly.
b3=$(env "${canary_env[@]}" CODEX_HOME="$OUT/codex-home" "$CODEX" sandbox -c shell_environment_policy.ignore_default_excludes=false -- /bin/sh -c "$probe" 2>> "$OUT/sandbox.stderr"); rc=$?
echo "B3:codex-sandbox-default-excludes-on exit=$rc broker_vars_in_shell=[$(echo "$b3" | sed -n 1p)] $(echo "$b3" | sed -n 2p)" | tee -a "$LOG"
# Ambient launcher: names (never values) of broker-prefixed variables already present in this shell.
echo "ambient_launcher_broker_var_names=[$(env | cut -d= -f1 | grep -E '^(APCA|ALPACA|TWS|IBKR)_' | sort | paste -sd, -)]" | tee -a "$LOG"
"$CODEX" --version | tee -a "$LOG"
