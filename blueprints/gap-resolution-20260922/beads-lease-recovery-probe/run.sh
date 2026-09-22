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
# IMPORTANT CONFOUND FOUND, AND ITS CAUSE CORRECTED IN A LATER FIX ROUND: an
# earlier pilot claimed with `bd update <id> --claim --assignee <name>`
# (matching the triage's proposed command). The lease-grant mechanism itself
# is NOT the cause: --claim does arm a lease for the CLI actor (--actor /
# $BEADS_ACTOR / git user.name / $USER). The actual cause, per
# gastownhall/beads source at the exact pinned commit
# f45b249ce6b40ba62aecc03949e6371e8f7c79d8 (== bd 1.3.0), is that the same
# call's --assignee value is then applied through the ordinary generic-update
# path, and ManageLeaseOnUpdate (internal/storage/issueops/update.go) deletes
# the issue's lease row (DeleteLeaseInTx) whenever a generic update changes
# who holds an in_progress claim. With the lease row gone, `bd reclaim`'s own
# query (ReclaimExpiredLeasesInTx, internal/storage/issueops/lease.go) is an
# inner join `FROM leases l JOIN issues i ... WHERE i.status = 'in_progress'
# AND l.lease_expires_at < ?`, which structurally cannot select an issue with
# no lease row, at any elapsed time -- not a transient miss at 0s
# grace/~59s past TTL, but a permanent exclusion from recovery for any issue
# claimed or reassigned this way. This is a real, permanent limit on bd's
# crash-recovery semantics, not merely a usage trap for this one invocation.
# The corrected run below uses bare `--claim` (no extra --assignee), which
# does confirm lease_expires_at/heartbeat_at in its own reply, keeps its
# lease row, and is the invocation actually exercised for the receipt's
# positive result.
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
