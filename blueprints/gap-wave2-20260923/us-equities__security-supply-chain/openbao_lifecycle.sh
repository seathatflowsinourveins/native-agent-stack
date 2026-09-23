#!/usr/bin/env bash
# Gaps 6/14: secret lifecycle on a loopback-only OpenBao 2.6.2 dev server
# (in-memory storage, temp HOME, random root token never logged). A synthetic
# test broker credential is written, read with a policy-scoped token, rotated,
# the old version destroyed, and the token revoked; a research-policy token is
# checked for denial. Only exit codes, HTTP-style error lines and SHA-256 of
# returned values are logged, never token or credential values.
set -uo pipefail
C=${C:-$HOME/.cache/gap-wave2-20260923/security-supply-chain}
BAO=$C/openbao-2.6.2/bao
OUT=$C/work/openbao; mkdir -p "$OUT"; LOG=$OUT/lifecycle.log; : > "$LOG"
T=$(mktemp -d "$C/work/openbao-home.XXXX"); export HOME=$T
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
export BAO_ADDR=http://127.0.0.1:$PORT
ROOT=$(python3 -c 'import secrets;print("root-"+secrets.token_hex(16))')
gen() { python3 -c 'import secrets;print("synthetic-"+secrets.token_hex(12))'; }
h() { printf '%s' "$1" | sha256sum | cut -c1-16; }
step() {  # step LABEL EXPECTED_RC TOKEN CMD... ; stdout captured to $OUT_STEP, stderr summarized
  local label=$1 want=$2 tok=$3; shift 3
  OUT_STEP=$(BAO_TOKEN=$tok "$@" 2> "$T/err"); local rc=$?
  local err=$(grep -m1 -oE '(Code: [0-9]+|permission denied|invalid token|bad token|No value found[^.]*)' "$T/err" | paste -sd' ' -)
  local ok=$([[ $rc == "$want" ]] && echo as_expected || echo UNEXPECTED)
  echo "$label exit=$rc expected=$want $ok ${err:+err=[$err]}" | tee -a "$LOG"
}
"$BAO" version | tee -a "$LOG"
"$BAO" server -dev -dev-listen-address="127.0.0.1:$PORT" -dev-root-token-id="$ROOT" -dev-no-store-token \
  > "$T/server.log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null; wait $SRV 2>/dev/null; rm -rf "$T"' EXIT
for i in $(seq 1 50); do BAO_TOKEN=$ROOT "$BAO" status >/dev/null 2>&1 && break; sleep 0.2; done
echo "server pid=$SRV listen=127.0.0.1:(ephemeral) storage=inmem" | tee -a "$LOG"
ss -ltnp 2>/dev/null | grep -E "pid=$SRV\b" | awk '{print "listening on", $4}' | sed "s/:$PORT/:<port>/" | tee -a "$LOG"

cat > "$T/broker.hcl" <<'EOF'
path "secret/data/broker/alpaca-paper" { capabilities = ["read"] }
EOF
cat > "$T/research.hcl" <<'EOF'
path "secret/data/research/*" { capabilities = ["read", "list"] }
EOF
step policy-broker-reader 0 "$ROOT" "$BAO" policy write broker-reader "$T/broker.hcl"
step policy-research 0 "$ROOT" "$BAO" policy write research "$T/research.hcl"
V1_ID=$(gen); V1_SECRET=$(gen)
step kv-put-v1 0 "$ROOT" "$BAO" kv put -mount=secret broker/alpaca-paper key_id="$V1_ID" secret_key="$V1_SECRET"
step research-put-note 0 "$ROOT" "$BAO" kv put -mount=secret research/notes topic=factors
step token-create-broker 0 "$ROOT" "$BAO" token create -policy=broker-reader -ttl=15m -field=token
TB=$OUT_STEP
step token-create-research 0 "$ROOT" "$BAO" token create -policy=research -ttl=15m -field=token
TR=$OUT_STEP
step broker-token-read-v1 0 "$TB" "$BAO" kv get -mount=secret -field=secret_key broker/alpaca-paper
echo "  read value matches v1: $([[ $OUT_STEP == "$V1_SECRET" ]] && echo yes || echo no) sha=$(h "$OUT_STEP")" | tee -a "$LOG"
step research-token-read-broker-DENIED 2 "$TR" "$BAO" kv get -mount=secret -field=secret_key broker/alpaca-paper
step research-token-read-own-path 0 "$TR" "$BAO" kv get -mount=secret -field=topic research/notes
step broker-token-write-DENIED 2 "$TB" "$BAO" kv put -mount=secret broker/alpaca-paper key_id=x secret_key=y
# Rotation: a new version replaces the credential; the old version is destroyed.
V2_ID=$(gen); V2_SECRET=$(gen)
step kv-rotate-v2 0 "$ROOT" "$BAO" kv put -mount=secret broker/alpaca-paper key_id="$V2_ID" secret_key="$V2_SECRET"
step broker-token-read-after-rotation 0 "$TB" "$BAO" kv get -mount=secret -field=secret_key broker/alpaca-paper
echo "  read value matches v2: $([[ $OUT_STEP == "$V2_SECRET" ]] && echo yes || echo no); differs from v1: $([[ $OUT_STEP != "$V1_SECRET" ]] && echo yes || echo no)" | tee -a "$LOG"
step kv-destroy-v1 0 "$ROOT" "$BAO" kv destroy -mount=secret -versions=1 broker/alpaca-paper
step read-destroyed-v1 2 "$ROOT" "$BAO" kv get -mount=secret -version=1 -field=secret_key broker/alpaca-paper
step kv-metadata 0 "$ROOT" "$BAO" kv metadata get -mount=secret -format=json broker/alpaca-paper
echo "  metadata: $(printf '%s' "$OUT_STEP" | python3 -c 'import json,sys;d=json.load(sys.stdin)["data"];print("current_version",d["current_version"],{k:v["destroyed"] for k,v in d["versions"].items()})')" | tee -a "$LOG"
# Revocation.
step token-revoke-broker 0 "$ROOT" "$BAO" token revoke "$TB"
step broker-token-read-after-revoke-DENIED 2 "$TB" "$BAO" kv get -mount=secret -field=secret_key broker/alpaca-paper
step broker-token-lookup-after-revoke-DENIED 2 "$TB" "$BAO" token lookup
step research-token-still-valid 0 "$TR" "$BAO" token lookup -format=json
step token-revoke-research 0 "$ROOT" "$BAO" token revoke "$TR"
kill $SRV; wait $SRV 2>/dev/null; echo "server stopped exit_signal=$?" | tee -a "$LOG"
sleep 0.5; ss -ltn | grep -c ":$PORT " | sed 's/^/listeners_left_on_port=/' | tee -a "$LOG"
grep -c UNEXPECTED "$LOG" | sed 's/^/unexpected_steps=/' | tee -a "$LOG"
