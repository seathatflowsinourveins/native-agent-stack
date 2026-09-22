#!/bin/bash
# Beads dead-worker lease-recovery probe (gap-resolution-20260922, layer workers,
# gap_index 6 of catalogs/foundation/decisions.json id=dependency-task-queue).
#
# Exercises `bd reclaim`'s documented stale-lease recovery path in a disposable
# scratch database outside any tracked repo. Corrects the triage's proposed
# command list to the flags bd 1.3.0 actually exposes (`bd --db` has no effect
# on `bd init`, which always creates .beads/embeddeddolt/ under the scratch
# dir's cwd; `bd create --json` prints a single object, not an array).
#
# IMPORTANT CONFOUND FOUND AND CORRECTED: an earlier pilot claimed with
# `bd update <id> --claim --assignee <name>` (matching the triage's proposed
# command). Per gastownhall/beads source (cmd/bd/update.go,
# internal/storage/issueops/execution.go), --claim grants the lease to the
# CLI actor (--actor / $BEADS_ACTOR / git user.name / $USER), not to whatever
# --assignee is also passed; a combined --claim --assignee invocation then
# overwrites the assignee via a second, ordinary field patch after the lease
# is already granted to the actor identity, and its JSON response omits the
# lease_expires_at/heartbeat_at fields a bare --claim reply includes. That
# pilot's own reclaim call 59s past its lease's true 5-minute TTL (confirmed
# via internal/storage/issueops/lease.go's `const DefaultLeaseTTL = 5 *
# time.Minute` at the exact pinned commit f45b249ce6b40ba62aecc03949e6371e
# 8f7c79d8 == bd 1.3.0) still returned count:0 - a real, reportable
# discrepancy for that exact invocation, but not evidence against
# `bd reclaim` itself, since --claim alone is bd's own documented "atomically
# claim" path. The corrected run below uses bare `--claim` (no extra
# --assignee), which does confirm lease_expires_at/heartbeat_at in its own
# reply, and is the invocation actually exercised for the receipt's positive
# result.
#
# The probe deliberately does NOT fake an expired lease by writing to the
# Dolt tables directly (`bd sql` also refuses raw SQL in embedded mode:
# "'bd sql' is not yet supported in embedded mode"): `bd reclaim --older-than
# 0s` immediately after claim is run first to document that a live lease is
# correctly left untouched (WHERE lease_expires_at < now), then the script
# waits past the real 5-minute TTL before re-running reclaim, so the observed
# transition is real elapsed-time dead-worker recovery, not a database edit
# that could diverge from the real code path.
#
# Usage: run.sh <scratch-dir> <wait-seconds>
set -euo pipefail
SCRATCH="${1:?scratch dir}"
WAIT_S="${2:-340}"
BD="${BD:-$HOME/.local/share/codex-ecosystem/bin/bd}"

rm -rf "$SCRATCH"
mkdir -p "$SCRATCH"
cd "$SCRATCH"
git init -q .
git config user.email "probe@example.com"
git config user.name "probe"

"$BD" init -q

CREATE_OUT=$("$BD" create "worker-crash-probe" --description "scratch issue for lease-recovery test" --json)
echo "$CREATE_OUT"
ISSUE_ID=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$CREATE_OUT")

echo "=== claim (bare --claim; actor comes from git user.name = probe) ==="
"$BD" update "$ISSUE_ID" --claim --json

echo "=== reclaim immediately after claim (expect no-op: lease not yet expired) ==="
"$BD" reclaim --older-than 0s --id "$ISSUE_ID" --json -v

echo "=== show after immediate reclaim attempt (expect still in_progress, lease_expires_at ~5m out) ==="
"$BD" show "$ISSUE_ID" --json

echo "=== waiting ${WAIT_S}s for the real 5-minute lease TTL to expire ==="
sleep "$WAIT_S"

echo "=== reclaim after wait (expect the stale lease reverted to ready/open) ==="
"$BD" reclaim --older-than 0s --id "$ISSUE_ID" --json -v

echo "=== show after reclaim (final state; expect status back to open/ready, assignee cleared) ==="
"$BD" show "$ISSUE_ID" --json
