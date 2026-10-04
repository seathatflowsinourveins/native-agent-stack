#!/usr/bin/env bash
# Recompute prove.sh's forbidden-string list -- both the OLD (pre-fix, 12-character floor) and the NEW (fixed,
# no floor, plus the explicit `pwd` literal) versions -- from the real probe prompt and prove.sh's own
# CODEX_TASK literal (extracted from prove.sh itself, so this stays correct across prove.sh edits), and
# compare the OLD recomputation against a retained forbidden.txt by SHA-256. Never prints prompt/command
# content: only line counts and digests.
#
# Usage: verify_forbidden_list.sh <probe-prompt.txt> <prove.sh> [<retained-forbidden.txt-to-compare>]
set -u
PROMPT_FILE=${1:?usage: verify_forbidden_list.sh <probe-prompt.txt> <prove.sh> [<retained-forbidden.txt>]}
PROVE_SH=${2:?usage: verify_forbidden_list.sh <probe-prompt.txt> <prove.sh> [<retained-forbidden.txt>]}
RETAINED=${3:-}
PROMPT="$(cat "$PROMPT_FILE")"
CODEX_TASK="$(sed -n "/^CODEX_TASK=/,/\.'\$/p" "$PROVE_SH" | sed "1s/^CODEX_TASK='//" | sed '$s/.$//')"
[ -n "$CODEX_TASK" ] || { echo "FAIL could not extract CODEX_TASK from $PROVE_SH" >&2; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# OLD: prove.sh (pre-2026-09-26 fix) -- sentence-split, then an 8/12-char floor, no explicit `pwd`.
{ printf '%s\n' "$PROMPT" "$CODEX_TASK" | tr '.' '\n'; echo "git log --oneline -1"; } \
  | sed -E 's/^[[:space:]0-9.]*//; s/[[:space:]]+$//' | awk 'length($0) >= 12' | sort -u > "$TMP/old.txt"

# NEW: fixed prove.sh -- same sentence-split, no length floor, plus the explicit `pwd` literal.
{ printf '%s\n' "$PROMPT" "$CODEX_TASK" | tr '.' '\n'; echo "git log --oneline -1"; echo "pwd"; } \
  | sed -E 's/^[[:space:]0-9.]*//; s/[[:space:]]+$//' | awk 'NF' | sort -u > "$TMP/new.txt"

old_count=$(wc -l < "$TMP/old.txt"); new_count=$(wc -l < "$TMP/new.txt")
old_sha=$(sha256sum "$TMP/old.txt" | awk '{print $1}')
new_sha=$(sha256sum "$TMP/new.txt" | awk '{print $1}')
echo "OLD (pre-fix, 12-char floor): $old_count lines, sha256 $old_sha"
echo "NEW (fixed, no floor + pwd):  $new_count lines, sha256 $new_sha"
echo "NEW adds exactly: $((new_count - old_count)) line(s) relative to OLD"

if [ -n "$RETAINED" ]; then
  retained_sha=$(sha256sum "$RETAINED" | awk '{print $1}')
  retained_count=$(wc -l < "$RETAINED")
  echo "RETAINED file ($(basename "$RETAINED")): $retained_count lines, sha256 $retained_sha"
  if [ "$retained_sha" = "$old_sha" ]; then
    echo "RESULT: RETAINED == recomputed OLD (byte-identical) -- the 23:47Z run's forbidden.txt is exactly"
    echo "        reproduced from probe-prompt.txt + prove.sh's own CODEX_TASK text under the pre-fix pipeline."
  else
    echo "RESULT: RETAINED differs from recomputed OLD -- do not assume they match; investigate before citing"
    echo "        this run's forbidden.txt as reproduced by this pipeline."
  fi
fi
