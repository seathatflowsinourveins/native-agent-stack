#!/usr/bin/env bash
# promptfoo exec provider for the X9 round-2 comparison: a thin local integration. Contract (promptfoo 0.123.1,
# src/providers/scriptCompletion.ts): argv is this script's own args, then the prompt, the provider options JSON and the
# call context JSON; stdout (trimmed) is the output. Runs one headless Claude Code session in the arm's worktree, keeps
# the whole stream-json transcript, and prints summarize.py's compact JSON.
# usage (promptfooconfig.yaml): exec: bash run_arm.sh <arm>
set -u
arm=$1 prompt=$2
X=$(cd "$(dirname "$0")" && pwd)
S=$(dirname "$(dirname "$X")")
wt=$S/wt-x9-$arm
mkdir -p "$X/runs/$arm"
out=$X/runs/$arm/$(date -u +%Y%m%dT%H%M%SZ)-$$.jsonl
start=$(date +%s%3N)
(cd "$wt" && timeout 300 claude -p "$prompt" --output-format stream-json --verbose --max-turns 10 \
  < /dev/null > "$out" 2> "$out.err")
rc=$?
python3 "$X/summarize.py" "$arm" "$out" "$rc" "$(( $(date +%s%3N) - start ))"
