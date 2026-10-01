# Stage-1 and first-boot checklist

Copy this list into the private run log, not into the checkout, and tick a step only when its proof in
[the recipe](../../platforms/linux-wsl2-new-distro.md) holds. The commands live in the recipe only; this list names the
pass condition each step must show. A step that shows anything else stops the run. W6 runs only after the W5 marker.
The ticked list and transcript feed the synthetic [receipt example](stage1-receipt.example.json). Tick a separate copy
for each image arm's throwaway rehearsal, through F3 and the R1 comparisons, then for the real run, which skips R1.
Both arms are symmetric and provisional, with no merit precedence; both new-host acceptance runs are unrun.

| Release | Selected image | Exact SHA-256 |
| --- | --- | --- |
| 26.04.1 trial | `ubuntu-26.04.1-wsl-amd64.wsl` | `48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104` |
| 24.04.5 fallback | `ubuntu-24.04.5-wsl-amd64.wsl` | `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e` |

## Rehearsals (both image arms, before the real run)

- [ ] **R1** Each provisional image arm ran on its own throwaway name and its own folder through F3, with P3's baseline and W5's second storage count, W5's `cloud-init schema --system`, W7's owner and F2's idle observation recorded in the receipt's `rehearsal` block; then that name alone was terminated and unregistered (a failed rehearsal exported first, with exit 0 and its SHA-256 and size recorded); the last `--list --verbose` no longer lists it and the starred line is unchanged. Both arms have the same preregistered first-boot/schema, systemd user from the second instance, WSL GPU visibility, uv-managed CPython 3.13 and Node 24.21.0 criteria recorded in `comparison_arms`; failures and skips stay explicit, with no automatic winner.

## Workstation distribution (sh), before stage 1

- [ ] **P1** `gpgv` exits 0 with `Good signature` by `843938DF228D22F7B3742BC0D94AA3F0EFE21092`, with no key import; both 26.04.1 and 24.04.5 signed `SHA256SUMS` lines carry the exact release hashes above.
- [ ] **P2** `cloud-init schema -c` prints `Valid schema` for the render of `<WSL_USER>` and exits 0; the workstation cloud-init version and render's SHA-256 are recorded for the selected image. A host schema check is not image qualification; W5 must record and validate the selected packaged version on path A.
- [ ] **P3** The `hv_storvsc` count without the registration line is recorded as the baseline; the newest error line, by its kernel time against `/proc/uptime`, is at least one hour old or absent (younger: errors are current, the run stops; microsoft/WSL#41482); `swapon --show` is recorded.

## Windows host (PowerShell)

- [ ] **W1** `Z:\WSL\downloads` exists and the transcript is open; WSL is 2.4.10 or later; the default (starred) distribution is recorded; `<Name>` is unregistered; `Z:\WSL\<Name>` does not exist; no Landscape user-data exists for `<Name>`; no `agent.yaml` exists, or its recorded top-level keys include neither `users` nor `write_files`; the `.wslconfig` read shows `instanceIdleTimeout` and `vmIdleTimeout` or their absence, recorded as `idle_keys`; free space on `Z:` is recorded.
- [ ] **W2** Explicit `<RELEASE>` is one of the two controlled arms; download URL, filename and catalog entry match that release. The actual whole-image, signed Canonical publication and pinned DistributionInfo.json SHA-256 all equal that release's exact hash above; actual file size recorded, with no inferred 26.04.1 size; no `throw`.
- [ ] **W3** `%USERPROFILE%\.cloud-init\<Name>.user-data` exists, starts with `#cloud-config`, names `<WSL_USER>` twice and contains no `${`; its SHA-256 equals P2's.
- [ ] **W4** The selected `ubuntu-<RELEASE>-wsl-amd64.wsl` installs with exit 0; `Distribution successfully installed`; `<Name>` is `Stopped` at version 2; the starred line is unchanged.
- [ ] **W5** First launch exit 0, without the prompt marker; `id -un` is `<WSL_USER>` and `id -u` is `1000`; selected-image `cloud-init --version` recorded; `cloud-init status --long` prints `status: disabled` with `boot_status_code: disabled-by-marker-file`; `/var/lib/cloud/data/result.json` names `DataSourceWSL` with `"errors": []`; `/var/lib/cloud/data/status.json` shows the four stages finished without errors; `cloud-init schema --system` prints `Valid schema user-data` and exits 0; `/etc/wsl.conf` names the user once; `/etc/cloud/cloud-init.disabled` exists; sudo is NOPASSWD; the starred line is unchanged. On both paths, the second storage count equals P3's baseline; a larger count is recorded with the new lines, a failed W5 counts as exposure to microsoft/WSL#41482, and nothing continues to stage 2 until that is decided.
- [ ] **W6** Only after the W5 marker: re-listed before `--unregister`; before `--unregister`, `<Name>` terminated and exported to `Z:\WSL\downloads\<Name>-failed.tar` with exit 0, and its SHA-256 and size recorded in `failed_attempt_export`; the same selected image imports with exit 0; `cloud-init status` recorded; `visudo` `parsed OK`; after `--terminate`, `id -un` is `<WSL_USER>`; W5's checks pass, with `result.json` and `status.json` checked only if cloud-init ran on the import (otherwise their absence is recorded) and `cloud-init schema --system` skipped; `creation_path` is `B`.
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
