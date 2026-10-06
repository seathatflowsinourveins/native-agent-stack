# Phase 1 repository transfer to NativeStack2604

These are host steps for the co-op after the P1 repository checks pass. This PR
performs no clone, privileged operation or mount. The three destinations are new;
an existing checkout or conflicting vault mount stops the operation.

The approved full-resolution plan, SHA256
775119dc6840552def19142a10e2730b489b6365c346e6f9fb6f5db5f2572ba2,
assigns these repositories and the Librarium bind in Phase 1 step 6.
Librarium is the distinct repository below, not librarium-course. Its existing
workspace and Windows vault paths stay the same. This public runbook uses the
example account below; the requested PR host-apply section carries the exact
operator-specific fstab line. Substitute that line and account guard together.

| Repository | New destination | Source audited on 2026-10-06 |
| --- | --- | --- |
| seathatflowsinourveins/nas-ops | $HOME/code/nas-ops | main 1fc22572b0f8aadbe976fae8fe12ec811103e456 |
| seathatflowsinourveins/librarium | $HOME/projects/librarium | main 7c6215ebdcb47ee6a73af692868b9ff014db3c8c |
| seathatflowsinourveins/native-agent-stack | $HOME/code/native-agent-stack-live | ecfa112764c664d35377dd66b8cfcb67e5a94d60 is the source baseline; record origin/main actually cloned |

Each clone tracks main. Record the returned HEAD instead of assuming an audited
remote has not advanced. No previous checkout, key or native sign-in is copied.

## Apply the new clones

Run every apply/read-back block in the SAME ordinary NativeStack2604 user shell
with set -euo pipefail. Before a later rollback, restore the recorded backup path
and vault variables from the private receipt and enable that same error policy.
Retain the dated backup path and
created-clone list in the co-op's private receipt. Commands stop on the first
failure; a partial clone is preserved for review rather than overwritten.

~~~bash
set -euo pipefail
p1_repo_backup="$HOME/.local/state/native-agent-stack/backups/p1-repositories-$(rtk proxy date -u +%Y%m%dT%H%M%SZ)"
rtk proxy mkdir -m 0700 -p -- "$p1_repo_backup"
rtk proxy mkdir -p -- "$HOME/code" "$HOME/projects"

test ! -e "$HOME/code/nas-ops"
test ! -L "$HOME/code/nas-ops"
rtk proxy nice -n 19 git clone --branch main -- \
  https://github.com/seathatflowsinourveins/nas-ops.git "$HOME/code/nas-ops"
printf '%s\n' nas-ops >> "$p1_repo_backup/created-clones"

test ! -e "$HOME/projects/librarium"
test ! -L "$HOME/projects/librarium"
rtk proxy nice -n 19 git clone --branch main -- \
  https://github.com/seathatflowsinourveins/librarium.git "$HOME/projects/librarium"
printf '%s\n' librarium >> "$p1_repo_backup/created-clones"

test ! -e "$HOME/code/native-agent-stack-live"
test ! -L "$HOME/code/native-agent-stack-live"
rtk proxy nice -n 19 git clone --branch main -- \
  https://github.com/seathatflowsinourveins/native-agent-stack.git "$HOME/code/native-agent-stack-live"
printf '%s\n' native-agent-stack-live >> "$p1_repo_backup/created-clones"
~~~

For **each** destination, substitute its path in this native read-back. Require
main, equal local/origin heads and clean status before mounting the vault; retain
the observed commit and command exits.

~~~bash
p1_clone="$HOME/code/nas-ops"  # repeat for the other two destinations
test "$(rtk proxy git -C "$p1_clone" symbolic-ref --short HEAD)" = main
rtk proxy git -C "$p1_clone" rev-parse HEAD
rtk proxy git -C "$p1_clone" rev-parse origin/main
test "$(rtk proxy git -C "$p1_clone" rev-parse HEAD)" = "$(rtk proxy git -C "$p1_clone" rev-parse origin/main)"
test -z "$(rtk proxy git -C "$p1_clone" status --porcelain=v1)"
~~~

## Apply the Librarium vault bind

The canonical Librarium instructions bind its existing Windows-native Obsidian
vault. The exact fstab line requested for this host is:

~~~fstab
/mnt/c/Users/example/librarium-vault /home/example/projects/librarium/vault none bind,nofail 0 0
~~~

The following host step needs sudo; this lane does not execute it. The target
must be unmounted, and /etc/fstab must have no existing entry at that
exact mountpoint. Preserve the old fstab before adding the one reviewed row.
No vault contents are copied or removed.

~~~bash
p1_vault_source=/mnt/c/Users/example/librarium-vault
p1_vault_target="$HOME/projects/librarium/vault"
p1_fstab_line='/mnt/c/Users/example/librarium-vault /home/example/projects/librarium/vault none bind,nofail 0 0'

test "$HOME" = /home/example
test -d "$p1_vault_source"
test ! -L /etc/fstab
test ! -L "$p1_vault_target"
if rtk proxy findmnt --mountpoint "$p1_vault_target" --noheadings --output TARGET >/dev/null; then exit 1; fi
if rtk proxy findmnt --fstab --mountpoint "$p1_vault_target" --noheadings --output TARGET >/dev/null; then exit 1; fi
if test -e "$p1_vault_target"; then
  test -d "$p1_vault_target"
  test ! -e "$p1_repo_backup/librarium.vault.before"
  rtk proxy mv -- "$p1_vault_target" "$p1_repo_backup/librarium.vault.before"
fi
rtk proxy mkdir -p -- "$p1_vault_target"

rtk proxy sudo cp -a -- /etc/fstab "$p1_repo_backup/fstab.before"
printf '\n%s\n' "$p1_fstab_line" | rtk proxy sudo tee -a /etc/fstab >/dev/null
rtk proxy sha256sum /etc/fstab > "$p1_repo_backup/fstab.applied.sha256"
rtk proxy sudo systemctl daemon-reload
rtk proxy sudo mount "$p1_vault_target"
rtk proxy git -C "$HOME/projects/librarium" config --local core.fileMode false
~~~

The canonical explicit host paths appear only where the requested bind requires
them; retain machine read-backs privately. For verification, use the exact
mountpoint rather than --target, which can return a containing filesystem.

~~~bash
rtk proxy findmnt --verify --verbose --target "$p1_vault_target"
rtk proxy findmnt --fstab --mountpoint "$p1_vault_target" --noheadings --output SOURCE,TARGET,FSTYPE,OPTIONS
rtk proxy findmnt --mountpoint "$p1_vault_target" --noheadings --output SOURCE,TARGET,FSTYPE,OPTIONS
test "$(rtk proxy stat -c '%d:%i' "$p1_vault_source")" = "$(rtk proxy stat -c '%d:%i' "$p1_vault_target")"
test "$(rtk proxy git -C "$HOME/projects/librarium" config --local --get core.fileMode)" = false
~~~

Git status after binding may reflect legitimate Windows-vault content; never
discard it to make a read-back clean. The clean-clone check above precedes the
bind.

## Rollback

Unmount before moving the new Librarium checkout. A busy mount stops rollback;
do not use a forced or lazy unmount. Restore the saved fstab only while its
post-apply checksum still matches. If another operator changed fstab, preserve
those edits and remove only the exact owned row through sudoedit.

~~~bash
if rtk proxy findmnt --mountpoint "$p1_vault_target" --noheadings --output TARGET >/dev/null; then
  rtk proxy sudo umount -- "$p1_vault_target"
fi
if test -f "$p1_repo_backup/fstab.before"; then
  if test -f "$p1_repo_backup/fstab.applied.sha256" &&
     rtk proxy sudo sha256sum --check --status "$p1_repo_backup/fstab.applied.sha256"; then
    rtk proxy sudo cp -a -- "$p1_repo_backup/fstab.before" /etc/fstab
  else
    # A concurrent edit or interrupted append: inspect/remove only the owned row.
    rtk proxy sudoedit /etc/fstab
  fi
  rtk proxy sudo systemctl daemon-reload
fi
if rtk proxy findmnt --mountpoint "$p1_vault_target" --noheadings --output TARGET >/dev/null; then exit 1; fi
if rtk proxy findmnt --fstab --mountpoint "$p1_vault_target" --noheadings --output TARGET >/dev/null; then exit 1; fi
if test -d "$p1_repo_backup/librarium.vault.before"; then
  if test -e "$p1_vault_target"; then rtk proxy rmdir -- "$p1_vault_target"; fi
  rtk proxy mv -- "$p1_repo_backup/librarium.vault.before" "$p1_vault_target"
fi

# Move only destinations recorded as newly created by this apply; preserve edits.
if rtk proxy grep -qx nas-ops "$p1_repo_backup/created-clones"; then
  if test -e "$HOME/code/nas-ops"; then
    test ! -e "$p1_repo_backup/nas-ops"
    rtk proxy mv -- "$HOME/code/nas-ops" "$p1_repo_backup/nas-ops"
  fi
fi
if rtk proxy grep -qx librarium "$p1_repo_backup/created-clones"; then
  if test -e "$HOME/projects/librarium"; then
    test ! -e "$p1_repo_backup/librarium"
    rtk proxy mv -- "$HOME/projects/librarium" "$p1_repo_backup/librarium"
  fi
fi
if rtk proxy grep -qx native-agent-stack-live "$p1_repo_backup/created-clones"; then
  if test -e "$HOME/code/native-agent-stack-live"; then
    test ! -e "$p1_repo_backup/native-agent-stack-live"
    rtk proxy mv -- "$HOME/code/native-agent-stack-live" "$p1_repo_backup/native-agent-stack-live"
  fi
fi
~~~

The Windows source vault remains in place. Renaming the fresh checkouts also
preserves their repository-local configuration and any later edits.

For clone-only rollback before any bind step, use just the corresponding
created-clones guard and move above; no fstab operation is needed. A failed
partial clone is retained at its new destination for review, never replaced.

## Pinned sources

- [Librarium CLAUDE.md at 7c6215eb, lines 94–108](https://github.com/seathatflowsinourveins/librarium/blob/7c6215ebdcb47ee6a73af692868b9ff014db3c8c/CLAUDE.md#L94):
  original workspace, NTFS vault, bind and repository-local fileMode setting.
- [Retirement decision at ecfa11276, lines 51–53](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecfa112764c664d35377dd66b8cfcb67e5a94d60/docs/decisions/2026-09-29-retire-polaris.md#L51):
  preserve the migrated workspace path.
- [Git v2.53.0 clone](https://github.com/git/git/blob/v2.53.0/Documentation/git-clone.adoc):
  native fresh clone and main tracking; --revision is deliberately not used.
- [util-linux v2.41.3 mount](https://github.com/util-linux/util-linux/blob/v2.41.3/sys-utils/mount.8.adoc)
  and [findmnt](https://github.com/util-linux/util-linux/blob/v2.41.3/misc-utils/findmnt.8.adoc):
  bind syntax, exact mountpoint filtering and fstab verification.
- [systemd v259.5 fstab generator](https://github.com/systemd/systemd/blob/v259.5/man/systemd-fstab-generator.xml):
  fstab translates to native units at boot and system-manager reload.
