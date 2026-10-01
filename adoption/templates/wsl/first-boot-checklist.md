# Stage-1 and first-boot checklist

Copy this list into the private run log, not into the checkout, and tick a step only when its proof in
[the recipe](../../platforms/linux-wsl2-new-distro.md) holds. The commands live in the recipe only; this list names the
pass condition each step must show. A step that shows anything else stops the run. W6 runs only after the W5 marker.
The ticked list and the transcript feed [the receipt example](stage1-receipt.example.json).

## Windows host (PowerShell)

- [ ] **W1** `Z:\WSL\downloads` exists and the transcript is open; WSL is 2.4.10 or later; the default (starred) distribution is recorded; `<Name>` is unregistered; `Z:\WSL\<Name>` does not exist; no Landscape user-data exists for `<Name>`; no `agent.yaml` exists, or its recorded top-level keys include neither `users` nor `write_files`; free space on `Z:` is recorded.
- [ ] **W2** The computed, Canonical-published and DistributionInfo.json sha256 are all `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`; no `throw`.
- [ ] **W3** `%USERPROFILE%\.cloud-init\<Name>.user-data` exists, starts with `#cloud-config`, names `<WSL_USER>` twice and contains no `${`.
- [ ] **W4** Install exit 0; `Distribution successfully installed`; `<Name>` is `Stopped` at version 2; the starred line is unchanged.
- [ ] **W5** First launch exit 0, without the prompt marker; `id -un` is `<WSL_USER>` and `id -u` is `1000`; `cloud-init status --long` prints `status: disabled` with `boot_status_code: disabled-by-marker-file`; `/var/lib/cloud/data/result.json` names `DataSourceWSL` with `"errors": []`; `/var/lib/cloud/data/status.json` shows the four stages finished without errors; `/etc/wsl.conf` names the user once; `/etc/cloud/cloud-init.disabled` exists; sudo is NOPASSWD; the starred line is unchanged.
- [ ] **W6** Only after the W5 marker: re-listed before `--unregister`; import exit 0; `cloud-init status` recorded; `visudo` `parsed OK`; after `--terminate`, `id -un` is `<WSL_USER>`; W5's checks pass, with `result.json` and `status.json` checked only if cloud-init ran on the import (otherwise their absence is recorded); `creation_path` is `B`.

## Inside the new distribution (as `<WSL_USER>`)

- [ ] **F1** `systemctl is-system-running --wait` prints `running`; no failed unit.
- [ ] **F2** `Linger` is `yes`.
- [ ] **F3** `/run/user/<uid>` is a directory and its `bus` a socket, both owned by `<WSL_USER>`; the user manager is `running`.
- [ ] **F4** apt exits 0; `jq`, `libatomic1` and `uidmap` print versions.
- [ ] **F5** `/etc/subuid` and `/etc/subgid` hold 65,536 ids for `<WSL_USER>`; whether `useradd` or `usermod` wrote them is recorded.
- [ ] **F6** `~/.bash_profile` is exactly the hand-off line.
- [ ] **F7** The clone's `HEAD` equals `origin` `main`; the commit is recorded.
- [ ] **F8** `ss` shows no listener on the four ports; the host file parses with the nine keys and is git-ignored.
- [ ] **F9** Stage 2 runs from this clone with `--profile <id>`; its own receipts cover it.
- [ ] **F10** The fragment profiles carry `<Name>` in their names; `type -P claude codex` prints two absolute paths, and the per-path `test -f` and `test -x` line prints `executable:` for both.
- [ ] **F11** In a login shell, after F9 and F10: when `test -x` finds `jcodemunch-mcp`, `claude mcp add` run from the clone's root prints `Added ...` and `claude mcp get jcodemunch` names the local scope and the command; when it does not, `not installed` is recorded, and a step not run is recorded as `skipped` with the reason. `jcodemunch_registration` holds the outcome.
