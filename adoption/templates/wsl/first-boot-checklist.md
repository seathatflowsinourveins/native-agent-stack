# Stage-1 and first-boot checklist

Copy this list into the private run log, not into the checkout, and tick a step only when its proof in
[the recipe](../../platforms/linux-wsl2-new-distro.md) holds. The recipe gives every command; this list repeats the five
baseline and paired observations so each has its own record. A step that shows anything else stops the run. W6 runs only after the W5 marker.
The ticked list and transcript feed the synthetic [receipt example](stage1-receipt.example.json). Tick a separate copy
for each image arm's throwaway rehearsal, through F3 and the R1 comparisons, then for the real run, which skips R1.
Ubuntu 26.04.1 LTS (Canonical WSL image) is the single default for the clean install. Ubuntu 24.04.5 is the named
rollback, used only on a release-caused 26.04 failure with no in-release remedy. The 26.04.1 rehearsal stopped at F1
on WSL 2.7.13. Run 2 on WSL 3.0.1.0 (2026-10-02) passed stage 1 and W5's path-A proofs and observed distinct cgroup
namespaces, then stopped at the paired rule on the console collision. Probe E1 tested the getty mask outside the
recipe; a complete run with it through F3 and full acceptance remain owed.

| Release | Selected image | Exact SHA-256 |
| --- | --- | --- |
| 26.04.1 default | `ubuntu-26.04.1-wsl-amd64.wsl` | `48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104` |
| 24.04.5 rollback | `ubuntu-24.04.5-wsl-amd64.wsl` | `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e` |

## Rehearsals (both image arms, before the real run)

- [ ] **R1** Each image arm ran on its own throwaway name and its own folder through F3, with P3's baseline and W5's second storage count, W5's `cloud-init schema --system`, W7's owner and F2's idle observation recorded in the receipt's `rehearsal` block; then that name alone was terminated and unregistered (a failed rehearsal exported first, with exit 0 and its SHA-256 and size recorded); after each unregister, the surviving distribution's `WSLInterop` registration exists and a Windows executable launches, and when either check fails R1's records (`ls /proc/sys/fs/binfmt_misc` and `systemctl status systemd-binfmt.service --no-pager`) are kept and the run stops for review, importing or provisioning nothing; the last `--list --verbose` no longer lists it and the starred line is unchanged. A name already removed by W5 is not removed again. Both arms have the preregistered criteria with the amendments of 2026-10-02 made before any comparison ran ([decision record](../../../docs/decisions/2026-10-01-new-wsl-distro-recipe.md)): first boot with F1's pass condition, schema, systemd user from the second instance, WSL GPU visibility, uv-managed CPython 3.13 and Node 24.21.0, recorded in `comparison_arms`; failures and skips stay explicit, and F3's rootless check must pass before acceptance. The real install uses the single default unless the release-caused rollback condition holds.

## Workstation distribution (sh), before stage 1

- [ ] **P1** `gpgv` exits 0 with `Good signature` by `843938DF228D22F7B3742BC0D94AA3F0EFE21092`, with no key import; both 26.04.1 and 24.04.5 signed `SHA256SUMS` lines carry the exact release hashes above.
- [ ] **P2** `cloud-init schema -c` prints `Valid schema` for the render of `<WSL_USER>` and exits 0; the workstation cloud-init version and render's SHA-256 are recorded for the selected image. A host schema check is not image qualification; W5 must record and validate the selected packaged version on path A.
- [ ] **P3** The `hv_storvsc` count without the registration line or the kernel's command-line echo is recorded as the baseline; the newest error line, by its kernel time against `/proc/uptime`, is at least one hour old or absent (younger: errors are current, the run stops; microsoft/WSL#41482), unless its kernel time is a line an earlier run of the page recorded as its own attachment-window line, which is noted and does not stop the run; `swapon --show` is recorded.

## Windows host (PowerShell)

- [ ] **W1** `Z:\WSL\downloads` exists and the transcript is open; `wsl.exe --version` records WSL 3.0.1 or later before installing or importing a second systemd distribution (PR #40519 and PR #41512); an older version stops before W4 or W6; the workstation's baseline is recorded from the already-running distribution without `sudo`, with the five commands below each on its own line and with its own receipt entry and exit. Its uid equals the new default uid `1000`; its system state is `running` with no failed unit, or `degraded` with its failed set contained in {`systemd-binfmt.service`, `getty@tty1.service`}; its user manager is `active`; its namespace is not `cgroup:[4026531835]` (`PROC_CGROUP_INIT_INO`, the initial namespace). Anything else stops before W4 and before any W6 import. A failed getty is allowed only as an earlier console collision's leftover: `systemctl show getty@tty1.service -p Result -p NRestarts` is then recorded as optional `getty_tty1_result` and must show `Result=start-limit-hit`, or the run stops. The default (starred) distribution is recorded; `<Name>` is unregistered; `Z:\WSL\<Name>` does not exist; no Landscape user-data exists for `<Name>`; no `agent.yaml` exists, or its recorded top-level keys include neither `users` nor `write_files`; the `.wslconfig` read shows `instanceIdleTimeout` and `vmIdleTimeout` or their absence, recorded as `idle_keys`; free space on `Z:` is recorded. The older 2.4.10 install-only minimum applies to a single systemd distribution with no second systemd distribution running.

```sh
id -u
systemctl is-system-running
systemctl --failed --no-legend --plain
systemctl is-active "user@$(id -u).service"
readlink /proc/self/ns/cgroup
```
- [ ] **W2** Explicit `<RELEASE>` is one of the two controlled arms; download URL, filename and catalog entry match that release. The actual whole-image, signed Canonical publication and pinned DistributionInfo.json SHA-256 all equal that release's exact hash above; actual file size recorded (run 2 observed 418,495,746 bytes for 26.04.1); no `throw`.
- [ ] **W3** `%USERPROFILE%\.cloud-init\<Name>.user-data` exists, starts with `#cloud-config`, names `<WSL_USER>` twice and contains no `${`; its SHA-256 equals P2's.
- [ ] **W4** The selected `ubuntu-<RELEASE>-wsl-amd64.wsl` installs with exit 0; `Distribution successfully installed`; `<Name>` is `Stopped` at version 2; the starred line is unchanged.
- [ ] **W5** First launch exit 0, without the prompt marker; `wsl: Failed to start the systemd user session` stops even with exit 0; `id -un` is `<WSL_USER>` and `id -u` is `1000`; getty `is-enabled` prints `masked` (normal exit 1), and `show` prints `LoadState=masked`, `ActiveState=inactive`, `NRestarts=0`, recorded as `getty_mask`; selected-image `cloud-init --version` recorded; `cloud-init status --long` prints `status: disabled` with `boot_status_code: disabled-by-marker-file`; `/var/lib/cloud/data/result.json` names `DataSourceWSL` with `"errors": []`; `/var/lib/cloud/data/status.json` shows the four stages finished without errors; `cloud-init schema --system` prints `Valid schema user-data` and exits 0; `/etc/wsl.conf` names the user once; `/etc/cloud/cloud-init.disabled` exists; sudo is NOPASSWD; the starred line is unchanged. After the first launch, while both distributions run and before F1, the already-running distribution reads a system unit active in both: its `cgroup.procs` has local process ids and no `0` entry, and the new distribution's `user@<uid>.service` is active. An empty or unreadable file is inconclusive and stops. The paired block below records each of the five commands on each side in its own receipt entry with its own exit, in `paired_isolation`: the same uid, both user managers `active`, the new distribution `running` with no failed unit or `degraded` with `systemd-binfmt.service` as its only failed unit (message proved at F1), two `cgroup:[...]` values that differ from each other and are not `cgroup:[4026531835]`, and all five workstation values equal to its W1 baseline. A getty failed in the new distribution or newly failed in the workstation fails the proof. Any failed W5 proof terminates only the new distribution, never stops or restarts a unit in either, exports `<Name>-w5-failed.tar` with the exit guard and its cause (`cgroup`, `tty` or a short text) in `w5_failure_export`, unregisters and checks surviving `WSLInterop` and a Windows executable, with R1's records and stop for review. Do not take path B for any such failure. On both paths, record P3's baseline before the import and `second_count` after the first launch. An increase confined to the window in which the new disk is attached, before cloud-init starts, is recorded with the new lines and does not stop the run. Any storage error after that window, or any provisioning step that fails with a storage cause, stops the run. An unknown attachment window stops for review; storage failures retain microsoft/WSL#41482 and their own cause.

```sh
id -u
systemctl is-system-running
systemctl --failed --no-legend --plain
systemctl is-active "user@$(id -u).service"
readlink /proc/self/ns/cgroup
/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec id -u
/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec systemctl is-system-running
/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec systemctl --failed --no-legend --plain
/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec sh -c 'systemctl is-active "user@$(id -u).service"'
/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec readlink /proc/self/ns/cgroup
```
- [ ] **W6** Only after the W5 OOBE marker, never for another failed W5 proof: re-listed before `--unregister`; before `--unregister`, `<Name>` terminated and exported to `Z:\WSL\downloads\<Name>-failed.tar` with exit 0, and its SHA-256 and size recorded in `failed_attempt_export`; immediately after unregister, the surviving distribution's `WSLInterop` exists and a Windows executable launches before any import, and when either check fails R1's records are kept and the run stops for review with no import; W1's version precondition holds; the same selected image imports with exit 0; `cloud-init status` recorded; the root block starts with `systemctl mask --now getty@tty1.service`, after the import's first boot has already started the getty; `visudo` `parsed OK`; after `--terminate`, `id -un` is `<WSL_USER>`; W5's cgroup proof, paired record and checks pass before W7 or F1, or a workstation value differing from its baseline stops and uses W5's recovery, with `result.json` and `status.json` checked only if cloud-init ran on the import (otherwise their absence is recorded) and `cloud-init schema --system` skipped; `creation_path` is `B`.
- [ ] **W7** Both paths: `<Name>` terminated once and absent from the running list, then relaunched with `id -un` printing `<WSL_USER>`; the file created from Windows under the user's home reads `1000:1000` and is deleted; `0:0` is recorded and stops every write from Windows into the distribution.

## Inside the new distribution (as `<WSL_USER>`)

- [ ] **F1** `systemctl is-system-running --wait` prints `running` with no failed unit, or `degraded` when `systemctl --failed --no-legend --plain` lists exactly `systemd-binfmt.service` and its log, from `journalctl -b 0 -t systemd-binfmt --no-pager -n 4`, holds `Failed to flush binfmt_misc rules, ignoring: Read-only file system` (microsoft/WSL#40621 and #41226); any other failed unit stops for review. `getty@tty1.service` must not appear there.
- [ ] **F2** `Linger` is `yes`; with no client attached, `<Name>` is in every list of the two minutes of polls, or the time it left is recorded beside W1's idle keys.
- [ ] **F3** `/run/user/<uid>` is a directory and its `bus` a socket, both owned by `<WSL_USER>`; the user manager is `running`. Right afterwards, as that user without sudo, Docker's `rootless` context reports `name=rootless` and `docker --context rootless run --rm hello-world` exits 0 with `Hello from Docker!`; a failed start or missing rootless mode stops with microsoft/WSL#41492. This check is owed on the first run after the WSL update; if the engine is absent, record `owed`, complete F4, F5 and Docker's supported rootless setup, then return here before F9 or accepting R1.
- [ ] **F4** apt exits 0; `jq`, `libatomic1` and `uidmap` print versions.
- [ ] **F5** `/etc/subuid` and `/etc/subgid` hold 65,536 ids for `<WSL_USER>`; whether `useradd` or `usermod` wrote them is recorded.
- [ ] **F6** `~/.bash_profile` is exactly the hand-off line.
- [ ] **F7** The clone's `HEAD` equals `origin` `main`; the commit is recorded.
- [ ] **F8** `ss` shows no listener on the four ports; the host file parses with the nine keys and is git-ignored.
- [ ] **F9** Stage 2 runs from this clone with `--profile <id>`; its own receipts cover it.
- [ ] **F10** The fragment profiles carry `<Name>` in their names; `type -P claude codex` prints two absolute paths, and the per-path `test -f` and `test -x` line prints `executable:` for both.
- [ ] **F11** In a login shell, after F9 and F10: when `test -x` finds `jcodemunch-mcp`, `claude mcp add` run from the clone's root prints `Added ...` and `claude mcp get jcodemunch` names the local scope and the command; when it does not, `not installed` is recorded, and a step not run is recorded as `skipped` with the reason. `jcodemunch_registration` holds the outcome.
