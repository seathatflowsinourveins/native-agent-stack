#!/usr/bin/env bash
# Gap 6 challenger arm: run native `git diff --no-index` (as the structural-diff
# challenger to difftastic) over the SAME 20-file, byte-verified old/new tree
# extracted for the prior wave's difftastic-larger-fixture.json (commit range
# 231077d095511391e7dd8a5ab25c451331332c5e..bdd04ca50eb781f8366c955f481479b7a7f57cbd).
# Does not re-extract or modify old/new; read-only over that retained tree.
set -euo pipefail
D="$HOME/codex-ecosystem/state/gap-resolution-20260922/worktrunk/difft-out"
OUT="$HOME/codex-ecosystem/state/gap-wave2-20260923/worktree-diff/git-diff-challenger-6"
mkdir -p "$OUT/reports"
> "$OUT/results.jsonl"
while IFS=$'\t' read -r status path; do
  old="$D/old/$path"
  new="$D/new/$path"
  report="$OUT/reports/$(echo "$path" | tr '/' '_').txt"
  set +e
  git diff --no-index --no-color -- "$old" "$new" > "$report" 2>"$OUT/reports/$(echo "$path" | tr '/' '_').stderr"
  exit_code=$?
  set -e
  bytes=$(wc -c < "$report")
  lines=$(wc -l < "$report")
  python3 -c "
import json,sys
print(json.dumps({'path': sys.argv[1], 'exit_code': int(sys.argv[2]), 'report_bytes': int(sys.argv[3]), 'report_lines': int(sys.argv[4])}))
" "$path" "$exit_code" "$bytes" "$lines" >> "$OUT/results.jsonl"
done < "$D/changed-files.txt"
echo "done"
