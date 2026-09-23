#!/bin/bash
# Usage: run_arm.sh <arm-name: with|without> <run-index> <mcp-config-path or "">
set -uo pipefail
ARM="$1"
IDX="$2"
MCPCFG="$3"
OUTDIR="~/codex-ecosystem/state/gap-wave2-20260923/rag-ops/gap6/runs"
mkdir -p "$OUTDIR"
QFILE="~/codex-ecosystem/state/gap-wave2-20260923/rag-ops/gap6/question.txt"
OUT="$OUTDIR/${ARM}_${IDX}.json"
STDOUT="$OUTDIR/${ARM}_${IDX}.stdout"
STDERR="$OUTDIR/${ARM}_${IDX}.stderr"

cd ~/code/agent-lab || exit 9
START=$(date -u +%s.%N)
if [ -n "$MCPCFG" ]; then
  flock ~/codex-ecosystem/state/gap-wave2-20260923/claude.lock \
    claude -p "$(cat "$QFILE")" \
      --mcp-config "$MCPCFG" --strict-mcp-config \
      --permission-mode bypassPermissions \
      --effort low \
      --add-dir ~/code/agent-lab \
      --output-format json \
      > "$STDOUT" 2> "$STDERR"
else
  flock ~/codex-ecosystem/state/gap-wave2-20260923/claude.lock \
    claude -p "$(cat "$QFILE")" \
      --strict-mcp-config \
      --permission-mode bypassPermissions \
      --effort low \
      --add-dir ~/code/agent-lab \
      --output-format json \
      > "$STDOUT" 2> "$STDERR"
fi
RC=$?
END=$(date -u +%s.%N)
DUR=$(python3 -c "print(round($END-$START,2))")
echo "{\"arm\":\"$ARM\",\"idx\":$IDX,\"rc\":$RC,\"duration_s\":$DUR}" > "$OUT.meta"
echo "arm=$ARM idx=$IDX rc=$RC dur=${DUR}s"
sleep 20
