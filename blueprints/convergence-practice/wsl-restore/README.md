# Native WSL backup and recovery qualification

VelaNext recovered both frozen synthetic snapshots with native restic **0.19.1**.
The final two `restore --verify` commands and `check --read-data` returned zero.
Independent comparison passed every fixture path, type, byte hash and POSIX mode,
including the original fixture directory mode. The [receipt](receipt.json)
links the complete source, installation, failed attempts and accepted evidence.

The fixture contains nested Unicode names, a 1 MiB binary, an empty file and
empty directory, an executable-mode file that is never executed, and a
changed/deleted/added-file transition between two snapshots. It contains no
personal files, native client state, histories, accounts or existing backup data.

The [source review](source-review.json) checked the current official releases and
exact source/license files for restic, gitleaks and Worktrunk. Only restic was
needed here. Its owned Linux binary passed the release asset hash, signed
`SHA256SUMS`, pinned upstream PGP fingerprint and native version check; the
[installation record](installation.json) retains all nine commands. No global
PATH, runtime settings, service or existing installation changed. gitleaks and
Worktrunk remain unqualified on this WSL host after the bounded executable lookup.

## Retained failures and recovery

The first attempt passed both backups, the full repository check and an incorrect
password rejection with exit 12. Its corruption setup then failed because restic
pack files are read-only and copying preserved that mode. The correction enables
owner-write **only on the selected copied pack**. The original repository remains
byte-identical. This failure and its exact runner/plan remain in [attempt 1](attempt-1/receipt.json).

The next attempt confirmed wrong-password exit 12 with no restored files and
corrupted-copy check exit 1. Its direct-subtree restore returned zero, but the
strict oracle rejected the new target directory's mode 0700 instead of the
fixture's original 0750. [Attempt 2](attempt-2/receipt.json) remains failed.

The [frozen correction](recovery-plan.json) reused those exact snapshots and the
same unchanged oracle. It restored their parent subtree into fresh targets, then
checked that each target contains only `fixture` and that the fixture—including
its root directory mode—matches completely. [Both restores passed](accepted/receipt.json)
through another fresh SSH connection. No third backup was needed. The healthy
repository's complete file hash manifest remained unchanged after recovery.

## Scope and replay

This qualifies synthetic **same-host WSL recovery with the retained local key**.
It does not qualify offhost storage, disaster recovery, lost-key recovery,
reboots/power loss, exFAT/NTFS, ACLs, extended attributes, sparse files, hardlinks,
symlinks or native client credential recovery. Future same-host key availability
remains unknown. No token, storage-efficiency or performance savings are claimed.

Use an explicitly selected, new private task directory and an available supported
Python interpreter. The Linux project-local installer refuses an existing target:

```sh
python3 install.py --destination "$NEW_PRIVATE_TOOL_DIR"
```

The current `run.py` and `plan.json` incorporate both observed corrections for a
future replay. They were not run as a third complete trial; each actual attempt's
exact executed sources remain under `attempt-1/` and `attempt-2/`. Keep
`fixture.py`, `corruption.py`, `run.py` and `plan.json` together in a selected
private directory on WSL. First run:

```sh
python3 run.py prepare --run-dir "$NEW_PRIVATE_RUN_DIR" \
  --restic "$NEW_PRIVATE_TOOL_DIR/restic"
```

End that SSH invocation. From a fresh connection, using the same selected private
run and key:

```sh
python3 run.py recover --run-dir "$NEW_PRIVATE_RUN_DIR" \
  --restic "$NEW_PRIVATE_TOOL_DIR/restic"
```

`recover.py` and `recovery-plan.json` reproduce the separately frozen correction
against the recorded preparation schema. They retain prior failure evidence and
require fresh recovery targets. Every native operation has a 120-second deadline,
explicit repository/password-file arguments, a minimal environment and no cache.
Passwords are generated locally as regular mode-0600 files outside Git and are
never returned. Preserve them privately while the owned encrypted fixture is
needed; deleting this task directory removes only its isolated installation and
synthetic recovery state. No pruning or existing backup lifecycle is involved.

Offline tests check corrupted bytes, missing/extra paths, directory and file
modes, symlink rejection, the frozen transition and copied-pack isolation:

```sh
python3 -m unittest tests.test_wsl_restore -v
```
