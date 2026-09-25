# NativeStack same-host recovery execution — 2026-09-24

Outcome: native restic 0.19.1 is signed and installed in an owned prefix; both public-reference and live ai-memory native backup chains passed isolated, encrypted **same-host** restore. This is not off-host disaster recovery. No live service was stopped, selected over, or restored in place. No password, archive body, memory page, or credential is copied into this workspace.

## Binary provenance

Official [restic 0.19.1 release](https://github.com/restic/restic/releases/tag/v0.19.1) is still latest stable; [official binary instructions](https://restic.readthedocs.io/en/stable/020_installation.html#official-binaries) publish fingerprint `CF8F18F2844575973F79D4E191A6868BD3F7A907`. `agent-recovery-restic-verify-corrected` recorded `GOODSIG` and `VALIDSIG` for that fingerprint on `SHA256SUMS.asc`, then verified archive SHA-256 `f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c`. `agent-recovery-restic-install` reported `restic 0.19.1 compiled with go1.26.4 on linux/amd64`. Binary path: `~/.local/share/codex-ecosystem/recovery/restic/0.19.1/restic`.

## Public-reference drill

`agent-recovery-public-drill` actual exit 0. Native `restic init`, `backup --files-from-verbatim` of the selected **22** public files, `snapshots`, `check --read-data` (2/2 packs, no errors), `restore --verify --overwrite never`, and `sha256sum --check` all passed. This pinned catalog's 22 current file bytes total **1,547,547**, not the older receipt's 160,642. Fresh private repository, password and restored tree are under `~/.local/share/codex-ecosystem/recovery/public-drill` (mode 0700 root, mode 0600 password). No retention or schedule was enabled.

## Live ai-memory drill

The parent-owned ai-memory 2.3.2 server at `127.0.0.1:49474` returned healthy status before and after. `agent-recovery-memory-backup` exit 0 obtained its native online archive of **49,538 bytes**; a private metadata-only archive check found 39 regular files, including 37 wiki files, one SQLite snapshot and one config, with no absolute, parent-traversal or link entries. Archive SHA-256 `cf403e8bf08e8f79c33bea6957c06c7317638edb8e4c089fc5b7dbf68110cad3`.

`agent-recovery-memory-restic` exit 0 encrypted that archive in a new repository, checked 2/2 packs with no errors, restored the archive to a new directory, and `cmp` proved byte equality. `agent-recovery-memory-restore` exit 0 ran original `ai-memory restore` in Bubblewrap with separate PID/network namespaces and **only** `/usr`, the exact application binary, the archive, and a new writable restore directory mounted. No `--force`, live store, or host home was mounted. `agent-recovery-memory-verify` exit 0 matched all 39 archived files to the isolated restored bytes; SQLite integrity `ok`, zero foreign-key violations, 56 tables. Restored SQLite SHA-256 `1bbdfe6a20901b07631354518de3c05654d3181eb320fa3221b7236386be69e5`. Live server remained healthy after.

All exact argv, stdout/stderr, hashes and actual exits reside in `work/receipts/agent-recovery-*`. Commands are the reviewed scripts `work/agent-recovery-{restic-verify,public-drill,memory-restic,memory-restore}.sh` and metadata-only Python verifiers. Private repository, password and restored state remain outside the catalog and this Windows workspace. To call this disaster recovery, the user still must choose an approved off-host destination and independent, recoverable key custody; then a real off-host restore must pass. The ai-memory online snapshot is SQLite-consistent but not proven globally atomic across DB/wiki/config under concurrent edits.

Retained failed attempts: `agent-recovery-restic-key-fingerprint` showed the correct key but GPG unexpectedly created a fresh empty `~/.gnupg` while reading it; subsequent verification used an explicit owned `gnupg` directory. `agent-recovery-restic-signature` exit 1 came from WSL command-line expansion of a shell variable in a one-liner (`mkdir /gnupg`), corrected by the reviewed script and full signature/hash checks. Neither failure was treated as success. No existing auth keyring was read or copied.
