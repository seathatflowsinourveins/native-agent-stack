# Stage-1 and first-boot checklist

Copy this list into the private run log, not into the checkout, and tick a step only when its proof in
[the recipe](../../platforms/linux-wsl2-new-distro.md) holds. The commands live in the recipe only; this list names the
pass condition each step must show. A step that shows anything else stops the run. W6 runs only after the W5 marker.
The ticked list and the transcript feed [the receipt example](stage1-receipt.example.json). Tick a copy twice: once for
the rehearsal on a throwaway name, through F3 and then R1, and once for the real run, which skips R1.

## Rehearsal (once, before the real run)

- [ ] **R1** The page ran on a throwaway name and its own folder through F3, with W5's `cloud-init schema --system`, W7's owner and F2's idle observation recorded in the receipt's `rehearsal` block; then that name alone was terminated and unregistered (a failed rehearsal exported first, with exit 0 and its SHA-256 and size recorded); the last `--list --verbose` no longer lists it and the starred line is unchanged.

## Workstation distribution (sh), before stage 1

- [ ] **P1** `gpgv` exits 0 with `Good signature` by `843938DF228D22F7B3742BC0D94AA3F0EFE21092`, with no key import; the signed `SHA256SUMS` line of the image carries the hash W2 pins.
- [ ] **P2** `cloud-init schema -c` prints `Valid schema` for the render of `<WSL_USER>` and exits 0; the cloud-init version and the render's SHA-256 are recorded.
- [ ] **P3** The `hv_storvsc` count without the registration line is `0` (microsoft/WSL#41482: any other count stops the run); `swapon --show` is recorded.

## Windows host (PowerShell)

- [ ] **W1** `Z:\WSL\downloads` exists and the transcript is open; WSL is 2.4.10 or later; the default (starred) distribution is recorded; `<Name>` is unregistered; `Z:\WSL\<Name>` does not exist; no Landscape user-data exists for `<Name>`; no `agent.yaml` exists, or its recorded top-level keys include neither `users` nor `write_files`; the `.wslconfig` read shows `instanceIdleTimeout` and `vmIdleTimeout` or their absence, recorded as `idle_keys`; free space on `Z:` is recorded.
- [ ] **W2** The computed, Canonical-published and DistributionInfo.json sha256 are all `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`; no `throw`.
- [ ] **W3** `%USERPROFILE%\.cloud-init\<Name>.user-data` exists, starts with `#cloud-config`, names `<WSL_USER>` twice and contains no `${`; its SHA-256 equals P2's.
- [ ] **W4** Install exit 0; `Distribution successfully installed`; `<Name>` is `Stopped` at version 2; the starred line is unchanged.
- [ ] **W5** First launch exit 0, without the prompt marker; `id -un` is `<WSL_USER>` and `id -u` is `1000`; `cloud-init status --long` prints `status: disabled` with `boot_status_code: disabled-by-marker-file`; `/var/lib/cloud/data/result.json` names `DataSourceWSL` with `"errors": []`; `/var/lib/cloud/data/status.json` shows the four stages finished without errors; `cloud-init schema --system` prints `Valid schema user-data` and exits 0; `/etc/wsl.conf` names the user once; `/etc/cloud/cloud-init.disabled` exists; sudo is NOPASSWD; the starred line is unchanged.
- [ ] **W6** Only after the W5 marker: re-listed before `--unregister`; before `--unregister`, `<Name>` terminated and exported to `Z:\WSL\downloads\<Name>-failed.tar` with exit 0, and its SHA-256 and size recorded in `failed_attempt_export`; import exit 0; `cloud-init status` recorded; `visudo` `parsed OK`; after `--terminate`, `id -un` is `<WSL_USER>`; W5's checks pass, with `result.json` and `status.json` checked only if cloud-init ran on the import (otherwise their absence is recorded) and `cloud-init schema --system` skipped; `creation_path` is `B`.
- [ ] **W7** Both paths: `<Name>` terminated once and absent from the running list, then relaunched with `id -un` printing `<WSL_USER>`; the file created from Windows under the user's home reads `1000:1000` and is deleted; `0:0` is recorded and stops every write from Windows into the distribution.

## Inside the new distribution (as `<WSL_USER>`)

- [ ] **F1** `systemctl is-system-running --wait` prints `running`; no failed unit.
- [ ] **F2** `Linger` is `yes`; with no client attached, `<Name>` is in every list of the two minutes of polls, or the time it left is recorded beside W1's idle keys.
- [ ] **F3** `/run/user/<uid>` is a directory and its `bus` a socket, both owned by `<WSL_USER>`; the user manager is `running`.
- [ ] **F4** apt exits 0; `jq`, `libatomic1` and `uidmap` print versions.
- [ ] **F5** `/etc/subuid` and `/etc/subgid` hold 65,536 ids for `<WSL_USER>`; whether `useradd` or `usermod` wrote them is recorded.
- [ ] **F6** `~/.bash_profile` is exactly the hand-off line.
- [ ] **F7** The clone's `HEAD` equals `origin` `main`; the commit is recorded.
- [ ] **F8** `ss` shows no listener on the four ports; the host file parses with the nine keys and is git-ignored.
- [ ] **F9** Stage 2 runs from this clone with `--profile <id>`; its own receipts cover it.
- [ ] **F10** The fragment profiles carry `<Name>` in their names; `type -P claude codex` prints two absolute paths, and the per-path `test -f` and `test -x` line prints `executable:` for both.
- [ ] **F11** In a login shell, after F9 and F10: when `test -x` finds `jcodemunch-mcp`, `claude mcp add` run from the clone's root prints `Added ...` and `claude mcp get jcodemunch` names the local scope and the command; when it does not, `not installed` is recorded, and a step not run is recorded as `skipped` with the reason. `jcodemunch_registration` holds the outcome.
