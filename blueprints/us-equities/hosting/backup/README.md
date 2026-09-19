# Native local backup and restore acceptance

On 2026-09-19, upstream restic **0.19.1** backed up and restored **22 selected
public reference files, 160,642 bytes**. The native full-data check read **2/2
packs** and reported **“no errors were found”**. Independent byte comparison and
`sha256sum --check` both matched all 22 files. The [receipt](receipt.json) records
the exact native backup and restore summaries. This is a real encrypted local
backup/restore, with no model inference.

The source was commit `1d6c3d2f67aaef8e381193385360bb81b1b022d9`.
[selected-files.txt](selected-files.txt) names the explicit files;
[source.sha256](source.sha256) records their original bytes. Later repository
changes are not part of that snapshot. The restore summary's `total_files: 30`
includes **22 regular files and 8 directories**.

## Upstream release and commands

The [official release](https://github.com/restic/restic/releases/tag/v0.19.1),
published 2026-07-05, was still the latest stable release at acceptance.
The installed Linux amd64 archive matched its SHA-256 in upstream `SHA256SUMS`;
the detached signature verified against the official primary fingerprint
`CF8F18F2844575973F79D4E191A6868BD3F7A907`. The checksum and binary hash are in
the receipt. Release metadata, signature output, command arguments and full
native output remain in private host evidence.

For a fresh installation, follow the
[official binary verification procedure](https://restic.readthedocs.io/en/stable/020_installation.html#official-binaries)
using the pinned release and the fingerprint above. Do not replace a working
binary merely to rerun this acceptance. Native `restic version` returned:

```text
restic 0.19.1 compiled with go1.26.4 on linux/amd64
```

These are the native operation commands used, with host-private locations
represented by variables. Set `STACK_REPO` to the selected checkout,
`BACKUP_ROOT` to a **new private directory outside that checkout**, and
`RESTIC_BIN` to the verified executable. Keep the password file outside the
source selection and never commit it or print its contents. The host run used
a random password in a new file with mode 0600, inside a directory with mode
0700. The commands use Bash and abort on a failed step.

```bash
set -euo pipefail
: "${STACK_REPO:?set an absolute source checkout path}"
: "${BACKUP_ROOT:?set an absolute NEW private backup directory}"
: "${RESTIC_BIN:?set the verified restic executable path}"
umask 077
mkdir -m 700 -- "$BACKUP_ROOT"
export RESTIC_REPOSITORY="$BACKUP_ROOT/repository"
export RESTIC_PASSWORD_FILE="$BACKUP_ROOT/password"
export RESTIC_CACHE_DIR="$BACKUP_ROOT/cache"
openssl rand -base64 48 > "$RESTIC_PASSWORD_FILE"
chmod 600 "$RESTIC_PASSWORD_FILE"
cd "$STACK_REPO"
SELECTION="$STACK_REPO/blueprints/us-equities/hosting/backup/selected-files.txt"
mapfile -t SELECTED_FILES < "$SELECTION"
sha256sum -- "${SELECTED_FILES[@]}" > "$BACKUP_ROOT/source.sha256"

"$RESTIC_BIN" init --json
"$RESTIC_BIN" backup --files-from-verbatim "$SELECTION" \
  --host native-agent-stack-reference --tag public-reference --json \
  > "$BACKUP_ROOT/backup.jsonl"
"$RESTIC_BIN" snapshots --tag public-reference --json \
  > "$BACKUP_ROOT/snapshots.json"
SNAPSHOT_ID=$(jq -er 'select(length == 1) | .[0].id' "$BACKUP_ROOT/snapshots.json")
"$RESTIC_BIN" check --read-data
mkdir -m 700 -- "$BACKUP_ROOT/restored"
"$RESTIC_BIN" restore "$SNAPSHOT_ID" --target "$BACKUP_ROOT/restored" \
  --verify --overwrite never --json
cd "$BACKUP_ROOT/restored"
sha256sum --check "$BACKUP_ROOT/source.sha256"
```

The password-generation spelling above uses OpenSSL; the recorded host run
used Python's cryptographic random generator without exposing its output.
Backup, snapshot selection, integrity checking and restoration all used the
unmodified upstream restic executable. This recipe intentionally requires a
new destination; for an existing repository, reuse its existing password
through its native configuration instead of rerunning initialization.

Exact acceptance conclusions:

| Native operation | Result |
| --- | --- |
| `backup --files-from-verbatim … --json` | Exit 0; 22 new files; 160,642 input bytes |
| `snapshots --tag public-reference --json` | Exit 0; 1 snapshot |
| `check --read-data` | Exit 0; 1 snapshot; 2 packs; no errors |
| `restore SNAPSHOT --verify --overwrite never --json` | Exit 0; 160,642 bytes restored |
| `sha256sum --check` in the fresh restore | Exit 0; 22 `OK` lines |
| Independent full-byte and file-set comparison | 22/22 identical; no missing or extra regular files |

The [upstream repository check](https://restic.readthedocs.io/en/stable/045_working_with_repos.html#checking-integrity-and-consistency)
reads all pack data when `--read-data` is set. Restore used an explicit snapshot
ID and a new directory; see the
[native restore documentation](https://restic.readthedocs.io/en/stable/050_restore.html).
The original files were never restored over.

## Retention preview and optional user service

This native policy preview was executed successfully:

```bash
"$RESTIC_BIN" forget --tag public-reference --group-by host,paths,tags \
  --keep-last 7 --dry-run --json
```

Its result was **keep 1, remove 0**. No deletion or prune was executed.
`keep-last 7` counts snapshots per group; it does not promise seven days of
coverage. Review the
[upstream retention semantics](https://restic.readthedocs.io/en/stable/060_forget.html)
before changing policy. A dry run is not active retention enforcement.

[native-agent-reference-backup.service.example](native-agent-reference-backup.service.example)
is an optional **manual, oneshot user service** using upstream restic directly.
Its paths must be adapted to the actual checkout and private configuration.
The example's configuration file supplies `RESTIC_REPOSITORY`,
`RESTIC_PASSWORD_FILE` and `RESTIC_CACHE_DIR`; only the path to the password
belongs there. The referenced source list must contain reviewed public files.
The service definition was syntax-checked; it was **not installed or run**.
No timer or recurring automation was created or enabled.

## Remaining recovery boundaries

- Repository, restored copy and password reside on the same host. Losing that
  host or volume can lose all three. This acceptance does **not** close off-host
  backup, independent key escrow, disaster recovery or always-on hosting.
- The source contains public configuration examples and historical receipts.
  Active client configuration, authentication stores, prompts, transcripts,
  order journals and live databases are excluded.
- Live SQLite, Qdrant, Prometheus and Loki need their own application-consistent
  export or coordinated snapshot procedures followed by application restore
  acceptance. Copying active database files would not prove usable recovery.
- Backups have no enabled schedule, expiry policy or external failure alerts.
  Scheduled/remote operation requires an explicit destination and retention
  decision. Disk-full, corrupt-pack and interrupted-restore recovery were not
  induced here.
- Packed-byte reduction and encryption are storage properties. No token savings
  or provider cost reduction is claimed from this backup.
