#!/usr/bin/env bash
# Run RTK 0.49.0 filter/recall on a second, distinct artifact pair: a fresh
# scratch git repo (not the scripts/native_token_ci.py rtk_fixture's
# git-fixture repo, not agent-lab) and a distinct command (`git diff --stat`
# instead of `git log -2`), including the error path (missing ref) through
# `rtk proxy`, with an isolated RTK_DB_PATH ledger.
set -euo pipefail

SCRATCH=/home/example/codex-ecosystem/state/gap-resolution-20260922/token-observation
FIX="$SCRATCH/rtk-second-fixture-repo"
rm -rf "$FIX"
mkdir -p "$FIX"
cd "$FIX"
git init --quiet
git config user.name "Gap Resolution Second Fixture"
git config user.email "gap-second@example.invalid"
printf 'module Alpha\nversion 0\n' > alpha.txt
git add alpha.txt
git commit --quiet -m SECOND_FIXTURE_ALPHA_BASELINE
printf 'module Alpha\nversion 1\nmodule Beta\nversion 0\n' > alpha.txt
printf 'auxiliary marker file\n' > beta.txt
git add alpha.txt beta.txt
git commit --quiet -m SECOND_FIXTURE_BETA_FOLLOWUP

export RTK_DB_PATH="$SCRATCH/rtk-second-fixture.db"
rm -f "$RTK_DB_PATH"

rtk --version
before=$(rtk gain --format json)
baseline=$(git diff --stat HEAD~1 HEAD)
compact=$(rtk git diff --stat HEAD~1 HEAD)
recovered=$(rtk proxy git diff --stat HEAD~1 HEAD)
if [ "$baseline" = "$recovered" ]; then echo "PROXY_EXACT_MATCH=true"; else echo "PROXY_EXACT_MATCH=false"; fi
set +e
rtk proxy git rev-parse --verify refs/heads/second-fixture-missing-ref
echo "ERROR_EXIT_CODE=$?"
set -e
after=$(rtk gain --format json)
echo "BEFORE: $before"
echo "AFTER: $after"
