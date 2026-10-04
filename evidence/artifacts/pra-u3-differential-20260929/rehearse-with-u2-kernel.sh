#!/usr/bin/env bash
# PR-A U3 repair round: a scratch rehearsal tree for the Codex call ledger (binding correction 1), which needs PR-A U2's kernel
# export callLedger. It extracts the U3 branch at REV (tools/skill-usage, examples/claude-native/workflows, tests,
# adoption/skills) with `git archive` into DEST and replaces examples/claude-native/workflows/child-usage.mjs with PR-A U2's copy
# at U2_REV. No ref, worktree or merge is made. DEST gets a `.git` file, as a checkout has, so the ledger's refusal of a path
# inside the checkout itself holds there too. The tree is U3's Python with U2's kernel only, without U3's own kernel changes
# (the rtk replay agent and D7), which the ledger does not read.
#
# Usage: bash rehearse-with-u2-kernel.sh REPO REV DEST
#   then, in DEST: python3 -B -m unittest -v tests.test_skill_usage.CodexCallLedger
set -euo pipefail
repo=$1 rev=$2 dest=$3
U2_REV=b2dd1eb78bd503c87a5e83811fed2894e153f19b  # claude/pra-u2-kernel-measures-2d-20260929, read 2026-09-29
rm -rf "$dest"
mkdir -p "$dest"
git -C "$repo" archive "$rev" tools/skill-usage examples/claude-native/workflows tests adoption/skills | tar -x -C "$dest"
git -C "$repo" show "$U2_REV:examples/claude-native/workflows/child-usage.mjs" > "$dest/examples/claude-native/workflows/child-usage.mjs"
printf 'gitdir: rehearsal-stand-in\n' > "$dest/.git"
echo "rehearsal rev=$(git -C "$repo" rev-parse --short=8 "$rev") kernel=${U2_REV:0:8}" \
     "kernel_sha256=$(sha256sum "$dest/examples/claude-native/workflows/child-usage.mjs" | cut -c1-64)"
