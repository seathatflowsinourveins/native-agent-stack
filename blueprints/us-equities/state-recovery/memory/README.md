# Native ai-memory state recovery

On 2026-09-19, the live ai-memory **2.3.1** server produced its native backup.
The archive passed an isolated native restore, was encrypted into a new local
restic repository, and passed another isolated native restore **from the
restic-recovered archive**. The live memory service stayed running throughout.
The [sanitized receipt](receipt.json) records the native commands and counts.

| Check | Observed result |
| --- | --- |
| `ai-memory backup --to …` | Exit 0; 3,202,145-byte archive |
| Backup contents | 324 files: 322 wiki files, one SQLite snapshot, one service configuration |
| `ai-memory restore --data-dir NEW --from …` in a fresh namespace | Exit 0; 64 ms |
| Restored original files | All 324 files byte-identical to the archive |
| SQLite `PRAGMA integrity_check` | `ok` |
| SQLite `PRAGMA foreign_key_check` | Zero violations |
| Logical data | All 56 table counts identical; one workspace, one project, 38 page-version rows, 19 sessions, 5,710 observations |
| FTS read query `research OR telemetry` | 184 observation matches before and after restore |
| `restic check --read-data` | Exit 0; 2/2 packs; no errors |
| Restic archive restoration | One file, 3,202,145 bytes, byte-identical |
| Native app restore from the recovered archive | Exit 0; SQLite bytes, integrity, all table counts and FTS results match |
| Live `ai-memory status` afterward | Exit 0 |

The archive SHA-256 is
`67a8973c66c4d3f6e7a327bbf6e85438214d39d071471662a826334b9c768766`.
The archives, database, wiki contents, configuration and passwords remain
private. No account authentication store was included. No archived prose or
credentials are published in this repository.

## Why these upstream operations

The native [backup command](https://github.com/akitaonrails/ai-memory/blob/v2.3.1/crates/ai-memory-cli/src/commands/backup.rs)
streams the server's `/admin/backup` response. The
[server handler](https://github.com/akitaonrails/ai-memory/blob/v2.3.1/crates/ai-memory-mcp/src/admin.rs#L815)
uses its SQLite online-backup operation before archiving the snapshot, wiki and
configuration. This avoids a raw copy of an active WAL database.

The native [restore command](https://github.com/akitaonrails/ai-memory/blob/v2.3.1/crates/ai-memory-cli/src/commands/restore.rs)
rejects unsafe archive paths and opens the restored store, including migrations.
Its process guard refuses restoration while another ai-memory process is
visible, even with a different data directory. The acceptance used existing
**bubblewrap 0.9.0** to provide separate PID, network and other namespaces, a
fresh `/proc`, a read-only host filesystem, and exactly one writable restore
directory. No process guard was disabled, and no live service was stopped.
Bubblewrap supplies isolation primitives; the actual boundary comes from the
[command arguments](https://github.com/containers/bubblewrap/blob/v0.9.0/README.md).

## Reproduce with native commands

Use the existing pinned `ai-memory`, `restic` and distribution `bwrap` binaries.
Set `MEMORY_BIN`, `RESTIC_BIN` and `BWRAP_BIN` to their absolute executable paths.
Set `RECOVERY_ROOT` to a new private directory outside client homes and public
checkouts. The native memory client must already reach the intended local
server through its normal configuration; do not copy client account stores.

```bash
set -euo pipefail
: "${MEMORY_BIN:?set the installed ai-memory executable}"
: "${RESTIC_BIN:?set the installed restic executable}"
: "${BWRAP_BIN:?set the installed bubblewrap executable}"
: "${RECOVERY_ROOT:?set an absolute NEW private directory}"
umask 077
mkdir -m 700 -- "$RECOVERY_ROOT"
"$MEMORY_BIN" backup --to "$RECOVERY_ROOT/native-memory-backup.tar.gz"
chmod 600 "$RECOVERY_ROOT/native-memory-backup.tar.gz"
```

Before restoration, inspect archive entry metadata privately. This acceptance
checked that every entry was a directory or regular file beneath `wiki/`, the
single `db/memory.sqlite` file, or `config.toml`; it rejected absolute paths,
parent traversal and links. Native restoration also enforces its upstream
archive checks. Configuration may contain a service credential and stays private.

Use restic's normal password-file mechanism. The actual host run generated a
random password without printing it, using Python's cryptographic random
generator and exclusive creation with mode 0600. The equivalent shell recipe
below uses OpenSSL, within the new private directory:

```bash
export RESTIC_REPOSITORY="$RECOVERY_ROOT/encrypted-repository"
export RESTIC_PASSWORD_FILE="$RECOVERY_ROOT/restic-password"
export RESTIC_CACHE_DIR="$RECOVERY_ROOT/restic-cache"
openssl rand -base64 48 > "$RESTIC_PASSWORD_FILE"
chmod 600 "$RESTIC_PASSWORD_FILE"
"$RESTIC_BIN" init --json
cd "$RECOVERY_ROOT"
"$RESTIC_BIN" backup --host native-agent-stack-state --tag ai-memory-state \
  --json native-memory-backup.tar.gz > restic-backup.jsonl
"$RESTIC_BIN" snapshots --tag ai-memory-state --json > restic-snapshots.json
SNAPSHOT_ID=$(jq -er 'select(length == 1) | .[0].id' restic-snapshots.json)
"$RESTIC_BIN" check --read-data
mkdir -m 700 -- "$RECOVERY_ROOT/restic-restored"
"$RESTIC_BIN" restore "$SNAPSHOT_ID" --target "$RECOVERY_ROOT/restic-restored" \
  --verify --overwrite never --json
cmp -- "$RECOVERY_ROOT/native-memory-backup.tar.gz" \
  "$RECOVERY_ROOT/restic-restored/native-memory-backup.tar.gz"
sha256sum -- "$RECOVERY_ROOT/restic-restored/native-memory-backup.tar.gz"
```

Restic **0.19.1** was already installed with verified upstream release signature
and checksum; see the [earlier installation evidence](../../hosting/backup/README.md).
Its [full repository check](https://restic.readthedocs.io/en/stable/045_working_with_repos.html#checking-integrity-and-consistency)
and [restore operation](https://restic.readthedocs.io/en/stable/050_restore.html)
were run against this new repository, not replayed from the earlier receipt.

Finally, restore the recovered archive with the original upstream application:

```bash
RESTORE_SANDBOX="$RECOVERY_ROOT/isolated-after-restic"
mkdir -m 700 -- "$RESTORE_SANDBOX"
env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=C.UTF-8 \
  AI_MEMORY_DATA_DIR="$RESTORE_SANDBOX/data" \
  "$BWRAP_BIN" --unshare-all --die-with-parent --new-session --cap-drop ALL \
  --ro-bind / / --proc /proc --dev /dev --tmpfs /tmp \
  --bind "$RESTORE_SANDBOX" "$RESTORE_SANDBOX" --chdir "$RESTORE_SANDBOX" \
  "$MEMORY_BIN" restore --data-dir "$RESTORE_SANDBOX/data" \
  --from "$RECOVERY_ROOT/restic-restored/native-memory-backup.tar.gz"
```

This command intentionally has no `--force`. It writes only beneath the newly
created restore directory and cannot reach the live server over the network.
If the host cannot provide unprivileged namespaces, retain that failure; do
not replace this command with a restore onto live state.

The acceptance then opened both the archived and restored SQLite files in
read-only URI mode using Python's standard `sqlite3` module. It compared schema
digests, every table count, exact database bytes, the integrity/foreign-key
checks above, and FTS match counts. All 323 non-database archive files also
matched byte-for-byte. These comparisons return only counts and status, never
memory bodies or service credentials.

## Limits retained

- This proves native application restore plus encrypted **same-host** recovery.
  Independent storage, secure password escrow, off-host failure recovery,
  automatic scheduling and retention enforcement remain unconfigured.
- The SQLite snapshot is consistent. The server archives wiki/config afterward
  without a documented global write lock; this is not an atomic cross-file
  DB/wiki snapshot under arbitrary concurrent edits. Compare application-level
  consistency before replacing live data in a future disaster recovery.
- Native backup includes wiki, SQLite and service configuration. It excludes
  `raw/`, model caches, logs and external native session transcripts. Do not
  describe it as complete portable-ledger or account recovery.
- Counts belong to the recorded snapshot, not the continually changing live
  service. The 38 `pages` rows include historical page versions, not 38 current
  durable pages.
- Restored application storage and FTS were checked locally. A replacement
  ai-memory HTTP/MCP server was not launched or switched into the live clients.
- No model invocation, broker action, destructive retention command or token
  savings claim is part of this recovery check.
