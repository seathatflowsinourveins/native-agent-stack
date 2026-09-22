#!/usr/bin/env bash
# Runs the pinned difft 0.71.0 ($HOME/.local/share/codex-ecosystem/bin/difft,
# a guarded launcher for $HOME/.local/share/codex-ecosystem/tools/difftastic-0.71.0/difft)
# over every file changed in a real multi-file commit range of this repository, one
# pair at a time. Requires old/<path> and new/<path> to already hold the pre- and
# post-image of each path in changed-files.txt (extracted with `git show <rev>:<path>`
# from the chosen commit range; here parent 231077d..bdd04ca of
# native-agent-stack-token-practice-review, 20 files changed).
#
# Executed once for evidence/artifacts/gap-resolution-20260922/git-github-automation/
# difftastic-larger-fixture.json; not re-run to fish for a different result.
set -u
cd "$(dirname "$0")/../../../.." 2>/dev/null || true
cd $HOME/codex-ecosystem/state/gap-resolution-20260922/worktrunk/difft-out
OUT=results.jsonl
> "$OUT"
while IFS=$'\t' read -r status path; do
  old_f="old/$path"
  new_f="new/$path"
  out=$(difft --display=inline --color=never "$old_f" "$new_f" 2>err.tmp)
  code=$?
  outfile="reports/$(echo "$path" | tr '/' '__').txt"
  mkdir -p reports
  printf '%s' "$out" > "$outfile"
  out_sha=$(sha256sum "$outfile" | cut -d' ' -f1)
  out_bytes=$(wc -c < "$outfile")
  # did difft actually recognize/parse the file, rather than emit a fallback notice?
  parsed_ok=true
  if echo "$out" | grep -qi "failed to parse\|could not find a parser\|panicked"; then
    parsed_ok=false
  fi
  python3 - "$path" "$code" "$out_bytes" "$out_sha" "$parsed_ok" <<'PYEOF' >> "$OUT"
import json, sys
path, code, out_bytes, out_sha, parsed_ok = sys.argv[1:6]
print(json.dumps({"path": path, "exit_code": int(code), "output_bytes": int(out_bytes), "output_sha256": out_sha, "reported_change": int(out_bytes) > 0, "parsed_ok": parsed_ok == "true"}))
PYEOF
done < changed-files.txt
