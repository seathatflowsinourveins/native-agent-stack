#!/usr/bin/env bash
# One bounded adaptive paper trial: ingest a fresh promotion-gate snapshot,
# gate it, then run `runner.py paper` once. Never retries; every step's output
# stays under OUT_DIR. The STOP file kill switch (safety.DEFAULT_STOP) applies.
#
# Required env: TRIAL (runner trial id, [a-z0-9-]{1,24}), ENV_FILE (0600 paper
# credential file outside any Git worktree), STATE_ROOT, OUT_DIR.
# Optional: CONFIG (default config-sip.json), PY, GATE_PY, LIVE_DIR (runner --live-dir:
# live decision/intent stream and NautilusTrader JSON log). Run it from a frozen,
# read-only copy of a published commit (git archive), never from a live worktree.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
data="$(cd "$here/../data" && pwd)"
: "${TRIAL:?}" "${ENV_FILE:?}" "${STATE_ROOT:?}" "${OUT_DIR:?}"
CONFIG="${CONFIG:-$here/config-sip.json}"
PY="${PY:-$HOME/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python}"
GATE_PY="${GATE_PY:-$HOME/.local/share/codex-ecosystem/tools/promotion-gate-20260922/.venv/bin/python3}"
mkdir -p "$OUT_DIR"
live=()
if [ -n "${LIVE_DIR:-}" ]; then live=(--live-dir "$LIVE_DIR"); fi
# One run per OUT_DIR: the lock directory is created atomically and never removed.
if ! mkdir "$OUT_DIR/.run-once" 2>/dev/null; then
  echo "refused: $OUT_DIR already holds a run (remove nothing; use a new OUT_DIR and TRIAL)" >&2
  exit 3
fi
exec >>"$OUT_DIR/scheduled-trial.log" 2>&1
echo "start $(date -u +%FT%TZ) trial=$TRIAL config_sha256=$(sha256sum "$CONFIG" | cut -c1-64)"
timeout 120 "$PY" "$data/ingest_snapshot.py" --env-file "$ENV_FILE" --config "$CONFIG" \
  --out "$OUT_DIR/universe-daily.csv" --receipt "$OUT_DIR/ingest-receipt.json"
timeout 120 "$GATE_PY" "$data/promotion_gate.py" --input "$OUT_DIR/universe-daily.csv" \
  --out "$OUT_DIR/gate-result.json" --calendar XNYS
set +e
timeout 900 "$PY" "$here/runner.py" paper --env-file "$ENV_FILE" --config "$CONFIG" \
  --output "$OUT_DIR/paper-output.json" --trial "$TRIAL" --state-root "$STATE_ROOT" \
  --gate-result "$OUT_DIR/gate-result.json" --snapshot "$OUT_DIR/universe-daily.csv" "${live[@]}"
rc=$?
echo "end $(date -u +%FT%TZ) runner_rc=$rc"
exit "$rc"
