# Decision: Ubuntu 26.04.1 WSL default and 24.04.5 rollback, provisioned by cloud-init (2026-10-01)

**Decided by:** coordinator session `native-agent-stack-c5` (decisions 1 to 5 below), on the research unit's findings of
2026-10-01. Unit W2 of that wave wrote the recipe, the templates and the test, and re-read the sources the same day.
A follow-up unit added F11 and the F5 range rule later that day, on the coordinator's brief. A second follow-up unit
then added the completeness critic's pre-stage-1 checks (R1, P1 to P3, W7, W5's schema check and F2's idle observation)
and corrected three facts, on the coordinator's brief and a research packet of the same day. The coordinator then set
P3's rule: the count is a baseline, an error line less than one hour old stops the run, and W5 counts again after the
first launch. A third follow-up took the updated host's first observations into the recipe on 2026-10-02: it names WSL
3.0.1 as the adopted target, adds W5's paired isolation record and F1's one accepted failed unit, and replaces the
interop restart with a stop for review (Updated-host correction).
This record changes nothing on a host. No `wsl.exe` command, import, `.wslconfig` edit or first launch ran for it. The
second follow-up's artifact checks ran P1 to P3's commands in the workstation distribution and changed nothing on the
host (Evidence classes).

**Scope:** [`adoption/platforms/linux-wsl2-new-distro.md`](../../adoption/platforms/linux-wsl2-new-distro.md) and its
pointer section in `adoption/platforms/linux-wsl2.md`; `adoption/templates/wsl/` (`cloud-init.user-data.template`,
`host.new-distro.json.template`, `first-boot-checklist.md`, `stage1-receipt.example.json`); `tests/test_wsl_new_distro_recipe.py`.

**Status:** the merged definitive manifest selects Ubuntu 26.04.1 LTS (Canonical WSL image) as the single default.
Ubuntu 24.04.5 is the named rollback, used only on a release-caused 26.04 failure with no in-release remedy.
The 2026-10-02 rehearsal held through stage 1, then stopped at F1 on the host's shared cgroup tree. It does not
trigger the image rollback. The host was updated to WSL 3.0.1.0 on 2026-10-02; full acceptance and the corrected
checks on it, with the two-distribution proof, remain owed. The earlier scoped
[experiment](../../blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json) keeps `status: planned`,
decision `trial`, no qualification runs and no usage comparison. Its next test preregisters both R1 rehearsals. The
reported signature exits and image stream hash match retain their bounded artifact scope; local consistency checks and synthetic receipt examples
do not qualify a distribution. Recipe, templates, this decision and tests are pinned by SHA-256 in that experiment.

## Context

- **The goal.** The user asked for the definitive WSL distribution for this practice, set up without prompts in the
  passwordless way an LLM-native session can follow end to end. Until now the repository had two pieces:
  - stage-2 tooling: `adoption/bootstrap-linux.sh` and its full-profile run;
  - userspace evidence: a fresh Ubuntu Base 24.04.5 filesystem on the existing WSL kernel
    (`docs/portable-userspace-install-20260921.md`).

  It had no procedure that creates the distribution itself.
- **Host** (research unit, 2026-10-01): WSL 2.7.13.0, kernel 6.18.33.2-2 and default version 2, with the workstation's
  distribution as the default. `wsl.exe --help` lists these forms:
  - `--install --from-file <Path> --name <Name> --location <Location> --no-launch`;
  - `--import <Distro> <InstallLocation> <FileName> [--version]`;
  - `--manage <Distro> --set-default-user <Username>`;
  - `--terminate <Distro>`.
- **Minimum WSL version for `--install --from-file`.** Microsoft gives 2.4.4 (build-custom-distro, updated 2025-09-12),
  Ubuntu's announcement 2.4.8 and Ubuntu's install guide 2.4.10 (Method 1). That install-only minimum remains valid
  for a single systemd distribution with no second systemd distribution running. It is insufficient for this page's
  second distribution: W1 requires WSL 3.0.1 or later before W4 or any W6 import, for isolated cgroups and their
  namespaces (PR #40519 and PR #41512). The research unit read the notes of WSL 2.7.14 (2026-09-11) and 3.0.1 (2026-09-29) and the `microsoft/WSL`
  source at the three tags, and wrote that they change nothing about install, import or first run. That was wrong
  (completeness critic, item 2). The fix for microsoft/WSL#40941, PR #40977 (after the first-run setup, files created
  from Windows are owned by 0:0), first ships in 2.9.8, a pre-release, and in 3.0.1. Its function,
  `ConnectionTargetManager::UpdateUid`, is absent from `src/windows/common/Redirector.h` at tags 2.7.13 and 2.7.14 and
  present at 2.9.8 and 3.0.1 (research packet, answer 3). W7 terminates `<Name>` once after the first launch and probes
  a file's owner; updating WSL stays the keys lane's decision.
- **Historical 24.04.5 image artifact check.** `ubuntu-24.04.5-wsl-amd64.wsl` (sha256 `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`)
  is 388,975,696 bytes and published twice:
  - in `https://releases.ubuntu.com/24.04.5/SHA256SUMS` (Last-Modified 2026-09-15 19:11:11 GMT; the same line is in
    `noble/SHA256SUMS`, with `SHA256SUMS.gpg` beside it);
  - as `Ubuntu-24.04` in `microsoft/WSL` `distributions/DistributionInfo.json` at `8bc98bc33b246fe66710eec9eaa1b24c323da987`
    (2026-09-14, "Updates Ubuntu latest LTS images (#41465)"), which maps it to
    `https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl`.

  On the authoring host on 2026-10-01, a single stream of that URL measured 388,975,696 bytes with exactly that sha256
  (Last-Modified 2026-09-08 00:19:19 GMT, gzip). The gzip size field gives 1,275,596,800 bytes unpacked; that field holds
  the size modulo 2^32.
- **What the image contains** (read from that stream):
  - `/etc/wsl.conf` is `[boot]` `systemd=true`.
  - `/etc/wsl-distribution.conf` has `[oobe] command = /usr/lib/wsl/wsl-setup`, `defaultUid = 1000` and
    `defaultName = Ubuntu-24.04`, plus a shortcut icon and a Windows Terminal profile template.
  - `/etc/cloud/cloud.cfg.d/99_wsl.cfg` sets `datasource_list: [WSL, NoCloud]`, disables network configuration and creates
    no default user.
  - `/etc/subuid` and `/etc/subgid` are present and empty (0 bytes). `/etc/login.defs` lines 178-193 set `SUB_UID_MIN`
    and `SUB_GID_MIN` to 100000 and `SUB_UID_COUNT` and `SUB_GID_COUNT` to 65536.
  - `/etc/skel` has `.bash_logout`, `.bashrc` and `.profile`, and no `.bash_profile`.
  - Installed (from the dpkg status): `cloud-init` 26.1-0ubuntu1~24.04.1, `systemd` and `systemd-sysv` 255.4-1ubuntu8.17,
    `libpam-systemd`, `dbus-user-session` 1.14.10-4ubuntu4.1, `sudo` 1.9.15p5, `git` 2.43.0, `python3` 3.12.3, `curl`,
    `ca-certificates`, `xz-utils`, `iproute2` 6.1.0, `gnupg` 2.4.4 and `wsl-setup` 0.5.10~24.04.2.
  - Absent: `jq`, `uidmap`, `bubblewrap`, `socat`, `libatomic1` and `ubuntu-insights`. The upstream `wsl-setup`
    repository now calls an Insights consent script that this image does not ship.
- **First run in the image's `/usr/lib/wsl/wsl-setup`** (148 lines, read from the stream):
  - It reads the Windows user name through `powershell.exe`, only to prefill a prompt (line 121).
  - When the file is missing, it copies the Ubuntu Sans Mono font into `%LOCALAPPDATA%\Microsoft\Windows\Fonts` and
    registers it under `HKCU` (lines 91-114, called at 125).
  - It sources `wait-for-cloud-init` (lines 127-130). With systemd running and `cloud-init-local.service` enabled, that
    script waits with `cloud-init status --wait` and then touches `/etc/cloud/cloud-init.disabled` (lines 9-12), so
    cloud-init runs on the first boot only.
  - It reuses the first interactive user with uid 1000 or more (lines 132-133). With none, it prompts
    `Create a default Unix user account:` (`read -e`, line 30, under `set -euo pipefail`, line 2), runs
    `adduser --quiet --gecos ''` (line 39) and adds the groups `adm,cdrom,sudo,dip,plugdev` (lines 20 and 44).
  - It appends `[user] default=` to `/etc/wsl.conf` only when no `default` exists under `[user]` (lines 54-72 and 146-148).
  - W5's two console lines, `Provisioning the new WSL instance $WSL_DISTRO_NAME` and `This might take a while...`, come
    from this script, not from WSL (follow-up research packet, answer 6). At the image's version they are lines 117-118:
    Launchpad `ubuntu/+source/wsl-setup` tag `import/0.5.10_24.04.2`, commit
    `74bfc89113bc7d46a4d9feb1e69cd6951fbc6908` (also `ubuntu/noble-updates`, changelog `wsl-setup (0.5.10~24.04.2)`),
    and GitHub tag 0.5.10 (`f83e4df49b3583272d5ca499ca63b426b934a1f3`). At the GitHub commit this record pins for
    `test/systemd-assertions.sh`, `86a561d5`, they sit at lines 122-123. WSL 2.7.13's `Resources.resw` holds neither
    string. The image's version, 0.5.10~24.04.2, is the research unit's read of the image's dpkg status; the follow-up
    did not re-read the image.
- **When WSL runs that command** (`microsoft/WSL` tag 2.7.13, commit `80697fd42cca3de0c0d5dd1931c36112372a577e`, read
  2026-10-01):
  - `WslClient.cpp:321` sets `LXSS_IMPORT_DISTRO_FLAGS_NO_OOBE` for `--import`. `--install --from-file` passes only the
    fixed-VHD flag (`:529-535`) and prints `Installing: {}` and
    `Distribution successfully installed. It can be launched via 'wsl.exe -d {}'` (`:525`, `:537`; texts from
    `localization/strings/en-US/Resources.resw`).
  - `LxssUserSession.cpp` registers the distribution with default uid root (`:1501-1511`, uid at `:1508`) and first-run
    setup on only when `NO_OOBE` is clear (`:1511`). It refuses a name or install path another registration uses
    (`:1475`, `:3798-3811`) and creates a missing install folder (`:1477-1481`). Without `--location` it uses
    `%LocalAppData%\wsl` plus a GUID (`:1464-1471`).
  - `WslCoreInstance.cpp:204-207` allows the first-run command only for a launch with no file name and no command line.
    `:171-178` makes any other launch wait, printing `Waiting for OOBE command to complete for distribution "{}"...`, and
    reads the default uid only after the command. `:293-303` clears `RunOOBE` and stores `oobe.defaultUid` only on exit 0;
    any other result leaves the setup pending.
  - `src/linux/init/init.cpp:623-676` runs the command as uid 0 through `/bin/sh -c`. A nonzero exit prints
    `OOBE command "%s" failed, exiting` and exits 1 (`:655-673`); success switches to `oobe.defaultUid` (`:675`).
  - `--import` extracts with `bsdtar` (`src/linux/init/main.cpp:1137-1155`), which reads the gzip `.wsl` file too.
  - The research unit added `_ProcessImportResultMessage` (`LxssUserSession.cpp:1597`). It creates the Start-menu shortcut
    and Windows Terminal profile (`:1682`), and both default to on (`src/linux/init/main.cpp:2656-2669`).
- **cloud-init on WSL.** Per Canonical's how-to and the cloud-init WSL datasource reference, the datasource reads
  `%USERPROFILE%\.cloud-init\<InstanceName>.user-data` first. A Landscape file at
  `%USERPROFILE%\.ubuntupro\.cloud-init\<InstanceName>.user-data` takes precedence. The datasource needs interop,
  automount and systemd. Both pages' examples create the user with `sudo: ALL=(ALL) NOPASSWD:ALL` and append
  `[user] default=` to `/etc/wsl.conf` through `write_files`. Whether cloud-init provisions an imported distribution is
  not documented.
- **cloud-init 26.1, the image's version, at tag `26.1`** (commit `8bf3567532b07e2cc15aa4c76c36ebed65ccfaec`; source read
  2026-10-01):
  - `cloudinit/sources/DataSourceWSL.py` loads the Ubuntu Pro files first: the Landscape instance file and `agent.yaml`,
    both in `%USERPROFILE%\.ubuntupro\.cloud-init` (`:241-270`, `:465-471`). It reads the local file only when no
    Landscape file exists (`:474-476`) and merges the result (`:490`). `merge_agent_landscape_data` lets every top-level
    `agent.yaml` key replace the user-data key entirely (`:317-336`), keeping only the user-data's Landscape tags
    (`:344-350`). When either side is not cloud-config, both go to cloud-init as an `#include` with the agent first
    (`:307-315`).
  - `cloudinit/cmd/status.py`: with systemd, `/etc/cloud/cloud-init.disabled` makes the boot code
    `disabled-by-marker-file` (`:284-286`) and the status `disabled` whatever the run did (`:385-386`). `detail` is the
    datasource while the run's `/run/cloud-init/status.json` exists and the marker reason otherwise (`:407-419`,
    `:471-481`). `errors` come only from that `/run` file (`:490`). With no datasource found, the generator's code is
    `disabled-by-generator` (`:298-300`). After the first launch, `cloud-init status` therefore proves the marker, not
    the run.
  - `cloudinit/cmd/main.py`: `status_wrapper` keeps `status.json` and `result.json` in the persistent data directory
    `/var/lib/cloud/data`, with only symbolic links in `/run/cloud-init` (`:880-888`, `:960-964`). Each stage's
    `start`, `finished`, `errors` and `recoverable_errors` go into `status.json` (`:915-929`, `:975-1015`).
    `result.json`, with the datasource and the errors of every stage, is written only when the final stage ends
    (`:1017-1030`). Single-process boots go through the same wrapper (`:1312-1368`, `:1400-1404`). The datasource
    string is the class name, `DataSourceWSL` (`cloudinit/sources/__init__.py:398-399`,
    `cloudinit/type_utils.py:21-28`).
- **What stage 2 expects** (`origin/main` 3361b342):
  - `adoption/bootstrap-linux.sh:167-178` requires x86_64, a non-root user and an Ubuntu or Debian `ID`.
  - `:186-200` refuses `--configure-full-profile` unless the checkout's `HEAD` is `origin/main`.
  - `:205-218` installs `ca-certificates curl git tar gzip xz-utils jq`, and `:221` requires
    `curl git tar sha256sum realpath flock jq mktemp`.
  - `:237-242` exits 1 on an empty `--profile`, and `:154-163` reads `adoption/hosts/<name>.json` for `--host`.
  - `adoption/bootstrap.md:227-228` gives the whole-profile run as
    `adoption/bootstrap-linux.sh --profile <id> --configure-full-profile --host <name>`, after native sign-in (step 3).
  - The guarded runners need a real `systemd --user` bus socket at `/run/user/$UID/bus`, owned by the user
    (`adoption/tools/README.md:184-188`).
  - Linger appears in the repository only as a draft (`adoption/templates/systemd/credential-boot-receipt.service:11-12`)
    and as "no record yet" (`docs/new-workstation-runtime-profile-20260922.md:25`).
- **Shared namespace.** All WSL 2 distributions share one network namespace (`adoption/platforms/linux-wsl2.md`,
  "Listeners and ports"). The template's ports collide with the workstation's services: `adoption/hosts/example.json:7-10`
  uses 14318, 49374, 16333 and 8231. The observability backend's templates fix 13000, 13100, 14333, 16333, 18080, 18525,
  18888, 18889, 19090, 19093, 20128 and 31415, and the live services also use 20129, 3710, 3800, 49474 and 18231.
- **jCodeMunch on a new distribution** (follow-up, 2026-10-01). The coordinator reported this gap from the cross-family
  review of PR #548. Stage 2's Claude profile step copies six SubagentStart carrier blocks from `adoption/hooks/claude/`
  into `~/.claude/hooks/` (`tools/adoption/install_claude_profile.py:49-59`):
  - `token-lanes-block.md` and `token-lanes-block.researcher.md` name jCodeMunch's `route`, `menu` and `order`;
  - `token-lanes-block.builder.md` and `token-lanes-block.reviewer.md` name `route` and `order`;
  - `token-lanes-block.scout.md` and `token-lanes-block.verifier.md` name no jCodeMunch tool.

  `adoption/mcp/claude-user.json` registers only `ai-memory` and `serena` at user scope. The 2026-09-25 addendum of
  `docs/decisions/2026-09-23-claude-user-profile.md` moved jCodeMunch to a per-project opt-in,
  `claude mcp add --scope local` (`adoption/bootstrap.md:458-472`), and no script runs it. No profile of
  `adoption/manifest.json` and no entry of `adoption/pins-linux-x86_64.json` carries `jcodemunch-mcp`. Only step 4a's
  `uv tool install --python 3.13 jcodemunch-mcp==1.108.319` installs it (`adoption/bootstrap.md:387-395`), and F9 does
  not run that line.
- **Local scope** (Claude Code's MCP page). "Local scope is the default. A local-scoped server loads only in the project
  where you added it and stays private to you. Claude Code stores it in `~/.claude.json` under that project's path, so
  the same server won't appear in your other projects." Its "Server status" section says "`claude mcp add` confirms a
  successful add by printing an `Added ...` line, which means the configuration was written". In its example, a
  repeated add at the same scope fails with `MCP server sentry already exists in local config`.
- **More than 65,536 subordinate ids.** Docker's rootless troubleshooting page says of
  `docker: failed to register layer: Error processing tar file(exit status 1): lchown <FILE>: invalid argument`: "This
  error occurs when the number of available entries in `/etc/subuid` or `/etc/subgid` is not sufficient. The number of
  entries required vary across images. However, 65,536 entries are sufficient for most images." The coordinator's
  brief calls the workstation's wider range a host observation for one benchmark image set.
- **Facts behind the second follow-up** (research packet of 2026-10-01; each source read that day, quoted as the packet
  quotes it):
  - *Install-path hashes, WSL 2.7.13* (`80697fd4`). The online `wsl --install <Distro>` looks the name up in
    DistributionInfo.json (`src/windows/common/WslInstall.cpp:94-146`) and runs `EnforceFileHash(file.get(),
    downloadInfo->Sha256)` (`:315`) before registering; a mismatch throws `TRUST_E_BAD_DIGEST` with
    `MessageHashMismatch` (`:36-50`; "The distribution hash doesn't match. Expected: {}, actual hash: {}",
    `Resources.resw:837-838`). The list comes from
    `https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json`
    (`src/windows/common/Distribution.cpp:20-21`) unless the host-wide `DistributionListUrl` or
    `DistributionListUrlAppend` value of the Lxss machine key overrides it (`:223-230`, `Distribution.h:85-86`).
    `--install --from-file` goes straight to `RegisterDistribution` with no hash check (`WslClient.cpp:500-537`).
  - *File ownership after the first-run setup.* https://github.com/microsoft/WSL/issues/40941 (closed "completed"
    2026-08-07, label `fixinbound`; reported on WSL 2.7.8.0). A contributor's reproduction
    (issuecomment-4863506473): "3. Finish the OOBE. 4. Create a file from Windows. The file created will be 0:0 until
    the next wsl --shutdown." https://github.com/microsoft/WSL/pull/40977 (merged 2026-08-07, merge commit
    `70f6890c83bb5e56b8ea17abdbb834b55e92dc80`): "Currently, after a fresh distro installation, operations in the linux
    plan9 share will use the uid 0. Because the uid was cached before the OOBE is complete. And this only recovers after
    a distro termination." The 2.9.8 release notes list it; the 2.7.11 to 2.7.14 notes do not. At 2.7.13,
    `WslCoreInstance.cpp:293-302` stores the new default uid after the setup without refreshing the plan9 registration.
    No source says whether `wsl --terminate` clears the state.
  - *Kernel storage errors.* https://github.com/microsoft/WSL/issues/41482 (closed by its reporter 2026-08-31, no linked
    fix): continuous `hv_storvsc` errors such as `tag#542 cmd 0x28 status: scsi 0x2 srb 0x4 host 0xc0000001` on WSL
    2.7.12.0, kernel 6.18.33.2-2 and Ubuntu 24.04 LTS, with `/sbin/init failed to start within 10000ms` and
    `Timed out waiting for user session`; the reporter counted them with `dmesg | grep -c hv_storvsc`. A contributor:
    "This seems to be an issue with the swap.vhdx. The exact cause is not clear yet"; the workaround is `[wsl2]`
    `swap=0` and `wsl --shutdown`. A comment of 2026-09-28 reports the same on Fedora 44.
  - *Idle shutdown.* wsl-config (pinned in Sources): `[wsl2] vmIdleTimeout`, default 60000, "Only available on Windows
    11"; `[general] instanceIdleTimeout`, default 15000, "Set to -1 to disable auto shutdown" (added to the page by
    MicrosoftDocs/WSL#2620; the key came with WSL 2.5.4). WSL 2.7.13 `LxssUserSession.cpp:2658-2676`: "A value of less
    than zero indicates that the instance should never be idle-terminated"; `:3583-3599` stops an instance only when
    no Windows calling process is registered. https://github.com/microsoft/WSL/issues/13416 (open): on WSL 2.7.3.0,
    "`loginctl enable-linger` ... does not prevent the poweroff" (issuecomment-5245052311). The coordinator read this
    workstation's global WSL configuration on 2026-10-01 at 10:08Z, values only: `[wsl2] vmIdleTimeout=-1`,
    `[general] instanceIdleTimeout=-1`, `networkingMode=mirrored` and `swap=24GB`.
  - *cloud-init's schema check.* Canonical's WSL how-to checks the provisioned instance with
    `sudo cloud-init schema --system` and expects `Valid schema user-data`. In cloud-init 26.1
    (`cloudinit/config/schema.py`): root is required (`:1388-1393`); a missing file prints
    `Error: Config file ... does not exist` (`:1428-1433`); with more than one data part a header comes first and the
    line is indented (`:1443-1458`, `:1492`); an invalid schema exits 1 (`:1493-1498`,
    `cloudinit/log/log_util.py:68-79`). The `schema` subcommand never reads `/etc/cloud/cloud-init.disabled`
    (`cloudinit/cmd/main.py:1240-1241`, `:1286-1293`), and `wait-for-cloud-init` runs no `cloud-init clean`.
  - *Signed checksums.* https://ubuntu.com/tutorials/how-to-verify-ubuntu (undated): "Ubuntu and most variants come with
    the relevant keys pre-installed"; it verifies with `gpg --keyid-format long --verify SHA256SUMS.gpg SHA256SUMS`
    after a keyserver fetch. `ubuntu-keyring` 2023.11.28.1 (Launchpad `import/2023.11.28.1`,
    `edc0a0be9a90f364bc39a87d3837ad4c15395950`, `debian/changelog:141-142`) adds "4096R/EFE21092 Ubuntu CD Image
    Automatic Signing Key (2012)" to `ubuntu-archive-keyring`, so `/usr/share/keyrings/ubuntu-archive-keyring.gpg`
    carries `843938DF228D22F7B3742BC0D94AA3F0EFE21092`. The repository's 2026-09-21 precedent verified Ubuntu's signed
    sums with the same key (`docs/portable-userspace-install-20260921.md`).

## W-IMG preregistration and preserved primary evidence (2026-10-01)

The north-star action is a recoverable second WSL distribution for native engineering. The accepted unit extends the
existing upstream-command recipe, templates and tests at `798ac445`; it creates no installer or architecture. The
coordinator applied the maintained ECC `search-first` guidance in quick mode and the TDD skill at the already-agreed
public recipe/template/experiment seams. No new dependency or skill installation is needed.

| Image role | Actual release URL | Exact image SHA-256 | Catalog entry at `8bc98bc33b246fe66710eec9eaa1b24c323da987` |
| --- | --- | --- | --- |
| 26.04.1 default | https://releases.ubuntu.com/26.04.1/ubuntu-26.04.1-wsl-amd64.wsl | `48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104` | `Ubuntu-26.04` (also `Ubuntu`) |
| 24.04.5 rollback | https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl | `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e` | `Ubuntu-24.04` |

Both arms use the same R1 preregistered criteria with the amendments of 2026-10-02 made before any comparison ran
(recorded below), and native probes in the recipe, on separate throwaway names under the same host kernel, driver,
settings, checkout, user-data and bootstrap profile. R1 keeps its initial run
through F3, then extends successful rehearsals through F9 for the existing toolkit and the bounded comparison probes.
The default-user systemd manager and bus are checked from the workstation's second-instance session. GPU visibility
uses Microsoft's/NVIDIA's native WSL guidance; toolkit runtime checks use the accepted bootstrap and official Node
24.21.0 pin. A version/startup probe or visible GPU does not establish full-stack, CUDA workload or model acceptance.
The clean install uses the single 26.04.1 default from
[`definitive-manifest.json`](../../evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json).
The 24.04.5 rollback returns only for a release-caused 26.04 failure with no in-release remedy. Both arms' full
new-host acceptance remains owed; the comparison distributions do not become clean-install alternatives.

**Preserved facts, reused rather than rerun.** The retained
[integration receipt](../../evidence/artifacts/new-wsl-dual-image-20261001/receipt.json) reports signed-checksum
verification exit 0 for both releases, signer fingerprint `843938DF228D22F7B3742BC0D94AA3F0EFE21092` and a 26.04.1
image stream hash match. There is no retained verification output for that 26.04.1 signature check; those reported
exits, fingerprint and match do not establish a retained `Good signature` stream. The earlier 24.04.5 P1 output and
tampered-copy control below retain their historical artifact scope. No 26.04.1 image size was observed in that
authoring stream; the later rehearsal records its own download size separately.

The inspected 26.04.1 packages are cloud-init 26.1-0ubuntu3~26.04.1, systemd 259.5-0ubuntu3.4, Python interpreter
3.14.4-1ubuntu0.1, sudo-rs 0.2.13-0ubuntu1 and wsl-setup 0.6.3ubuntu~26.04.1. Correction: the earlier Python 3.14.3
statement was the `python3` metapackage (3.14.3-0ubuntu2); the retained dpkg `python3.14`, `python3.14-minimal` and
`libpython3.14-stdlib` stanzas prove interpreter 3.14.4-1ubuntu0.1. System Python 3.14 is not toolkit CPython 3.13
migration acceptance; uv selects and installs managed 3.13 separately. Installed uv 0.12.17 `run --help` exited 0
and lists `--no-project` and `--python`; no managed interpreter run was performed for this unit.

The retained `wsl-setup` and `wait-for-cloud-init` image extracts match tag `0.6.3`, upstream commit
`73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8`. `wsl-setup:155-156` calls `ubuntu-insights.sh`. Its consent path preserves
existing Linux/Windows settings; `ubuntu-insights.sh:15-19` asks only on terminal stdin (`-t 0`). W5 uses NUL stdin.
No recipe command invents consent or writes the Windows-wide consent registry. Neither source inspection nor the
workstation's P2 schema check qualifies a new image; W5 must record the selected packaged version and its own schema.
Canonical's cloud-init WSL guide explicitly assumes 24.04/22.04 and does not qualify 26.04.

**Prior failed preparation attempt.** The preceding native Claude worker returned the actual weekly-limit message,
process exit 1, and made no changes. Its native returned usage is preserved in the experiment's usage rule, without
summing cache subsets, estimating missing totals or treating unknown retries as zero. This is a recipe-preparation
failure, not a failed first boot of either image. No provider, GPU, import or first-boot run is claimed by this unit.

**Completeness critic.** Both signed sums, exact selected-image bytes/hash, packaged schema versus host schema,
second-instance systemd user behavior, Windows GPU visibility, separate uv CPython 3.13 and Node 24 startup now have
explicit symmetric criteria. Preserve the old export guard for failed rehearsals and W6. The remaining gap is native
new-host execution of both arms, plus separate full-stack/GPU-workload/model acceptance. Debian, alternate creation
routes and containers remain the earlier sweep candidates; this bounded unit adds none. The lifecycle-task skills
sweep receives only a future execution gap, since the accepted lifecycle/TDD/search guidance covers parameterization.

## Rehearsal correction (2026-10-02)

The retained `coordinator-review.md` and `stage1-receipt.json` on
`origin/foundation/new-wsl-rehearsal-20261002` at `76b7c0b4ee45d3a6f0a60fa68d053e0f2039e8e4`, under
`evidence/artifacts/new-wsl-rehearsal-20261002/`, record the real
Ubuntu 26.04.1 rehearsal on WSL 2.7.13. Stage 1 held, including schema and ownership; F1 returned `degraded`, with
`user@1000.service` failing to spawn its executor. From the already-running distribution, the coordinator read
`0 <pid> 0` in `system.slice/cron.service/cgroup.procs` and the other distribution's user manager reported the
workstation's own `ControlGroup`. The supplied namespace observation, `cgroup:[4026531835]`, names Linux's initial
cgroup namespace, `PROC_CGROUP_INIT_INO` in `include/linux/proc_ns.h`; it corroborates the diagnosis and is not a gate.

Correction: command support on 2.7.13 did not establish safe concurrent systemd distributions. Microsoft's release
notes name PR #40519 in 2.9.8 (isolate distro cgroups) and PR #41512 in 2.9.13 (create their namespaces), both
pre-releases; 3.0.1 is the first stable release with both. The 2.7 line has neither. W1 now requires 3.0.1 or later
before any install or import. After launch, W5 must observe no `0` entry in a unit active in both distributions, from
the already-running distribution, and an active new `user@<uid>.service`, before F1. A failed observation terminates
only the new distribution, exports, unregisters and checks surviving interop; it never stops or restarts a system unit
in either distribution. When this correction was written, nothing had been observed on 3.0.1 on this host; the
Updated-host correction below records what followed. Rootless Docker/Podman issue 41492 remains open; F3's container
start is owed on the first run after the update.

After removal, the surviving distribution lost the VM-wide `WSLInterop` registration. The coordinator restored it
with `sudo systemctl restart systemd-binfmt`. Every unregister now checks both that registration and one Windows
executable on the survivor and stops if either observation does not return. The Updated-host correction replaces
the restart, which the adopted release does not support, with a stop for review.

The rehearsal's storage baseline was 7 and second count 13, with six new lines in the disk-attachment window before
cloud-init. Their placement about 15 seconds before `init-local` is derived in the receipt; the launch exited 0.
W5 and the checklist now record an attachment-only increase with its lines and continue; any later storage error or
provisioning failure with a storage cause stops. The older rule requiring equality was not supported by that run.

The repair extends the existing Python `unittest` consistency checks with independent stage ids, every selected-image
digest field and in-memory controls restoring the old unsafe wording. These checks inspect source only; they do not
rerun the host rehearsal. A completeness check keeps path B, the export guards, all existing stages and the older
single-distribution install boundary; it also checks the new unregister in cgroup recovery. Public upstream refresh
was unavailable because DNS resolution failed, so the retained review and the supplied upstream references are used
without claiming a fresh fetch or an updated-host result.

## Updated-host correction (2026-10-02)

The coordinator's brief of 2026-10-02 reports the first observations of the updated host, WSL 3.0.1.0 with kernel
6.18.40.1-1, made from 06:39Z to 06:57Z in the workstation's distribution, as its default user and without `sudo`.
`id -u` printed `1000`. `systemctl is-system-running` printed `degraded` (exit 1), with `systemd-binfmt.service` as the
only failed unit. `systemctl is-active "user@$(id -u).service"` printed `active`. `readlink /proc/self/ns/cgroup`
printed `cgroup:[4026532183]`, equal to `/proc/1/ns/cgroup`; WSL 2.7.13 had printed the initial namespace,
`cgroup:[4026531835]`. The host also passed its check of a rootless container, interop and the user manager.
`systemd-binfmt.service` failed at each observed boot with `Failed to flush binfmt_misc rules, ignoring: Read-only file system`
and exit 1, while `WSLInterop` and `python3.12` are registered and Windows executables launch. (Qualified on 2026-10-02
after the Codex lane's bounded review of `46acc1e5`: WSL installs that read-only lock only while `[boot]
protectBinfmt` is on, its default, and as a best-effort step, `init.cpp` L2433 and L2916-L2923 and
`WslDistributionConfig.h` L62 at tag `3.0.1`; "every boot" is this host's observation under the default, not an
upstream guarantee.) Nothing was observed with
two distributions running.

Three decisions follow; Sources lists what each rests on.

1. **Adopted target.** The recipe adopts stable WSL 3.0.1 or later for a second systemd distribution. The 2.9.8 and
   2.9.13 pre-release history and the 2.7.13 rehearsal stay as history, and the single-distribution note stays. The
   host's update and its check are one sentence in Host-wide rules; the two-distribution proof is still owed.
2. **Paired isolation (W5).** W5 records the same five observations from both running distributions, `uid`,
   `system_state`, `failed_units`, `user_manager` and `cgroup_namespace`, under `paired_isolation` in the receipt, after
   the cgroup block and before F1. The workstation's values must equal its own baseline from W1, the two namespaces must
   differ from each other and from `cgroup:[4026531835]`, and both user managers must be `active`. W6's relaunch repeats
   the record, as it repeats the cgroup proof, and the failure recovery is the cgroup-failure recovery, unchanged.
3. **The by-design unit failure (F1) and the interop recovery (R1).** F1 accepts `degraded` only when
   `systemctl --failed --no-legend --plain` lists exactly `systemd-binfmt.service` and that unit's log holds the
   read-only flush message; any other failed unit stops the run as before. `sudo systemctl restart systemd-binfmt` was
   the WSL 2.7.x interop remedy. On the adopted release the registration is protected and that restart itself exits 1,
   so R1 keeps its check after every unregister and, when it fails on 3.0.1, stops for review with
   `ls /proc/sys/fs/binfmt_misc` and `systemctl status systemd-binfmt.service --no-pager` recorded; nothing is imported
   or provisioned.

Alternatives, each rejected against that evidence:

- **A one-sided W5 reading**, the new distribution's `user@<uid>.service` alone: it cannot show the same uid, distinct
  namespaces and two healthy managers, so the record pairs the five observations.
- **Namespace values alone**: a value does not prove isolation (W1 already says so), and two values compare only next to
  the workstation's own baseline.
- **Stopping at every `degraded`**, the earlier F1: the unit fails at each boot on the adopted release under its default
  `protectBinfmt` setting, so no run on this host could pass F1.
- **Accepting any `degraded`**: it would hide a real failed unit. The pass condition names the one unit and its log
  message.
- **Keeping the restart as the interop recovery**: it exited 1 on this host on the adopted release, where PR #40621
  protects the registration on purpose while `protectBinfmt` is on (its default).

The conditions that would overturn these decisions are in Overturn condition, items 3 and 4.

## Alternatives

1. **Images.** Ubuntu 26.04.1 LTS (Canonical WSL image) is the single clean-install default; the parameterized recipe
   retains historical 24.04.5 as the named rollback only for a release-caused 26.04 failure with no in-release remedy.
   Full new-host compatibility remains owed. The earlier `python3` 3.14.3 statement described its metapackage, not
   the 3.14.4 interpreter (correction in W-IMG preregistration).
   Other alternatives:
   - `wsl --install Ubuntu-24.04` from the online catalog installs the same bytes. At 2.7.13 it does check the download
     against the catalog entry's `Sha256` (`WslInstall.cpp:36-50`, `:315`), while `--install --from-file` checks no
     hash (`WslClient.cpp:500-537`); this record first had that backwards (completeness critic, item 8). The online path
     reads the catalog from `master` at install time unless a host-wide `DistributionListUrl` override is set. The file
     path is kept for a pinned file and a hash the operator sees, against a catalog resolved at install time, and W2's
     own hash check exists because `--from-file` verifies nothing.
   - The `cloud-images.ubuntu.com/wsl` rootfs tarballs: that page says WSL images moved to cdimages and those tarballs are
     not general-purpose.
   - The other images of WSL's catalog (Fedora, Arch, AlmaLinux, openSUSE, SLE, Kali and eLxr) are out of scope while
     stage 2 accepts only `ID=ubuntu` or `ID=debian` (`adoption/bootstrap-linux.sh:175-178`). Debian, whose catalog
     file is a salsa.debian.org CI artifact, feeds the layer's next landscape sweep (completeness critic, item 6).
   - WSL containers, generally available in 3.0.1, feed the next landscape sweep for disposable clean-install tests;
     they are unlikely to host stage 2 (completeness critic, item 7).
   - A self-built image is out of scope: it breaks the rule to install upstream artifacts with upstream commands
     (completeness critic, item 9).
2. **Creation path.**
   - **Interactive first launch.** The prompt of `wsl-setup` line 30 needs a person, which blocks an LLM-native run.
   - **`--import` with a manual user (path B).** It starts as root and skips the first-run command
     (`WslClient.cpp:321`), so `wait-for-cloud-init` never writes its marker; the cloud-init question stays open.
   - **In-place repair after a failed first launch.** Not chosen by the coordinator; recommended by unit W2. Create the user
     as root with `wsl.exe -d <Name> -u root --exec useradd ...` and relaunch without a command. A failed first run leaves
     `RunOOBE` set (`WslCoreInstance.cpp:293-297`), and the next launch reruns `wsl-setup`, which reuses any uid 1000 or
     more user (lines 132-133) and writes the marker. The registration, the official first-run path and the marker all
     stay as in path A, and no disk is deleted.
   - **cloud-init `packages:` in the user-data.** It would fold F4 into the unattended phase, where a failed `apt` would
     surface only as cloud-init's recoverable errors.
   - **A golden copy**, `wsl --export` of a provisioned distribution and then `--import-in-place` of its disk, feeds the
     layer's next landscape sweep. **Ubuntu Pro for WSL** (Landscape) is out of scope: it needs a subscription and a
     server (completeness critic, item 9).
3. **First boot.**
   - Leave out `libatomic1`. The Node 24.21.0 binary that `adoption/pins-linux-x86_64.json` pins lists no
     `libatomic.so.1` among its `NEEDED` libraries (the tarball matched its pin
     `fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6`; read with `readelf -d` on 2026-10-01).
   - Append `<user>:100000:65536` to `/etc/subuid` and `/etc/subgid` by hand, as in Docker's example, instead of
     `usermod --add-subuids` and `--add-subgids`.
   - Allocate a wider subordinate range at first boot, as the workstation has. Docker's troubleshooting page ties the
     need to the image set and calls 65,536 sufficient for most images.
   - Register jCodeMunch in F11 through step 4a's checked-in `.mcp.json` form. It waits for workspace trust and
     approval, and a nested `${ECO_INSTALL_ROOT:-...}` default does not expand there (the addendum's measurement).
   - Install `jcodemunch-mcp` in F11 when it is absent, with step 4a's `uv tool install` line. Not chosen in the
     coordinator's brief: F11 records `not installed`, and the install stays with step 4a.
   - Leave the clone unregistered. Four carrier blocks would then name tools of a server the session lacks.
4. **Host-wide.**
   - Proceed with the second systemd distribution on WSL 2.7.13: rejected after the rehearsal proved a shared cgroup
     tree and a failed uid-1000 user manager. WSL 3.0.1 or later is now a host prerequisite, for PR #40519 and PR
     #41512, and also carries the fix for microsoft/WSL#40941. The keys lane performs the update outside this page.
     W7's owner probe remains required. This record's earlier install-only version claim did not establish safe
     concurrent systemd distributions; the retained rehearsal and upstream release notes correct it.
   - Apply settings with `wsl --shutdown`: it stops every distribution.
   - Set `swap=0` for microsoft/WSL#41482, or change an idle key: both change the global WSL configuration, and the
     first takes effect only after a WSL shutdown; that is the user's decision, not this recipe's.
   - P3 as a bare count that stops on any error line, the second follow-up's first form: rejected by the coordinator.
     A count over the current boot cannot tell errors that are happening now from an old burst, and on this host one
     burst seven days earlier would have blocked stage 1 for good. P3's count is now a baseline; the newest line's age
     and W5's second count decide.
   - Judge that age by the journal's wall-clock stamp (`-o short-iso`): rejected, because journald stamps a kernel
     line when it reads it, and after a restart of the workstation distribution it reads the ring buffer again and
     stamps old lines anew. The kernel time against `/proc/uptime` does not move.
   - Make the new distribution the default now: the workstation stays the default until a separate decision.

## Decision

1. **Images.** The single clean-install default is Ubuntu 26.04.1 LTS (Canonical WSL image). Select 24.04.5 only as
   the named rollback for a release-caused 26.04 failure with no in-release remedy. P1 verifies both signed sums; W2 controls each release-to-file-to-SHA-to-catalog
   pairing, downloads the selected release URL and hashes the actual whole image. W4 and W6 use the same selected
   filename. Historical 24.04 receipts keep their original evidence class and scope; they do not accept either arm
   on a new host.
2. **Creation path.**
   - **Path A.** Render `%USERPROFILE%\.cloud-init\<Name>.user-data` from the template (W3). The user is `<WSL_USER>`,
     uid 1000, in groups `adm, cdrom, sudo, dip, plugdev`, with `sudo: "ALL=(ALL) NOPASSWD:ALL"`, a locked password and
     `[user] default` appended to `/etc/wsl.conf`. Then run
     `wsl --install --from-file <dir>\ubuntu-<RELEASE>-wsl-amd64.wsl --name <Name> --location Z:\WSL\<Name> --no-launch` (W4),
     then a first launch with standard input at end of file (W5).
   - **Rehearsals first (R1).** Each release runs on its own throwaway name and folder through F3, recording W5's schema,
     W7's probe and F2's idle observation. Successful rehearsals extend through F9 and the same preregistered comparison
     probes; per-arm results enter `comparison_arms`. R1 terminates and unregisters only its own name, after W6's export
     rule when a rehearsal failed. Both comparison records precede the real explicitly selected `<Name>`.
   - **Pre-checks (P1 to P3)**, in the workstation distribution before W1. P1 verifies `SHA256SUMS` with `gpgv`
     for both releases against the installed archive keyring (key `843938DF228D22F7B3742BC0D94AA3F0EFE21092`) and prints
     both signed image lines. P2 runs the workstation's `cloud-init schema -c` on the selected-image render and prints its
     SHA-256, which W3's file must match; this does not qualify the selected image's schema, which W5 checks itself. P3
     records the current boot's `hv_storvsc` kernel journal count, without the registration line, as a baseline and
     prints the newest error line's kernel time beside `/proc/uptime`. An error line less than one hour old stops the
     run (microsoft/WSL#41482); the threshold is this recipe's choice, not an upstream figure.
   - **Second storage reading (W5).** Record the baseline before the import and the second count after the first
     launch on both paths. An increase confined to disk attachment before cloud-init starts is recorded with its
     lines and does not stop the run. Any storage error after that window, or a provisioning failure with a storage
     cause, stops the run. An unknown window stops for review; retain the actual cause with microsoft/WSL#41482.
   - **Preflight (W1).** Neither Ubuntu Pro file exists, or `agent.yaml`'s top-level keys are recorded and include
     neither `users` nor `write_files`. W1 also reads `instanceIdleTimeout` and `vmIdleTimeout` of the global WSL
     configuration, without writing it. WSL must be 3.0.1 or later before W4 or any W6 import. Record the
     workstation's baseline of five values in the already-running distribution, as its default user and without `sudo`:
     the uid, the system state, the failed unit names, the user manager's state and `readlink /proc/self/ns/cgroup`,
     with the initial namespace `cgroup:[4026531835]`, Linux's `PROC_CGROUP_INIT_INO`, named as corroboration rather than
     the gate. The baseline must already meet W5's rule for one distribution, or the run stops before W4.
   - **After the first launch (W5).** `cloud-init status --long` must print `status: disabled` with
     `boot_status_code: disabled-by-marker-file`. Completion and errors come from `/var/lib/cloud/data/result.json`
     (`DataSourceWSL`, `"errors": []`) and `/var/lib/cloud/data/status.json` (four stages finished without errors). On
     path A, `cloud-init schema --system` must print a line matching `^\s*Valid schema user-data$`; path B skips it.
     `wsl: Failed to start the systemd user session` stops even when the launch exits 0. While both distributions run,
     before F1, the already-running distribution must read no `0` entry in a system unit's `cgroup.procs`, for a unit
     active in both, and the new distribution's `user@<uid>.service` must be active. Then the paired record reads the
     same five values from both distributions (`paired_isolation`): the same uid, active user managers, system managers
     `running` or `degraded` with only `systemd-binfmt.service` failed, two namespaces that differ from each other and
     from the initial one, and the workstation's values equal to its W1 baseline. Failure of either proof terminates
     only the new distribution, never stops or restarts a unit in either, guards the export, unregisters and checks
     surviving interop.
   - **Terminate once (W7).** After W5 (path A) or W6 (path B): `wsl --terminate <Name>`, a relaunch, and an empty file
     created from Windows under the user's home must read `1000:1000`. `0:0` stops every write from Windows.
   - **How to tell cloud-init did not provision.** The launch prints `Create a default Unix user account:` and
     `OOBE command "/usr/lib/wsl/wsl-setup" failed, exiting` and returns nonzero.
   - **Fallback, path B (W6).** Re-list, then preserve the failed attempt. `wsl --terminate <Name>` and
     `wsl --export <Name> Z:\WSL\downloads\<Name>-failed.tar` keep its cloud-init logs, `/var/lib/cloud/instance` and its
     configuration. Its SHA-256 and size go to the receipt's `failed_attempt_export`. A nonzero export exit throws
     before any deletion. Then `--unregister` the literal new name, check surviving interop, `--import ... --version 2`, then a manual user with
     the same groups and NOPASSWD drop-in, `[user] default`, the marker and `wsl --terminate <Name>`.
   - **Stage-1 receipt.** The private PowerShell transcript, sanitized into the shape of
     `adoption/templates/wsl/stage1-receipt.example.json`. Its payload keys are those `scripts/validate.py` compares with a
     `receipts[]` row; `kind` is `native_cli_e2e` and `component_ids` is `systemd` (stack row `255.4-1ubuntu8.17`, the
     image's version).
3. **First boot**, as the user:
   - `systemctl is-system-running --wait` must print `running`, as Ubuntu's own setup test asserts, or `degraded` when
     `systemctl --failed --no-legend --plain` lists exactly `systemd-binfmt.service` and that unit's log holds the
     read-only flush message: the adopted release mounts the binfmt status file read-only (microsoft/WSL#40621) and
     upstream calls the unit's error benign (#41226). Any other failed unit stops the run for review.
   - `loginctl enable-linger`, then `Linger=yes`; then, with no client attached, `wsl.exe --list --running` every 10
     seconds for two minutes records whether `<Name>` stays up (F2).
   - The user bus is a socket owned by the user. Right after F3, a rootless container must start on Docker's
     `rootless` context, as the user without sudo. Check `name=rootless` and run
     `docker --context rootless run --rm hello-world`; a failed start stops with microsoft/WSL#41492. This is owed
     on the first run after the update; an absent engine requires F4, F5 and Docker's supported rootless setup, then
     a return to this check before F9 or accepting R1.
   - `apt-get install` the bootstrap's list plus `libatomic1` and `uidmap`:
     - `uidmap` for rootless Docker in the Harbor harness;
     - `libatomic1` for parity with the workstation profile (`docs/new-workstation-runtime-profile-20260922.md:34`). The
       measurement in Alternatives 3 removes the original reason, so the coordinator may drop it.
   - Subordinate ids are checked, and `usermod --add-subuids 100000-165535 --add-subgids 100000-165535` runs only when
     none exist. 65,536 stays the stage-1 value. The unit that pulls the images (the evaluation harness unit) widens
     the range only when a pull fails with `lchown <FILE>: invalid argument`, and records the image and the error.
   - `~/.bash_profile` gets the hand-off line of `adoption/platforms/linux-wsl2.md` (lines 185-188).
   - A clone of `origin/main`; `adoption/hosts/<host>.json` from the host template on ports 24318, 29374, 26333 and 28231,
     probed with `ss`.
   - Native sign-in, then stage 2 with `--profile <id> --configure-full-profile --host <host>`. The brief's command lacked
     `--profile`, which the script requires.
   - The Windows Terminal fragment with profile names that carry `<Name>`, then `type -P claude codex`, with each printed
     path tested by `test -f` and `test -x`.
   - F11, after stage 2 and F10, in a login shell. `test -x` checks the `jcodemunch-mcp` binary in its own block. When
     the binary exists, step 4a's `claude mcp add --scope local jcodemunch` line runs from the clone's root, and
     `claude mcp get jcodemunch` proves it. The receipt's `jcodemunch_registration` records `registered`,
     `not installed` or `skipped` with the reason. The coordinator's brief gives the reason to record every outcome:
     under the Gate A re-aim, the baseline capture freezes whichever state exists.
4. **Host-wide.**
   - No `.wslconfig` change, no `wsl --update`, never `wsl --shutdown`.
   - `wsl --terminate <Name>` only, and only for the new distribution.
   - The default distribution stays the workstation's.
   - The generated terminal profile may stay, hidden by the operator if duplicated.
   - WSL package updates are the keys lane's decision.
   - The rehearsal (R1) names only its own distribution.
   - Every unregister checks `/proc/sys/fs/binfmt_misc/WSLInterop` and launches a Windows executable in the surviving
     distribution. If registration or Windows execution does not return, the run stops for review after the new
     distribution is removed, with `ls /proc/sys/fs/binfmt_misc` and `systemctl status systemd-binfmt.service
     --no-pager` recorded; nothing is imported or provisioned. The WSL 2.7.x remedy, restarting `systemd-binfmt`, is
     not used on the adopted release, where that restart exits 1.
   - W1's `Select-String` read is the only command that names `.wslconfig`; the test rejects any other command naming it.
   - The test rejects any recipe command that breaks these rules.
5. **Open questions** stay open; see below.

## Overturn condition

1. **Images.** Keep 26.04.1 as the single default; 24.04.5 returns only for a release-caused 26.04 failure with no
   in-release remedy. Accept the selected image within the measured host scope only after the required, identically scoped R1
   comparison records for first boot, the systemd user manager from a second instance, WSL GPU visibility,
   uv-managed CPython 3.13 and the pinned Node 24. Preserve failures and skips; missing evidence is not a win.
   Comparisons stay on throwaway names. Re-pin a release only after Canonical's signed sums and the
   pinned Microsoft catalog agree. A W2 mismatch stops the run with nothing installed.
2. **Creation path.** Revisit in two cases:
   - a host run with a correct user-data file still shows the W5 markers;
   - a WSL release changes when the first-run command runs (`WslCoreInstance.cpp:204`) or what a failure leaves
     (`:293-303`).

   The coordinator may instead adopt the in-place repair as the first fallback, ahead of path B.
3. **First boot.** Revisit in four cases:
   - F1 reports `degraded` with a failed unit other than `systemd-binfmt.service`, or without that unit's read-only
     flush message, on a clean run;
   - the bootstrap starts installing `uidmap` or `libatomic1` itself;
   - the Harbor lane retires rootless Docker, which removes `uidmap` and F5;
   - the user-scope MCP template registers jCodeMunch again (the addendum's overturn condition), or a script runs the
     per-project registration, which turns F11 into a check.

   Drop `libatomic1` when the coordinator accepts the `readelf` measurement.
4. **Host-wide.** Revisit on a later WSL update after the completed 3.0.1 update (re-verify install, import and first
   run at that tag, including W7's check of the microsoft/WSL#40941 fix already present in 3.0.1) or when a separate
   decision makes the new distribution the default. Revisit P3 when microsoft/WSL#41482 names a fixed release, or when a run
   shows storage errors that the one-hour threshold, this recipe's choice, misjudges. Revisit the adopted target and
   W5's paired record when a stable release after 3.0.1 changes how distributions share cgroups, or when a run shows two
   equal namespaces or an unhealthy user manager. Revisit F1's one accepted failed unit when a WSL release stops mounting
   the binfmt status file read-only or systemd stops failing on it, and R1's stop for review when a 3.0.1 run loses
   `WSLInterop` after an unregister and upstream documents a remedy.

## Command table

Every command line of the recipe's `powershell` and `sh` blocks, in order. `tests/test_wsl_new_distro_recipe.py` fails
when a row and the recipe disagree. The proofs are what the next run must print. The earlier 2.7.13 rehearsal is
retained separately; the corrected run on 3.0.1 remains owed. P1 to P3 also have historical artifact checks in the
workstation distribution (Evidence classes).

| Step | Shell | Command | Proof |
| --- | --- | --- | --- |
| R1 | powershell | `wsl.exe -d '<Name>' --exec bash -lc 'stat -c %U,%F /run/user/$(id -u) /run/user/$(id -u)/bus'` | R1: record the returned exit and output required by the recipe |
| R1 | powershell | `wsl.exe -d '<Name>' --exec systemctl --user is-system-running --wait` | R1: record the returned exit and output required by the recipe |
| R1 | powershell | `wsl.exe -d '<Name>' --exec test -c /dev/dxg` | R1: record the returned exit and output required by the recipe |
| R1 | powershell | `wsl.exe -d '<Name>' --exec /usr/lib/wsl/lib/nvidia-smi` | R1: record the returned exit and output required by the recipe |
| R1 | powershell | `wsl.exe -d '<Name>' --exec bash -lc 'python3 --version'` | R1: record the returned exit and output required by the recipe |
| R1 | powershell | `wsl.exe -d '<Name>' --exec bash -lc 'uv run --no-project --python 3.13 python --version'` | R1: record the returned exit and output required by the recipe |
| R1 | powershell | `wsl.exe -d '<Name>' --exec bash -lc 'node --version'` | R1: record the returned exit and output required by the recipe |
| R1 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| R1 | powershell | `wsl.exe --list --quiet` | read first: the throwaway name is listed, and it is not the real `<Name>` |
| R1 | powershell | `wsl.exe --terminate '<Name>'` | the throwaway distribution stopped; no other distribution stops |
| R1 | powershell | `wsl.exe --unregister '<Name>'` | the throwaway distribution removed, nothing else |
| R1 | powershell | `wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'` | on the surviving distribution: WSLInterop exists and /mnt/c/Windows/System32/cmd.exe /d /c ver launches with exit 0 |
| R1 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }` | a failure stops the block; R1's recovery records the observations and stops for review |
| R1 | powershell | `wsl.exe --list --verbose` | the throwaway name absent; the starred line equals W1's |
| R1 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| R1 | powershell | `wsl.exe --list --quiet` | read first: the throwaway name is listed, and it is not the real `<Name>` |
| R1 | powershell | `wsl.exe --terminate '<Name>'` | the throwaway distribution stopped; no other distribution stops |
| R1 | powershell | `wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-rehearsal.tar'` | the failed rehearsal saved before `--unregister` deletes its disk |
| R1 | powershell | `$LASTEXITCODE` | `0` |
| R1 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }` | no `throw`; a `throw` stops R1 with the name still registered |
| R1 | powershell | `(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-rehearsal.tar').Hash.ToLowerInvariant()` | the export's SHA-256, recorded in `rehearsal` |
| R1 | powershell | `(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-rehearsal.tar').Length` | the export's size in bytes, recorded in `rehearsal` |
| R1 | powershell | `wsl.exe --unregister '<Name>'` | the throwaway distribution removed, nothing else |
| R1 | powershell | `wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'` | on the surviving distribution: WSLInterop exists and /mnt/c/Windows/System32/cmd.exe /d /c ver launches with exit 0 |
| R1 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }` | a failure stops the block; R1's recovery records the observations and stops for review |
| R1 | powershell | `wsl.exe --list --verbose` | the throwaway name absent; the starred line equals W1's |
| R1 | sh | `test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver` | only after a failed removal check, natively on the survivor: the check again, its output recorded |
| R1 | sh | `ls /proc/sys/fs/binfmt_misc` | the registered formats, recorded: whether `WSLInterop` is among them |
| R1 | sh | `systemctl status systemd-binfmt.service --no-pager` | the unit's state and log lines, recorded; then stop for review and import or provision nothing |
| P1 | sh | `for RELEASE in 26.04.1 24.04.5; do` | both signed-sums arms, each in an empty temporary directory |
| P1 | sh | `SUMS_DIR="$(mktemp -d)"` | an empty temporary directory, also `gpgv`'s home |
| P1 | sh | `curl -fsSL -o "$SUMS_DIR/SHA256SUMS" "https://releases.ubuntu.com/$RELEASE/SHA256SUMS" \|\| exit 1` | P1: record the returned exit and output required by the recipe |
| P1 | sh | `curl -fsSL -o "$SUMS_DIR/SHA256SUMS.gpg" "https://releases.ubuntu.com/$RELEASE/SHA256SUMS.gpg" \|\| exit 1` | P1: record the returned exit and output required by the recipe |
| P1 | sh | `gpgv --homedir "$SUMS_DIR" --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg "$SUMS_DIR/SHA256SUMS.gpg" "$SUMS_DIR/SHA256SUMS"` | exit 0 and `Good signature` by `843938DF228D22F7B3742BC0D94AA3F0EFE21092`; `BAD signature` or a missing key stops the run |
| P1 | sh | `if [ "$?" -ne 0 ]; then exit 1; fi` | nonzero interop verification stops recovery |
| P1 | sh | `grep -F " *ubuntu-$RELEASE-wsl-amd64.wsl" "$SUMS_DIR/SHA256SUMS" \|\| exit 1` | each release's exact signed image line from the controlled pins |
| P1 | sh | `done` | P1: record the returned exit and output required by the recipe |
| P2 | sh | `RENDER_DIR="$(mktemp -d)"` | an empty temporary directory |
| P2 | sh | `python3 -c 'import string, sys; sys.stdout.write(string.Template(open(sys.argv[1], encoding="utf-8").read()).substitute(WSL_USER=sys.argv[2]))' adoption/templates/wsl/cloud-init.user-data.template '<WSL_USER>' > "$RENDER_DIR/<Name>.user-data"` | the bytes W3 writes, rendered in the workstation |
| P2 | sh | `cloud-init --version` | the workstation's cloud-init version, recorded |
| P2 | sh | `cloud-init schema -c "$RENDER_DIR/<Name>.user-data"` | `Valid schema` and exit 0; `Invalid user-data` (exit 1) stops the run |
| P2 | sh | `sha256sum "$RENDER_DIR/<Name>.user-data"` | the render's SHA-256, equal to W3's |
| P3 | sh | `sudo journalctl -k -b 0 --no-pager \| grep hv_storvsc \| grep -Evc 'registering driver hv_storvsc\|[Cc]ommand line:'` | the count, recorded as the baseline (a count of `0` makes the last `grep` exit 1) |
| P3 | sh | `sudo journalctl -k -b 0 --no-pager -o short-monotonic --no-hostname \| grep hv_storvsc \| grep -Ev 'registering driver hv_storvsc\|[Cc]ommand line:' \| tail -n 1` | the newest error line with its kernel time in brackets, or nothing |
| P3 | sh | `cat /proc/uptime` | the seconds since boot as the first number; minus the line's kernel time, an age under 3600 s stops the run (microsoft/WSL#41482) |
| P3 | sh | `swapon --show` | recorded; active swap is the issue's condition, not a failure by itself |
| W1 | powershell | `New-Item -ItemType Directory -Force -Path 'Z:\WSL\downloads'` | the folder for the transcript and the image exists |
| W1 | powershell | `$env:WSL_UTF8 = '1'` | wsl.exe writes UTF-8 instead of UTF-16 |
| W1 | powershell | `wsl.exe --version` | WSL version: 3.0.1 or later for a second systemd distribution; older stops before W4 or any W6 import |
| W1 | powershell | `wsl.exe --list --verbose` | the starred line is recorded as the default |
| W1 | powershell | `wsl.exe --list --quiet` | `<Name>` is not listed |
| W1 | powershell | `Test-Path -LiteralPath 'Z:\WSL\<Name>'` | `False` |
| W1 | powershell | `Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\<Name>.user-data')` | `False` |
| W1 | powershell | `Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml')` | `False`; when `True`, the next row decides |
| W1 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml') -Pattern '^[A-Za-z_][A-Za-z0-9_-]*:' -ErrorAction SilentlyContinue` | no output, or the top-level keys recorded and neither `users:` nor `write_files:` among them |
| W1 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig') -Pattern '^\s*\[', '^\s*instanceIdleTimeout\s*=', '^\s*vmIdleTimeout\s*=' -ErrorAction SilentlyContinue` | a read only: the section headers and the two idle keys, or nothing; recorded as `idle_keys` |
| W1 | powershell | `Get-PSDrive -Name Z \| Select-Object -Property Name, Used, Free` | `Free` recorded |
| W1 | sh | `id -u` | planned default uid 1000; otherwise stop before W4 or any W6 import |
| W1 | sh | `systemctl is-system-running` | running with no failed unit, or degraded with the failed set contained in {systemd-binfmt.service, getty@tty1.service}; otherwise stop |
| W1 | sh | `systemctl --failed --no-legend --plain` | first column of each row, or none; failed getty only as a prior collision with Result=start-limit-hit |
| W1 | sh | `systemctl is-active "user@$(id -u).service"` | active; otherwise stop before W4 or any W6 import |
| W1 | sh | `readlink /proc/self/ns/cgroup` | not cgroup:[4026531835], PROC_CGROUP_INIT_INO; necessary, with W5 required to prove isolation |
| W1 | sh | `systemctl show getty@tty1.service -p Result -p NRestarts` | only when the baseline includes failed getty: Result=start-limit-hit; record NRestarts in optional getty_tty1_result; another result stops |
| W2 | powershell | `$ProgressPreference = 'SilentlyContinue'` | no progress rendering during the download |
| W2 | powershell | `$Release = '<RELEASE>'` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `switch ($Release) {` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `'26.04.1' { $Expected = '48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104'; $CatalogName = 'Ubuntu-26.04' }` | the exact hash and catalog entry for the single clean-install default |
| W2 | powershell | `'24.04.5' { $Expected = 'bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e'; $CatalogName = 'Ubuntu-24.04' }` | the exact hash and catalog entry for the release-caused-failure rollback only |
| W2 | powershell | `default { throw 'unsupported release: do not download or install' }` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `}` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `$Image = "ubuntu-$Release-wsl-amd64.wsl"` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `$ImagePath = "Z:\WSL\downloads\$Image"` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `$ImageUrl = "https://releases.ubuntu.com/$Release/$Image"` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `$SumsPath = "Z:\WSL\downloads\$Release-SHA256SUMS"` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `Invoke-WebRequest -UseBasicParsing -Uri $ImageUrl -OutFile $ImagePath` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `Invoke-WebRequest -UseBasicParsing -Uri "https://releases.ubuntu.com/$Release/SHA256SUMS" -OutFile $SumsPath` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `$Published = (Select-String -LiteralPath $SumsPath -Pattern (' \*' + [regex]::Escape($Image) + '$')).Line.Split(' ')[0]` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `$Listed = ((Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/microsoft/WSL/8bc98bc33b246fe66710eec9eaa1b24c323da987/distributions/DistributionInfo.json').Content \| ConvertFrom-Json).ModernDistributions.Ubuntu \| Where-Object Name -eq $CatalogName` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ImagePath).Hash.ToLowerInvariant()` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `"computed $Actual published $Published listed $($Listed.Amd64Url.Sha256) url $($Listed.Amd64Url.Url)"` | the selected release's exact hash three times and its pinned release URL |
| W2 | powershell | `if ($Actual -ne $Expected -or $Published -ne $Expected -or $Listed.Amd64Url.Sha256 -ne $Expected -or $Listed.Amd64Url.Url -ne $ImageUrl) { throw 'sha256 mismatch: do not install' }` | no throw: whole-image, signed-publication, catalog hash and URL match |
| W2 | powershell | `(Get-Item -LiteralPath $ImagePath).Length` | actual selected-image byte count for this host run; run 2 observed 418,495,746 bytes for 26.04.1 |
| W3 | powershell | `New-Item -ItemType Directory -Force -Path (Join-Path $env:USERPROFILE '.cloud-init')` | the folder exists |
| W3 | powershell | `$Text = [System.IO.File]::ReadAllText('<checkout>\adoption\templates\wsl\cloud-init.user-data.template').Replace('${WSL_USER}', '<WSL_USER>')` | the template rendered in memory |
| W3 | powershell | `[System.IO.File]::WriteAllText((Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data'), $Text)` | UTF-8 without a byte order mark |
| W3 | powershell | `Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -TotalCount 1` | `#cloud-config` |
| W3 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -Pattern '^- name: ', '^    default='` | two lines ending in `<WSL_USER>` |
| W3 | powershell | `(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data')).Hash.ToLowerInvariant()` | equal to P2's `sha256sum` value |
| W3 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -SimpleMatch -Pattern '${'` | no output |
| W4 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W4 | powershell | `wsl.exe --install --from-file 'Z:\WSL\downloads\ubuntu-<RELEASE>-wsl-amd64.wsl' --name '<Name>' --location 'Z:\WSL\<Name>' --no-launch` | W4: record the returned exit and output required by the recipe |
| W4 | powershell | `$LASTEXITCODE` | `0` |
| W4 | powershell | `wsl.exe --list --verbose` | `<Name>` `Stopped`, version 2; the starred line unchanged |
| W5 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W5 | powershell | `cmd.exe /d /c "wsl.exe -d <Name> < NUL"` | Provisioning the new WSL instance <Name>; no prompt marker; wsl: Failed to start the systemd user session stops even with exit 0 |
| W5 | powershell | `$LASTEXITCODE` | `0`; nonzero with the markers means W6 |
| W5 | powershell | `wsl.exe -d '<Name>' --exec id -un` | `<WSL_USER>` |
| W5 | powershell | `wsl.exe -d '<Name>' --exec id -u` | `1000` |
| W5 | powershell | `wsl.exe -d '<Name>' --exec systemctl is-enabled getty@tty1.service` | masked; exit 1 is normal for a masked unit; otherwise W5 recovery |
| W5 | powershell | `wsl.exe -d '<Name>' --exec systemctl show getty@tty1.service -p LoadState -p ActiveState -p NRestarts` | LoadState=masked, ActiveState=inactive, NRestarts=0; otherwise W5 recovery |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init --version` | selected-image packaged cloud-init version; not the P2 workstation version |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init status --long` | `status: disabled` and `boot_status_code: disabled-by-marker-file`; proves the marker, not the run |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/result.json` | `"datasource": "DataSourceWSL"` and `"errors": []`: the run completed without errors |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/status.json` | each of the four stages `finished` with empty `errors`; `recoverable_errors` recorded |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init schema --system` | path A: a line matching `^\s*Valid schema user-data$` and exit 0; skipped on path B |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /etc/wsl.conf` | `[boot]`, `systemd=true`, `[user]`, `default=<WSL_USER>`, each once |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec ls -l /etc/cloud/cloud-init.disabled` | the marker exists |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec sudo -l -U '<WSL_USER>'` | `(ALL) NOPASSWD: ALL` |
| W5 | powershell | `wsl.exe --list --verbose` | the starred line equals W1's |
| W5 | sh | `systemctl is-active '<COMMON_UNIT>'` | natively on the already-running distribution: active and exit 0 |
| W5 | sh | `/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec systemctl is-active '<COMMON_UNIT>'` | the same system unit is active in the new distribution, exit 0 |
| W5 | sh | `cat '/sys/fs/cgroup/system.slice/<COMMON_UNIT>/cgroup.procs'` | read from the already-running distribution while both run: local process ids, no exact 0 entry; empty or unreadable stops |
| W5 | sh | `/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec sh -c 'systemctl is-active "user@$(id -u).service"'` | the new default user has uid 1000 and user@1000.service is active, exit 0; otherwise W5 recovery |
| W5 | sh | `id -u` | workstation uid, equal to host.workstation_baseline; record its own exit and printed value |
| W5 | sh | `systemctl is-system-running` | workstation system_state, equal to host.workstation_baseline; record its own exit and printed value |
| W5 | sh | `systemctl --failed --no-legend --plain` | workstation failed_units, equal to host.workstation_baseline; record its own exit and printed value |
| W5 | sh | `systemctl is-active "user@$(id -u).service"` | workstation user_manager, equal to host.workstation_baseline; record its own exit and printed value |
| W5 | sh | `readlink /proc/self/ns/cgroup` | workstation cgroup_namespace, equal to host.workstation_baseline; record its own exit and printed value |
| W5 | sh | `/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec id -u` | same uid as the workstation (1000) |
| W5 | sh | `/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec systemctl is-system-running` | running with no failed unit, or degraded with systemd-binfmt.service as its only failed unit; its message is proved at F1 |
| W5 | sh | `/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec systemctl --failed --no-legend --plain` | first column of each row, or none; getty@tty1.service must not be failed |
| W5 | sh | `/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec sh -c 'systemctl is-active "user@$(id -u).service"'` | new default user manager active; paired observation with its own exit |
| W5 | sh | `/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec readlink /proc/self/ns/cgroup` | different from the workstation namespace and not cgroup:[4026531835] |
| W5 | powershell | `$env:WSL_UTF8 = '1'` | W5: record the returned exit and output required by the recipe |
| W5 | powershell | `wsl.exe --list --quiet` | W5: record the returned exit and output required by the recipe |
| W5 | powershell | `wsl.exe --terminate '<Name>'` | any failed W5 proof: terminate the new distribution, never stop or restart a system unit in either distribution |
| W5 | powershell | `wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-w5-failed.tar'` | the failed W5 state saved before unregister; nonzero export prevents deletion |
| W5 | powershell | `$LASTEXITCODE` | W5: record the returned exit and output required by the recipe |
| W5 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }` | export failure stops with the name still registered; otherwise continue to hash, size and unregister |
| W5 | powershell | `(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-w5-failed.tar').Hash.ToLowerInvariant()` | record the export hash in w5_failure_export |
| W5 | powershell | `(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-w5-failed.tar').Length` | record the export size in w5_failure_export |
| W5 | powershell | `wsl.exe --unregister '<Name>'` | any failed W5 proof: guarded export succeeded; remove only the new distribution and immediately check surviving interop |
| W5 | powershell | `wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'` | on the surviving distribution: WSLInterop exists and /mnt/c/Windows/System32/cmd.exe /d /c ver launches with exit 0 |
| W5 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }` | a failure stops the block; R1's recovery records the observations and stops for review |
| W5 | powershell | `wsl.exe --list --verbose` | W5: record the returned exit and output required by the recipe |
| W5 | sh | `sudo journalctl -k -b 0 --no-pager \| grep hv_storvsc \| grep -Evc 'registering driver hv_storvsc\|[Cc]ommand line:'` | On both paths, record P3's baseline before the import and `second_count` after the first launch. An increase confined to the window in which the new disk is attached, before cloud-init starts, is recorded with the new lines and does not stop the run. Any storage error after that window, or any provisioning step that fails with a storage cause, stops the run. |
| W6 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W6 | powershell | `wsl.exe --list --quiet` | read before unregistering: `<Name>` is the new distribution |
| W6 | powershell | `wsl.exe --terminate '<Name>'` | `<Name>` stopped before the export; no other distribution stops |
| W6 | powershell | `wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-failed.tar'` | the failed attempt saved as a tar before `--unregister` deletes its disk |
| W6 | powershell | `$LASTEXITCODE` | `0` |
| W6 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }` | no `throw`; a `throw` stops W6 with `<Name>` still registered |
| W6 | powershell | `(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Hash.ToLowerInvariant()` | the export's SHA-256, recorded in `failed_attempt_export` |
| W6 | powershell | `(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Length` | the export's size in bytes, recorded in `failed_attempt_export` |
| W6 | powershell | `wsl.exe --unregister '<Name>'` | `<Name>` removed, nothing else |
| W6 | powershell | `wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'` | on the surviving distribution: WSLInterop exists and /mnt/c/Windows/System32/cmd.exe /d /c ver launches with exit 0 |
| W6 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }` | a failure stops the block; R1's recovery records the observations and stops for review |
| W6 | powershell | `wsl.exe --import '<Name>' 'Z:\WSL\<Name>' 'Z:\WSL\downloads\ubuntu-<RELEASE>-wsl-amd64.wsl' --version 2` | W6: record the returned exit and output required by the recipe |
| W6 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init status --wait --long` | `done` or `error` when cloud-init ran, `disabled` by `disabled-by-generator` when it found no datasource; recorded (open question 1) |
| W6 | sh | `systemctl mask --now getty@tty1.service` | the imported getty masked; first boot already started it, so W5 paired proof after relaunch must show workstation unchanged |
| W6 | sh | `id -u '<WSL_USER>' \|\| useradd --create-home --uid 1000 --groups adm,cdrom,sudo,dip,plugdev --shell /bin/bash '<WSL_USER>'` | uid 1000 exists |
| W6 | sh | `printf '%s ALL=(ALL) NOPASSWD:ALL\n' '<WSL_USER>' > /etc/sudoers.d/90-wsl-default-user` | the drop-in written |
| W6 | sh | `chmod 0440 /etc/sudoers.d/90-wsl-default-user` | mode 0440 |
| W6 | sh | `visudo -cf /etc/sudoers.d/90-wsl-default-user` | `parsed OK` |
| W6 | sh | `grep -q '^\[user\]' /etc/wsl.conf \|\| printf '\n[user]\ndefault=%s\n' '<WSL_USER>' >> /etc/wsl.conf` | one `[user]` section naming the user |
| W6 | sh | `touch /etc/cloud/cloud-init.disabled` | the marker exists |
| W6 | powershell | `wsl.exe --terminate '<Name>'` | exit 0 |
| W6 | powershell | `wsl.exe --list --running` | `<Name>` absent |
| W6 | powershell | `wsl.exe -d '<Name>' --exec id -un` | `<WSL_USER>`; then W5's checks, without `cloud-init schema --system` |
| W7 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W7 | powershell | `wsl.exe --terminate '<Name>'` | `<Name>` stopped once after the first launch (microsoft/WSL#40941); no other distribution stops |
| W7 | powershell | `wsl.exe --list --running --quiet` | `<Name>` absent |
| W7 | powershell | `wsl.exe -d '<Name>' --exec id -un` | `<WSL_USER>`: relaunched for the F steps |
| W7 | powershell | `New-Item -ItemType File -Path '\\wsl.localhost\<Name>\home\<WSL_USER>\wsl-owner-probe'` | an empty file created from Windows under the user's home |
| W7 | powershell | `wsl.exe -d '<Name>' --exec stat -c %u:%g '/home/<WSL_USER>/wsl-owner-probe'` | `1000:1000`; `0:0` is recorded and stops every write from Windows |
| W7 | powershell | `Remove-Item -LiteralPath '\\wsl.localhost\<Name>\home\<WSL_USER>\wsl-owner-probe'` | the probe file deleted |
| F1 | sh | `systemctl is-system-running --wait` | `running` with no failed unit; or `degraded` (exit 1) only when the next two rows show `systemd-binfmt.service` as the only failed unit, with its read-only flush message |
| F1 | sh | `systemctl --failed --no-legend --plain` | no output when `running`; when `degraded`, a list of exactly `systemd-binfmt.service`; any other failed unit stops the run |
| F1 | sh | `journalctl -b 0 -t systemd-binfmt --no-pager -n 4` | when `degraded`: the unit's log holds `Failed to flush binfmt_misc rules, ignoring: Read-only file system`; read without `sudo` through the `adm` group, or repeated once with `sudo` when only the journal's permission notice prints |
| F1 | sh | `systemctl list-unit-files --type=service --no-pager` | the service list prints |
| F1 | sh | `sudo journalctl -b 0 -t systemd-binfmt --no-pager -n 4` | only after an unreadable degraded journal: record both outputs and judge this read-only flush message |
| F2 | sh | `sudo loginctl enable-linger "$(id -un)"` | exit 0 |
| F2 | sh | `loginctl show-user "$(id -un)" --property=Linger --value` | `yes` |
| F2 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| F2 | powershell | `foreach ($Poll in 1..12) { Start-Sleep -Seconds 10; [DateTime]::UtcNow.ToString('HH:mm:ss'); wsl.exe --list --running --quiet }` | twelve times and lists with no client attached; whether `<Name>` stays listed, recorded as `idle_observation` |
| F3 | sh | `stat -c '%U %F' "/run/user/$(id -u)" "/run/user/$(id -u)/bus"` | `<WSL_USER> directory`, then `<WSL_USER> socket` |
| F3 | sh | `systemctl --user is-system-running --wait` | `running` |
| F3 | sh | `docker --context rootless info --format '{{json .SecurityOptions}}'` | exit 0 and name=rootless before attempting the container; otherwise stop |
| F3 | sh | `docker --context rootless run --rm hello-world` | as the user without sudo: Hello from Docker! and exit 0; failure stops with issue 41492; owed on the first run after update |
| F4 | sh | `sudo apt-get update` | exit 0 |
| F4 | sh | `sudo apt-get install -y --no-install-recommends ca-certificates curl git tar gzip xz-utils jq libatomic1 uidmap` | exit 0 |
| F4 | sh | `dpkg-query -W -f='${Package} ${Version}\n' jq libatomic1 uidmap` | three versions |
| F5 | sh | `grep "^$(id -un):" /etc/subuid /etc/subgid` | a range in both files, or nothing |
| F5 | sh | `grep -q "^$(id -un):" /etc/subuid \|\| sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$(id -un)"` | only when the first `grep` printed nothing |
| F5 | sh | `grep "^$(id -un):" /etc/subuid /etc/subgid` | 65,536 ids in both files |
| F6 | sh | `test -e ~/.bash_profile \|\| printf '%s\n' 'if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi' > ~/.bash_profile` | written only when absent |
| F6 | sh | `cat ~/.bash_profile` | exactly the hand-off line |
| F7 | sh | `mkdir -p ~/code` | exit 0 |
| F7 | sh | `git clone https://github.com/seathatflowsinourveins/native-agent-stack.git ~/code/native-agent-stack` | exit 0 |
| F7 | sh | `git -C ~/code/native-agent-stack rev-parse HEAD` | a commit |
| F7 | sh | `git -C ~/code/native-agent-stack ls-remote origin refs/heads/main` | the same commit |
| F8 | sh | `cd ~/code/native-agent-stack` | the clone |
| F8 | sh | `ss -ltnH '( sport = :24318 or sport = :29374 or sport = :26333 or sport = :28231 )'` | no output |
| F8 | sh | `python3 -c 'import string, sys; sys.stdout.write(string.Template(open(sys.argv[1], encoding="utf-8").read()).substitute(WSL_USER=sys.argv[2]))' adoption/templates/wsl/host.new-distro.json.template "$(id -un)" > 'adoption/hosts/<host>.json'` | the host file written |
| F8 | sh | `python3 -m json.tool 'adoption/hosts/<host>.json'` | the nine keys |
| F8 | sh | `git check-ignore 'adoption/hosts/<host>.json'` | prints the path |
| F9 | sh | `cd ~/code/native-agent-stack` | the clone |
| F9 | sh | `adoption/bootstrap-linux.sh --profile '<id>'` | stage 2 (bootstrap step 2) |
| F9 | sh | `adoption/bootstrap-linux.sh --profile '<id>' --configure-full-profile --host '<host>'` | stage 2, after native sign-in |
| F10 | powershell | `wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'type -P claude codex'` | two absolute paths |
| F10 | powershell | `wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'for n in claude codex; do p=$(type -P $n); [[ -f $p && -x $p ]] && echo executable: $p; done'` | `executable:` and each path: both are regular executable files |
| F11 | sh | `test -x "${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/jcodemunch-mcp"` | exit 0; exit 1 means `not installed`: record it and skip the rest of F11 |
| F11 | sh | `cd ~/code/native-agent-stack` | the clone, the project the local scope belongs to |
| F11 | sh | `claude mcp add --scope local jcodemunch -e "CODE_INDEX_PATH=$HOME/.code-index" -e JCODEMUNCH_SHARE_SAVINGS=0 -- "${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/jcodemunch-mcp"` | an `Added ...` line; on a re-run the name already exists |
| F11 | sh | `claude mcp get jcodemunch` | the local scope, the command and a status, recorded as `jcodemunch_registration` |

## Open questions

Each one stays open until a host run records the observation named here.

1. **cloud-init on an imported distribution.** Whether cloud-init provisions an `--import`ed distribution is not
   documented. Path B records `cloud-init status --wait --long` before it creates anything.
2. **What keeps the distribution running with no client attached.** This workstation's global WSL configuration holds
   `[general] instanceIdleTimeout=-1` and `[wsl2] vmIdleTimeout=-1` (the coordinator's read of 2026-10-01, 10:08Z,
   values only), and the new distribution inherits them. By the WSL 2.7.13 source (`LxssUserSession.cpp:2658-2676`) a
   negative value means the instance is never idle-terminated, so on this host the setting keeps `<Name>` running, not
   linger. Issue reports say linger alone does not: microsoft/WSL#13416 (open; on WSL 2.7.3.0 "`loginctl enable-linger`
   ... does not prevent the poweroff") and #9968 (open). On a host without the setting, the distribution stops about
   `instanceIdleTimeout` (default 15000 ms, wsl-config) after its last Windows-side client exits, its user services
   with it; changing the global file is the user's decision, outside the recipe. W1 records both keys, and F2 lists the
   running distributions for two minutes with no client attached and records whether `<Name>` stays listed. Whether
   `wsl.exe --list --running` itself counts as a client is not verified.
3. **Interop after unregister.** On WSL 2.7.13 the surviving distribution lost the VM-wide `WSLInterop` registration
   after the failed rehearsal was unregistered. Restarting its `systemd-binfmt` restored Windows execution there. Every
   R1, W5 and W6 unregister now checks the registration and a Windows executable. On the adopted release the
   registration is protected (microsoft/WSL#40621) and that restart exits 1, so a failed check stops for review with
   R1's records. This is a required observation and a stop, rather than an open binfmt question.
4. **Subordinate ids from `useradd`.** Whether `useradd` allocated subordinate ids on the selected release. cloud-init 26.1 creates
   users with `useradd` (`cloudinit/distros/__init__.py:683` at tag 26.1). useradd(8) says it allocates `SUB_UID_COUNT`
   ids when `/etc/subuid` exists, and the image ships both; F5 records which tool wrote the range.
5. **Both image comparisons.** The preregistered R1 criteria cover the 26.04.1 default and 24.04.5 rollback on
   throwaway names. Full acceptance on the updated host remains owed; the older 24.04.5 receipts do not settle it.
6. **File ownership after a terminate (microsoft/WSL#40941).** Whether `wsl --terminate <Name>` clears the 0:0 owner of
   files Windows creates after the first-run setup. The fix's pull request says the state "only recovers after a distro
   termination", and the issue's reproduction says it lasts "until the next wsl --shutdown". The 2.7.13 rehearsal
   returned `1000:1000` after W7's terminate; the updated host must repeat that observation.
7. **Kernel storage errors on this host (microsoft/WSL#41482).** Whether `hv_storvsc` errors break a first launch on
   this kernel. On 2026-10-01 P3's count in the workstation's journal of the current boot was 21 (Evidence classes):
   one burst of `cmd 0x2a` write errors (`WRITE_10`) on 2026-09-24 around 03:20Z and none since, where the issue shows
   `cmd 0x28` read errors (`READ_10`). Under the coordinator's rule that count is P3's baseline, and its newest line,
   about 7.4 days old, did not stop that authoring check. The later rehearsal's baseline 7 and second count 13 retain
   their own boot scope; the six new lines preceded cloud-init in the attachment window. Future runs must establish
   their own window, retain its lines and stop on later errors or a provisioning failure with a storage cause.
8. **Isolation with two distributions running on 3.0.1.** Whether the two distributions have distinct cgroup
   namespaces, healthy managers and the same uid while both run. The updated host's reading covers one distribution
   only (Updated-host correction). W5's paired record, `paired_isolation`, is the observation that settles it, and W1's
   baseline shows whether the new distribution disturbed the workstation's values.

## Completeness critic (2026-10-01)

The unit closed without the critic that the repository rule requires; a review thread on PR #569 pointed it out. An
independent researcher (Claude Opus, read-only, primary sources fetched 2026-10-01) then asked what the unit did not
look at: candidate classes, kinds of evidence and unread sources. It read about 30 sources and found 11 items. None
overturns the selection. Five change what must happen before stage 1. The follow-up of 2026-10-01 adds their checks to
the recipe (last column); do not run stage 1 without the checks of items 1 to 5.

| # | What the unit missed | Source read 2026-10-01 | Disposition | Outcome in the follow-up (2026-10-01) |
| --- | --- | --- | --- | --- |
| 1 | No dry run. Stage 1 and first boot have never run anywhere; a rehearsal on a throwaway name and location stays inside this record's host-wide rules | this record, "Evidence classes" | Queued before stage 1: a rehearsal that also collects items 2, 3 and 4 | R1: the page runs first on a throwaway name through F3, with W5's schema check, W7's probe and F2's idle observation in the receipt's `rehearsal` block; R1 then removes only that name |
| 2 | The claim that WSL 2.7.14 and 3.0.1 "change nothing about install, import or first run" is broader than what was checked. `2.7.13...3.0.1` is 677 commits ahead, and listed commits touch first run, import and termination. One of them fixes microsoft/WSL#40941: after the first-run setup, a file created from Windows is owned by 0:0 until the next `wsl --shutdown`, which this recipe forbids. That 2.7.13 lacks the fix is now established from source: the fix's function, `ConnectionTargetManager::UpdateUid`, is absent from `src/windows/common/Redirector.h` at tags 2.7.13 and 2.7.14 | https://github.com/microsoft/WSL/compare/2.7.13...3.0.1 ; https://github.com/microsoft/WSL/issues/40941 | Open question; measured in the rehearsal (create a file from Windows under the user's home, read its owner, terminate the distribution, relaunch, read it again) | Context and the recipe's host-wide rules corrected; W7 terminates `<Name>` once after the first launch, relaunches it and requires `1000:1000` for a file created from Windows; open question 6 |
| 3 | The issue tracker was not searched for the selected path. microsoft/WSL#41482 reports continuous `hv_storvsc` read errors and systemd boot timeouts on Ubuntu 24.04 with kernel 6.18.33.2, this host's kernel; the maintainer's workaround needs `swap=0` and `wsl --shutdown`, both ruled out here | https://github.com/microsoft/WSL/issues/41482 | Open question; a read-only pre-check in the current distribution (`journalctl -k` for `hv_storvsc`) before stage 1, since both share the kernel | P3 records the current boot's `hv_storvsc` journal count without the registration line as a baseline, stops on an error line less than one hour old by its kernel time and records `swapon --show`; W5 counts again after the first launch. On this host the baseline is 21, from one burst seven days old (Evidence classes, open question 7) |
| 4 | Whether linger keeps the distribution running. microsoft/WSL#13416 (open: WSL shuts down despite an active systemd service, still reproduced on 2.7.3) and #9968 (open) bear on open question 2 | https://github.com/microsoft/WSL/issues/13416 ; https://github.com/microsoft/WSL/issues/9968 | Open question; observed in the rehearsal with no client attached, because stage 2's user services depend on it | W1 reads the two idle keys; F2 lists the running distributions for two minutes with no client attached; open question 2 rewritten with the setting, the source and the issues |
| 5 | Two upstream verification steps are skipped: Canonical's how-to validates the user data with `sudo cloud-init schema --system`, and `SHA256SUMS.gpg` exists and is never verified (the repository's 2026-09-21 precedent verified Ubuntu's signed sums) | https://documentation.ubuntu.com/wsl/stable/howto/cloud-init/ ; https://releases.ubuntu.com/24.04.5/SHA256SUMS.gpg | Queued before stage 1: both become recipe steps in the follow-up | P1 verifies the signed sums with `gpgv`; P2 runs `cloud-init schema -c` before any boot, its hash compared with W3's; W5 runs `cloud-init schema --system` on path A |
| 6 | Other base images were not weighed. Microsoft's distribution list also carries Debian, Fedora, Arch, AlmaLinux, openSUSE, SLE and Kali; stage 2 accepts only `ID=ubuntu` or `debian` (`adoption/bootstrap-linux.sh:175-178`) | https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json | Debian feeds the layer's next landscape sweep; the others are out of scope while stage 2 rejects their `ID` | Alternatives 1 states both |
| 7 | WSL containers, generally available with 3.0.1 (one VM, network and disk per session, OCI images), were not weighed for disposable clean-install tests | https://devblogs.microsoft.com/commandline/wslc-architecture-deep-dive/ | Feeds the layer's next landscape sweep; unlikely to host stage 2 | Alternatives 1 states it |
| 8 | The reason given for dismissing `wsl --install Ubuntu-24.04` ("verifies no hash the operator can see") is incomplete: 2.7.13 carries a hash-mismatch message, and a local manifest can be pinned through `DistributionListUrl` | https://raw.githubusercontent.com/microsoft/WSL/2.7.13/localization/strings/en-US/Resources.resw ; https://learn.microsoft.com/en-us/windows/wsl/build-custom-distro | Open question; the selection stands because the online path resolves the list at install time and the registry key is host-wide; the follow-up corrects the stated reason | Alternatives 1 corrected from source (the online path checks the catalog's hash, `--from-file` checks none); the recipe's W2 says why its own check exists |
| 9 | Creation routes not weighed: a golden copy (`wsl --export`, then `--import-in-place` of a provisioned disk), a Docker-exported root file system, a custom first-run command in `/etc/wsl-distribution.conf`, Ubuntu Pro for WSL | https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro ; https://docs.cloud-init.io/en/latest/reference/datasources/wsl.html | The golden copy feeds the next sweep; a self-built image is out of scope (it breaks the upstream-install rule) and Ubuntu Pro needs a subscription and a server | Alternatives 1 and 2 state the exclusions and the sweep item |
| 10 | Package updates between the image build and today were not checked. They are harmless today: `wsl-setup` is unchanged, and cloud-init 26.2 is only proposed | Launchpad, published sources of both packages on noble | Feeds the next sweep | No change |
| 11 | Citation hygiene in a sample of eight: two Microsoft pages, use-custom-distro and systemd, display a date that matches neither of their metadata dates, the cloud-init datasource page is cited at `latest` (26.2 today) while the image runs 26.1, and W5's expected console lines have no cited source | the pages' own metadata | Open question; the follow-up pins each page by its revision and cites the lines | Sources pin the Microsoft Learn pages by `git_commit_id` and the cloud-init CLI page at 26.1; W5's lines are cited at the image's `wsl-setup` (Context) |

Not checked by the critic: file-level WSL source diffs (the comparison view is truncated), whether `wsl --terminate`
clears the ownership bug, the contents of the other images, upstream test suites and community runbooks. Its issue
searches were samples of eight results per query, not sweeps.

## Evidence classes

- **Read today (source review).** The WSL source at tag 2.7.13; `ubuntu/wsl-setup` at
  `86a561d5149a9d76ec3c9b3ce2745e7ebca5f2ad`, GitHub main when the research unit read it
  (`test/systemd-assertions.sh:6-9` asserts `running`, `:30-33` the marker; these two citations are at that revision
  and were not checked at the image's version);
  systemd v255 `man/loginctl.xml:186-194` and `man/systemctl.xml:2297-2307`; and the documentation below. For the
  follow-up: step 4a and the addendum, the carrier blocks, the MCP template, the profiles and the Linux pins, Claude
  Code's MCP page and Docker's rootless troubleshooting page.
- **Artifact checks on the authoring host, 2026-10-01** (not runs of the recipe):
  - the image stream's size and sha256, and the files read from it;
  - the gzip size field;
  - the Node 24.21.0 tarball's sha256 and its binary's `NEEDED` list.
- **Artifact checks of the second follow-up unit, 2026-10-01**, in the workstation distribution (Ubuntu 24.04.5 LTS,
  kernel 6.18.33.2): not runs of the recipe on a new distribution, and they changed nothing on the host. The unit ran
  P1 to P3 verbatim from 11:50:17Z to 11:50:19Z, and P3 again in its final form at 12:19:29Z, extracted from the page
  with `<WSL_USER>` as `example` and `<Name>` as `rehearsal-example`, `TMPDIR` in its scratch area and `sudo` without
  a prompt, each command followed by its exit code:
  - P1 for 24.04.5 in that earlier recipe: both `curl` lines exited 0. The `gpgv` line exited 0:
    `gpgv --homedir "$SUMS_DIR" --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg "$SUMS_DIR/SHA256SUMS.gpg" "$SUMS_DIR/SHA256SUMS"`
    printed `Signature made Tue Sep 15 15:11:12 2026 EDT`, `using RSA key 843938DF228D22F7B3742BC0D94AA3F0EFE21092` and
    `Good signature from "Ubuntu CD Image Automatic Signing Key (2012) <cdimage@ubuntu.com>"`. The `grep` exited 0 and
    printed `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e *ubuntu-24.04.5-wsl-amd64.wsl`. Control:
    a copy of the sums with that line's first hash digit changed gave `BAD signature from ...`, exit 1. Afterwards the
    directory held only the two downloads and the control's copy, so `gpgv` wrote nothing to its home. The sums file
    has 9 lines; the SHA-256 of the sums file and of the signature:
    `728064ecf411f4ab702d9c3ca0a938ce672771424c028a1b52b2449f7eb5a068` and
    `f9be4b4a527b63f14dde0387edcb7a02ba3ac43d537b1674a5aeae19c6f23827`.
    `gpgv` 2.4.4-2ubuntu17.6 and `ubuntu-keyring` 2023.11.28.1.
  - P2: the render exited 0, and `cloud-init --version` printed cloud-init 26.1-0ubuntu1~24.04.1.
    `cloud-init schema -c` on the render printed `Valid schema <file>` after the warning `datasource not detected,
    using default instance-data/user-data paths.`, exit 0. The render's SHA-256 for `example` (another
    `<WSL_USER>` gives another value):
    `9ae3b7ba94ba36af78b4b0ce1b088ff92dac48ec9596223a640923dce07550f7`.
    Control: `lock_passwd: "maybe"` printed
    `Error: Cloud config schema errors: users.0.lock_passwd: 'maybe' is not of type 'boolean'`,
    `Error: Invalid schema: user-data` and `Invalid user-data <file>`, exit 1. An earlier run at 11:26Z also found the
    render equal to the template with a literal replace, without CR bytes and with `#cloud-config` first.
  - P3 under the coordinator's rule, its four lines run verbatim from the page at 12:19:29Z (and the same commands
    at 12:13:46Z with the same count and newest line). The count line,
    `sudo journalctl -k -b 0 --no-pager | grep hv_storvsc | grep -vc 'registering driver hv_storvsc'`, printed `21`
    (exit codes 0, 0 and 0): the baseline. The newest-line command,
    `sudo journalctl -k -b 0 --no-pager -o short-monotonic --no-hostname | grep hv_storvsc | grep -v 'registering driver hv_storvsc' | tail -n 1`,
    printed `[52879.587119] kernel: hv_storvsc <device>: tag#2687 cmd 0x2a status: scsi 0x0 srb 0x4 host 0xc00000a1`
    (exit codes 0, 0, 0 and 0; the device id is masked here). `cat /proc/uptime` printed `690053.56` as its first
    number, so the newest error line was about 637,174 s, 7.4 days, old: older than one hour, so P3 does not stop the
    run, and 21 is a baseline. `swapon --show` printed one 24G swap partition with 4.2G used (exit 0). W5's count line,
    the same command, also printed `21`, but no first launch had run, so that only checks the command: no second reading
    exists yet.
  - The first form of P3, the count alone with a stop on any count, printed `21` at 11:37:00Z and 11:50:19Z, and the
    form the brief first gave, `grep -c hv_storvsc`, printed 24 at 11:26:38Z (exit 0). The unit then split those lines
    (`sudo -n`, ids masked): 3 were `hv_vmbus: registering driver hv_storvsc`, one kernel message with one monotonic
    stamp that journald stored again after the workstation distribution restarted within this kernel boot. Every boot
    logs that line, so the page leaves it out. The other 21 were
    `hv_storvsc <device>: tag#<n> cmd 0x2a status: scsi 0x0 srb 0x4 host 0xc00000a1`: 14 distinct monotonic stamps
    within 47 ms, about 52,880 s after the kernel booted (2026-09-24 around 03:20Z), and none in the seven days since.
    `cmd 0x2a` is `WRITE_10`, where the issue's `cmd 0x28` is `READ_10` (`/usr/include/scsi/scsi.h:59-60`, libc6-dev).
    Under a stop on any count, that one old burst would have blocked stage 1 on this host for good; this is why the
    coordinator rejected the bare count as the rule (Alternatives 4).
  - Why the kernel time decides the age: the registration message, one kernel time, carries three journal reception
    stamps from 2026-09-24 03:20:59Z to 04:23:09Z, and the burst's error lines were received at 03:20:59Z and again at
    04:23:09Z (`-o short-iso --no-hostname`, 12:13:46Z). On this host the kernel clock and `/proc/uptime` agree within
    37 s over about 8 days: the newest kernel line's kernel time, 689,242.966 s, against its reception time at 12:13Z.
    The one-hour threshold is this recipe's choice, not an upstream figure; microsoft/WSL#41482 names no age.
- **Local integration.** `tests/test_wsl_new_distro_recipe.py`, checks over repository text and an in-memory render; it
  runs nothing on a host.
- **Reported artifact verification, W-IMG.** The retained integration receipt contains both signature verification
  exit codes, the signer fingerprint and the reported 26.04.1 stream hash match. It retains no verification output
  for that 26.04.1 signature check; it does not carry the signature-output evidence of the historical 24.04.5 P1
  check above.
- **Retained rehearsal, 2026-10-02.** The separate stage-1 receipt records Ubuntu 26.04.1's schema, install, launch
  and owner results on WSL 2.7.13, then F1's failed user manager. Its coordinator review establishes the shared
  cgroup diagnosis. The later unregister/interop observations and the initial namespace observation are retained in
  the supplied repair brief; they are not invented as output in the earlier worker receipt.
- **Reported host observation, 2026-10-02.** The coordinator's brief gives the five reads of the Updated-host
  correction, taken on WSL 3.0.1.0 with kernel 6.18.40.1-1 in the workstation's distribution from 06:39Z to 06:57Z. They
  cover one distribution and are not a run of the recipe. The third follow-up's unit repeated the five commands in the
  same distribution afterwards and read the same values: `1000`; `degraded` with exit 1; `systemd-binfmt.service` as
  the only failed unit; `active`; `cgroup:[4026532183]`. It also ran
  `journalctl -b 0 -t systemd-binfmt --no-pager | tail -n 4` as that distribution's default user, who is not in
  `adm`, and read only the notice that other users' and the system's messages are hidden, which is why F1 states its
  dependence on `adm` and repeats the line once with `sudo` when only that notice prints. Nothing was observed with two
  distributions running.
- **Not run.** The corrected recipe on WSL 3.0.1 with a second distribution, including W5's paired record, F1's accepted
  `degraded` and a rootless container in the new distribution, remains owed.
  F11 rests on a source read and has not run on a new distribution. The addendum records a run of the same command
  form on 2026-09-25, under a temporary `CLAUDE_CONFIG_DIR` on one WSL2 host.
- **Cross-family review.** GPT-6.1 Sol, read-only, 2026-10-01, of PR #569, returned `needs_changes` with three findings.
  All three were fixed against the cloud-init 26.1 source above, and `tests/test_wsl_new_distro_recipe.py`
  `CrossFamilyReviewTests` keeps them fixed:
  - W5 expected `status: done` after the marker exists; it now expects `disabled-by-marker-file` and reads
    `result.json` and `status.json`, and W6 does the same.
  - W1 did not check `agent.yaml`.
  - F10 trusted `type -P` alone.

## Sources

Read on 2026-10-01 by the research unit only, and cited here as it reported them:

- `wsl.exe --version` and `wsl.exe --help` on the Windows host: WSL 2.7.13.0, kernel 6.18.33.2-2, the command forms in
  Context.
- https://github.com/microsoft/WSL/releases/tag/2.7.14 (2026-09-11; backports #41524, #41540, #41557 and #41569) and
  https://github.com/microsoft/WSL/releases/tag/3.0.1 (2026-09-29; WSL containers generally available; #41657, #41688
  and #41689). Also the `microsoft/WSL` source at tags 2.7.13, 2.7.14 and 3.0.1, including `LxssUserSession.cpp:1597`
  and `:1682` and `src/linux/init/main.cpp:2656-2669`.
- https://releases.ubuntu.com/resolute/SHA256SUMS (2026-08-27) and the contents of the Ubuntu 26.04.1 image:
  - `python3` 3.14.3;
  - uutils coreutils;
  - `sudo-rs` beside `sudo`;
  - `bubblewrap` and `libatomic1` present.
- https://cloud-images.ubuntu.com/wsl/ (WSL image publication moved to cdimages; those rootfs tarballs are not
  general-purpose).

Read on 2026-10-01 by the research unit or by unit W2. The dates of the Microsoft Learn pages are their displayed "last
updated" values. The second follow-up's researcher read each page's `git_commit_id` that day, and the WSL pages are
pinned to it below; the unit fetched each pinned raw file (HTTP 200).

- Microsoft:
  - https://learn.microsoft.com/en-us/windows/wsl/build-custom-distro (`oobe.command`, `oobe.defaultUid`; the
    `uid`/`defaultUid` 1000 recommendation; `--install --from-file`; WSL 2.4.4; displayed 2025-09-12), pinned at
    https://github.com/MicrosoftDocs/WSL/blob/7b28cc1ee9b8ff672ada5e1c6c326d3573d703e5/WSL/build-custom-distro.md
  - https://learn.microsoft.com/en-us/windows/wsl/basic-commands (`--install` options including `--location` and
    `--no-launch`; displayed 2025-12-01), pinned at
    https://github.com/MicrosoftDocs/WSL/blob/7b28cc1ee9b8ff672ada5e1c6c326d3573d703e5/WSL/basic-commands.md
  - https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro (`--import` starts as root; user and `[user] default`;
    `wsl --terminate`; displayed 2024-07-16, which matches neither its `ms.date`, 2021-09-27, nor its `updated_at`,
    2026-06-02), pinned at
    https://github.com/MicrosoftDocs/WSL/blob/7b28cc1ee9b8ff672ada5e1c6c326d3573d703e5/WSL/use-custom-distro.md
  - https://learn.microsoft.com/en-us/windows/wsl/wsl-config ("The 8 second rule"; `[user] default`;
    `instanceIdleTimeout` 15000; `distributionInstallPath`; displayed 2026-09-16), pinned at
    https://github.com/MicrosoftDocs/WSL/blob/7ea1c6f9e25f1c89a05a0e97e5325a02a66ac6cd/WSL/wsl-config.md
  - https://learn.microsoft.com/en-us/windows/wsl/systemd (`systemctl status` and
    `systemctl list-unit-files --type=service`; displayed 2025-03-17, which matches neither its `ms.date`, 2025-01-13,
    nor its `updated_at`, 2026-06-02), pinned at
    https://github.com/MicrosoftDocs/WSL/blob/7b28cc1ee9b8ff672ada5e1c6c326d3573d703e5/WSL/systemd.md
  - https://learn.microsoft.com/en-us/windows/wsl/disk-space (`ext4.vhdx` location; 1 TB default maximum)
  - https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/get-filehash (default `SHA256`)
  - https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1
    (Windows PowerShell's `UTF8` writes a BOM)
  - https://learn.microsoft.com/en-us/dotnet/api/system.io.file.writealltext (UTF-8 without a BOM)
  - https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.host/start-transcript?view=powershell-5.1
    (`-LiteralPath`, `-Append`)
  - https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/cmd (`/c`, `/d`)
  - https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-xp/bb490982(v=technet.10) (`<` reads input
    from a file)
  - https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions (fragment profile GUIDs from the
    application and profile names; displayed 2025-11-12), whose `git_commit_id` is
    `eef3334aa62933c168521f13ab2cca28c9d93c47` in `MicrosoftDocs/terminal`; its file path there was not read
  - disk-space and the PowerShell, .NET and Windows Server pages were not read again and stay unpinned.
- Canonical and Ubuntu:
  - https://documentation.ubuntu.com/wsl/stable/howto/cloud-init/ (`%USERPROFILE%\.cloud-init\<instance>.user-data`; the
    NOPASSWD user example). It now redirects to https://ubuntu.com/wsl/docs/stable/howto/cloud-init/, "Last updated on
    Mar 17, 2026", whose check after provisioning is `sudo cloud-init schema --system` with the output
    `Valid schema user-data` (the second follow-up's researcher, 2026-10-01).
  - https://documentation.ubuntu.com/wsl/stable/howto/install-ubuntu-wsl2/ (Method 1, WSL 2.4.10)
  - https://ubuntu.com/blog/ubuntu-wsl-new-format-available (WSL 2.4.8; `wsl --install --from-file`)
  - https://releases.ubuntu.com/24.04.5/SHA256SUMS and https://releases.ubuntu.com/noble/SHA256SUMS
  - https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl (streamed and hashed)
  - https://manpages.ubuntu.com/manpages/noble/en/man8/useradd.8.html (`SUB_UID_COUNT` allocation)
  - https://manpages.ubuntu.com/manpages/noble/en/man8/usermod.8.html (`--add-subuids`, `--add-subgids`)
  - https://github.com/ubuntu/wsl-setup at `86a561d5149a9d76ec3c9b3ce2745e7ebca5f2ad`, GitHub main when read: the
    revision of the `test/systemd-assertions.sh` citations; W5's console lines sit there at lines 122-123
  - https://git.launchpad.net/ubuntu/+source/wsl-setup/tree/wsl-setup?id=74bfc89113bc7d46a4d9feb1e69cd6951fbc6908#n117,
    tag `import/0.5.10_24.04.2`, the image's version: W5's console lines at 117-118 (the second follow-up's researcher)
- cloud-init:
  - https://docs.cloud-init.io/en/latest/reference/datasources/wsl.html (lookup order, Landscape precedence,
    requirements, the default-user example). `latest` renders the 26.2 documentation today (completeness critic); the
    26.1 page was not fetched, so this citation stays at `latest`.
  - https://docs.cloud-init.io/en/latest/reference/modules.html (Users and Groups: `uid`, `lock_passwd` default `true`,
    `sudo`; also at `latest`, its 26.1 page not fetched)
  - https://docs.cloud-init.io/en/26.1/reference/cli.html, titled "CLI commands - cloud-init 26.1 documentation"
    (`status --long`, exit codes 0, 1 and 2; `--system`: "Validate the system cloud-config user-data"; read at 26.1 by
    the second follow-up's researcher, after the research unit read it at `latest`)
  - https://github.com/canonical/cloud-init at tag `26.1` (`8bf3567532b07e2cc15aa4c76c36ebed65ccfaec`):
    - `cloudinit/distros/__init__.py:662-684` (`add_user` runs `useradd`)
    - `cloudinit/cmd/status.py:25-68, 83-88, 232-307, 381-392, 407-419, 459-527` (marker and generator boot codes,
      `disabled` running status, `detail` and `errors` from the `/run` copy, exit codes)
    - `cloudinit/cmd/main.py:880-1032, 1312-1368, 1400-1404` (`status.json` and `result.json` in `/var/lib/cloud/data`)
    - `cloudinit/sources/DataSourceWSL.py:241-355, 435-491` (Ubuntu Pro file loading and the `agent.yaml` merge)
    - `cloudinit/sources/__init__.py:398-399` and `cloudinit/type_utils.py:21-28` (the datasource's string name)
- Microsoft WSL, Docker and systemd:
  - https://github.com/microsoft/WSL at tag 2.7.13 (`80697fd42cca3de0c0d5dd1931c36112372a577e`):
    `src/windows/common/WslClient.cpp`, `src/windows/service/exe/LxssUserSession.cpp`,
    `src/windows/service/exe/WslCoreInstance.cpp`, `src/linux/init/init.cpp`, `src/linux/init/main.cpp` and
    `localization/strings/en-US/Resources.resw`
  - https://github.com/microsoft/WSL/blob/8bc98bc33b246fe66710eec9eaa1b24c323da987/distributions/DistributionInfo.json
  - https://docs.docker.com/engine/security/rootless/ (`uidmap`; at least 65,536 subordinate ids;
    `loginctl enable-linger`)
  - https://github.com/systemd/systemd at `v255`: `man/loginctl.xml:186-194` and `man/systemctl.xml:2297-2307`, the
    sources of https://www.freedesktop.org/software/systemd/man/255/loginctl.html
  - https://nodejs.org/dist/v24.21.0/node-v24.21.0-linux-x64.tar.xz (the pinned tarball, hashed and inspected)
- This repository at `origin/main` 3361b342:
  - `adoption/bootstrap-linux.sh` (lines 154-163, 167-178, 186-200, 205-218, 221, 237-242, 1048-1058);
    `adoption/bootstrap.md` (lines 223-228, step 3);
  - `adoption/platforms/linux-wsl2.md` (lines 52-59, 158-166, 177-205, 211-218, 236-239); `adoption/hosts/example.json`;
    `adoption/tools/README.md:184-188`; `adoption/lifecycle.md:215-244`;
  - `adoption/templates/systemd/credential-boot-receipt.service:11-12`; `adoption/pins-linux-x86_64.json` (node);
  - `docs/new-workstation-runtime-profile-20260922.md:25,34`; `docs/next-host-stages.md:54-77`;
    `docs/decisions/2026-09-28-ecosystem-roadmap.md:58,122,205`; `observability/backends/templates`;
  - `scripts/validate.py` (`RECEIPT_KINDS`, receipt payload keys); `manifests/stack.json` (`systemd`).

Read on 2026-10-01 by the follow-up unit (F11 and the F5 range rule):

- https://code.claude.com/docs/en/mcp: local scope; "Server status", with the `Added ...` line; the repeated-add
  failure. The coordinator fetched it at 07:54Z and the unit re-read it at 08:02Z.
- https://docs.docker.com/engine/security/rootless/troubleshoot/: the `lchown <FILE>: invalid argument` entry. The
  coordinator fetched it at 07:47Z and the unit re-read it at 08:02Z.
- This repository at `3361b342`; the files read are unchanged at this branch's head:
  - `adoption/bootstrap.md:387-395` (step 4a's `uv tool install` lines) and `:458-472` ("jCodeMunch, per project");
  - `docs/decisions/2026-09-23-claude-user-profile.md:127-210` (the 2026-09-25 addendum);
  - `adoption/hooks/claude/token-lanes-block.md` and its five role blocks;
  - `tools/adoption/install_claude_profile.py:49-59` (the blocks it copies);
  - `adoption/mcp/claude-user.json`, the `profiles` of `adoption/manifest.json` and `adoption/pins-linux-x86_64.json`.

Read on 2026-10-01 by the review-repair unit (the export before W6's `--unregister`), through Context Mode:

- https://learn.microsoft.com/en-us/windows/wsl/basic-commands (`ms.date` 2025-12-01), with its source
  `WSL/basic-commands.md` of `MicrosoftDocs/WSL` on `main`. "Export a distribution":
  `wsl --export <Distribution Name> <FileName>` "Exports a snapshot of the specified distribution as a new distribution
  file. Defaults to tar format", with `--vhd` for a `.vhdx` file. "Unregister or uninstall a Linux distribution": all
  data, settings and software of the distribution "will be permanently lost". The page's in-place command,
  `wsl --import-in-place <Distribution Name> <FileName>`, registers an existing `.vhdx` as a new distribution and
  repairs nothing.
- https://documentation.ubuntu.com/wsl/latest/howto/cloud-init/ (redirected to
  https://ubuntu.com/wsl/docs/latest/howto/cloud-init/, "Last updated on Sep 28, 2026"): no repair of a failed
  provisioning is documented. The in-place repair of Alternatives 2 stays a reading of WSL's and `wsl-setup`'s source,
  not a documented procedure.

Read on 2026-10-01 for the second follow-up (the completeness critic's items), by its researcher, whose packet gives each
URL and file:line and is quoted here as it quotes them, and by the unit where noted:

- microsoft/WSL: https://github.com/microsoft/WSL/issues/40941, https://github.com/microsoft/WSL/pull/40977,
  https://github.com/microsoft/WSL/issues/41482, https://github.com/microsoft/WSL/issues/13416,
  https://github.com/microsoft/WSL/issues/9968 and the release notes at https://github.com/microsoft/WSL/releases
  (2.5.4, 2.7.11 to 2.7.14, 2.9.8); the source at tag 2.7.13 (`80697fd42cca3de0c0d5dd1931c36112372a577e`):
  `src/windows/common/WslInstall.cpp:36-50, 94-146, 287-325`, `Distribution.cpp:20-21, 223-230`,
  `Distribution.h:85-86`, `WslClient.cpp:500-537`, `Resources.resw:837-838, 1067`,
  `LxssUserSession.cpp:2658-2676, 3583-3599` and `WslCoreInstance.cpp:293-302`; `Redirector.h` at tags 2.7.13, 2.7.14,
  2.9.8 and 3.0.1, and `WslCoreInstance.cpp:315` (2.9.8) and `:316` (3.0.1).
- cloud-init at tag 26.1 (`8bf3567532b07e2cc15aa4c76c36ebed65ccfaec`): `cloudinit/config/schema.py:1279-1287, 1388-1498`,
  `cloudinit/log/log_util.py:68-79` and `cloudinit/cmd/main.py:1240-1241, 1286-1293`.
- wsl-setup at Launchpad `74bfc89113bc7d46a4d9feb1e69cd6951fbc6908`: `wsl-setup:117-118, 130`,
  `wait-for-cloud-init:9-12` and `debian/install`; GitHub tag 0.5.10, `f83e4df49b3583272d5ca499ca63b426b934a1f3`.
- https://ubuntu.com/tutorials/how-to-verify-ubuntu (steps 4 to 6) and the `ubuntu-keyring` `debian/changelog` at
  Launchpad `edc0a0be9a90f364bc39a87d3837ad4c15395950` (lines 104-106, 114 and 141-142).
- https://releases.ubuntu.com/24.04.5/SHA256SUMS and https://releases.ubuntu.com/24.04.5/SHA256SUMS.gpg (also
  fetched and verified by the unit; Evidence classes).
- The metadata of each Microsoft Learn page above (`ms.date`, `updated_at`, `git_commit_id` and the displayed date).
- By the unit: the pinned raw files of MicrosoftDocs/WSL (HTTP 200 for build-custom-distro, basic-commands,
  use-custom-distro, systemd and wsl-config), `adoption/bootstrap-linux.sh:175-178` on this branch, and
  `/usr/include/scsi/scsi.h:59-60` (libc6-dev) for the SCSI command codes.

Primary sources reused for W-IMG parameterization (2026-10-01):

- https://releases.ubuntu.com/26.04.1/SHA256SUMS and https://releases.ubuntu.com/26.04.1/SHA256SUMS.gpg;
  the retained integration receipt's reported signature exits/fingerprint and image stream hash match, with no
  retained 26.04.1 signature output and no new download for this unit.
- https://documentation.ubuntu.com/release-notes/26.04/ and the Microsoft creation docs pinned above support creation,
  not full-stack compatibility. https://ubuntu.com/wsl/docs/stable/howto/cloud-init/ is explicitly a 24.04/22.04 guide.
- https://github.com/ubuntu/wsl-setup/blob/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/wsl-setup and
  https://github.com/ubuntu/wsl-setup/blob/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/ubuntu-insights.sh, tag `0.6.3`.
- https://learn.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute and
  https://docs.nvidia.com/cuda/wsl-user-guide/index.html (preserved CUDA on WSL 13.4 guide): native GPU visibility only;
  `nvidia-smi` has limited WSL features and can be invoked at `/usr/lib/wsl/lib/nvidia-smi`.
- Existing `adoption/bootstrap.md`'s Python 3.13 prerequisite and `adoption/pins-linux-x86_64.json`'s official Node
  24.21.0 tarball pin; native uv `run --help` observation recorded above. No replacement installer was written.

Sources for the rehearsal correction (2026-10-02), retained review and supplied primary references:

- `origin/foundation/new-wsl-rehearsal-20261002` at `76b7c0b4ee45d3a6f0a60fa68d053e0f2039e8e4`,
  `evidence/artifacts/new-wsl-rehearsal-20261002/coordinator-review.md`
  and `stage1-receipt.json`; these were read with `git show`. The repair brief adds the interop recovery and
  initial-namespace observation after the worker's stop.
- microsoft/WSL release notes at https://github.com/microsoft/WSL/releases/tag/2.9.8,
  https://github.com/microsoft/WSL/releases/tag/2.9.13 and https://github.com/microsoft/WSL/releases/tag/3.0.1;
  https://github.com/microsoft/WSL/pull/40519 and https://github.com/microsoft/WSL/pull/41512.
- https://github.com/microsoft/WSL/issues/41492, still open in the retained review; no 3.0.1 rootless acceptance.
- Linux `v6.18`, https://github.com/torvalds/linux/blob/v6.18/include/linux/proc_ns.h, `PROC_CGROUP_INIT_INO`.
- https://docs.docker.com/engine/security/rootless/, the supported setup and rootless Docker context already selected
  by this recipe; the container check uses its native Docker CLI.
- This worktree's `evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`,
  `cross:wsl-distro` / `base-distribution`: the single Ubuntu 26.04.1 default. The repair brief supplies the later
  critics' confirmation and the release-caused-failure rollback condition.

Sources for the updated-host correction (2026-10-02), read that day by the third follow-up's unit:

- https://github.com/microsoft/WSL/pull/40621, "protect binfmt_misc from cross-distro wipe at shutdown" (merged): it
  bind-mounts a read-only file over `/proc/sys/fs/binfmt_misc/status` in each per-distro mount namespace, so that the
  write with which `systemd-shutdown` wiped the shared registry fails with `EROFS`. Read through the GitHub API.
- https://github.com/microsoft/WSL/issues/41226, "`systemd-binfmt.service` fails with "Read-only file system" on boot"
  (closed), and a contributor's answer of 2026-08-04: "The systemd error is benign and won't affect registration of user
  defined binfmt settings. Please ignore it if it's not affecting any functions." Read through the GitHub API.
- systemd `src/binfmt/binfmt.c`: `Failed to flush binfmt_misc rules, ignoring: %m` is line 253 of tag `v255` and line
  249 of tag `v259`. `tmpfiles.d/systemd.conf.in`: the `adm` group's read access to the system journal, lines 47-53 of
  `v255` and 44-50 of `v259`. The 26.04.1 image packages systemd 259.5-0ubuntu3.4 (the experiment record); tag `v259`
  was read, not `v259.5`.
- The coordinator's brief of 2026-10-02: the host observations of the Updated-host correction and the contract for the
  three changes.

## Amendment 2026-10-02 (rehearsal run 2 on WSL 3.0.1, and the scoped cross-family read)

The coordinator accepted run 2 and the scoped cross-family read of `fed1e93c` for PR #593. This amendment records
their source reviews and host observations and changes the next run's commands and proofs; it is not another host
run. Earlier sections retain their dated evidence and planning statements. The observations below supersede their
statements that simultaneous distributions on 3.0.1 were unobserved. No image comparison has run; the criteria are
the preregistered ones with the amendments of 2026-10-02 made before any comparison ran.

Run 2, 2026-10-02T08:32Z to 08:40Z, used a throwaway name, Ubuntu 26.04.1, path A, WSL 3.0.1.0 and kernel
6.18.40.1-1. P1, P2, W1, W2, W3, W4 and W5's path-A proofs passed: launch exit 0, uid 1000, cloud-init
26.1-0ubuntu3~26.04.1, retained `result.json` and `status.json` without errors, `Valid schema user-data`,
`/etc/wsl.conf`, the marker and sudo. It stopped at W5's paired rule and was removed through W5's recovery block.
The seven findings are:

1. **P3 counted the kernel's command line.** The baseline of `2` was `kernel: Command line:` at 0.000000 s and
   `kernel: Kernel command line:` at 0.018761 s, both naming `hv_storvsc.storvsc_max_hw_queues=4`. Neither is a
   storage error. The old age rule would stop a run within one hour of boot on these echoes. P3's two filters and
   W5's second count now exclude the registration line and `[Cc]ommand line:` with the same extended-regexp filter.
2. **Cgroup isolation held.** The workstation printed `cgroup:[4026532183]` and the new distribution
   `cgroup:[4026532407]`; the common unit's `cgroup.procs` held one local pid and no `0`. Both user managers were
   `active`, and the launch printed no user-session warning. This observes two distributions running together on
   3.0.1, while a complete corrected recipe run and F3 remain owed.
3. **The shared console failed the paired rule.** In the second the new distribution booted, both
   `getty@tty1.service` units received SIGHUP and restarted five times, then showed `Result=start-limit-hit`.
   Both system managers listed that unit and `systemd-binfmt.service` failed. The workstation changed from its W1
   baseline: `1000`, `degraded`, only `systemd-binfmt.service` failed, `active`, `cgroup:[4026532183]`.
   Both expose `/dev/tty1` as character device 4,1 of the one VM kernel. Source review of the two running images
   (workstation Ubuntu 24.04.5/systemd 255; new Ubuntu 26.04.1/systemd 259) found `TTYPath=/dev/tty1`,
   `TTYVHangup=yes`, `Restart=always`, `RestartSec=0` and enablement in `/etc/systemd/system/getty.target.wants/`;
   both `console-getty.service` units read `masked-runtime`. The workstation's getty stays failed until the next
   WSL start; no unit action is permitted there by this page, and nothing uses the VM console.
4. **One real storage error appeared.** The second count was `3`. The new driver line, `cmd 0x2a`, `srb 0x4`,
   host `0xc00000a1`, was at kernel time 7118.5 s in W4's install window. The disk was unmounted at 7126.9 s,
   and cloud-init's `init-local` started at 7134.15 s. The written attachment-window rule recorded the line and
   did not stop the run; the other two lines were the command-line echoes.
5. **Removal preserved interop.** Export and unregister both exited 0, and the survivor check passed. On 3.0.1
   `WSLInterop` survived both unregisters of 2026-10-02, in run 2 and probe E1, unlike the 2.7.13 rehearsal.
   The check after every unregister and its stop-for-review rule remain required.
6. **The image size was observed.** W2 printed `418495746` bytes for `ubuntu-26.04.1-wsl-amd64.wsl`.
7. **Journal access depends on the user's group.** The workstation user is not in `adm`: without `sudo` the
   identifier query printed the permission hint and `-- No entries --`; with `sudo` it printed
   `Failed to flush binfmt_misc rules, ignoring: Read-only file system`. The new user belongs to `adm` through
   the user-data. `journalctl -b 0 -t systemd-binfmt --no-pager -n 4`, without `tail`, printed the same lines.

The mechanism's upstream sources were reviewed at microsoft/WSL tag `3.0.1`:

- [`src/linux/init/init.cpp:363-365`](https://github.com/microsoft/WSL/blob/3.0.1/src/linux/init/init.cpp#L363-L365):
  "Mask console-getty.service since /dev/tty devices are shared at the VM level across all distros. When multiple
  distros are running, the second distro's getty fails because the tty is already held."
  [PR #14490](https://github.com/microsoft/WSL/pull/14490), merged 2026-04-09, says "Fixes #13595".
- [`distributions/validate-modern.py:27-40`](https://github.com/microsoft/WSL/blob/3.0.1/distributions/validate-modern.py#L27-L40):
  `DISCOURAGED_SYSTEM_UNITS` includes `console-getty.service` and does not include `getty@tty1.service`.
- A maintainer in [issue #13595](https://github.com/microsoft/WSL/issues/13595): "the best way to solve this would
  probably to try to get distros to disable the `getty` and adjacent units in WSL".

**Probe E1, 2026-10-02T08:42Z.** Outside the recipe, a second throwaway name used the same template with the new
`bootcmd`. Its rendered SHA-256 was `c0732303a0004121f9d373f7856454e3e59eeadea395bac46eb17e1671b32af4`.
It returned `Valid schema` on the workstation and `Valid schema user-data` in the image. The getty was `masked`
(`is-enabled` exit 1, normal for a masked unit), with `LoadState=masked`, `ActiveState=inactive` and `NRestarts=0`.
Only `systemd-binfmt.service` was failed. The journal recorded cloud-init creating the mask symlink and, 0.18 s later,
systemd's `Failed to start getty@tty1.service.`: the refused job of a masked unit, not a failed unit. Cloud-init
finished without errors; the user manager was `running`; namespaces were `cgroup:[4026532183]` and
`cgroup:[4026532410]`. The workstation's values did not change, and the probe was removed afterwards.

Ordering is a source review of the pinned 26.04.1 image's own files: `cloud-init-network.service` has
`Before=systemd-user-sessions.service`, `getty@.service` has `After=systemd-user-sessions.service`, and
`/etc/cloud/cloud.cfg` lists `bootcmd` among `cloud_init_modules`. The workstation's cloud-init
26.1-0ubuntu1~24.04.1 has the same ordering in `cloud-init.service`; that is the version the 24.04.5 image packages,
but the 24.04.5 image's own unit files were not read.

**Decision.** Mask `getty@tty1.service` in the new distribution through the template's `bootcmd`, during cloud-init's
network stage before systemd starts the unit. W5 proves the mask and retains all five paired observations with
separate exits. The workstation's five values must equal its W1 baseline. W1 accepts a failed workstation getty
only as an earlier collision's leftover with `Result=start-limit-hit`; it does not prove the workstation's unit
messages again, because that distribution is compared with itself and F1 proves the new distribution's message.
Any other baseline stops before W4 or any W6 import, including a uid other than 1000, an inactive user manager or
the initial cgroup namespace. Any failed W5 proof uses `w5_failure_export`, with `cause` (`cgroup`, `tty` or a short
text), and `<Name>-w5-failed.tar`; do not take path B for any such cause. Only the OOBE prompt failure permits W6.
On path B the root block masks the getty after its first boot has already started it, so W5's paired proof after
the relaunch decides whether the workstation changed; a difference stops and uses W5's recovery.

**Run 3 (2026-10-02T10:54Z to 11:01Z, the repaired recipe, a third throwaway name).** P1 to P3, W1 to W5, W7 and F1
to F5 passed. W5: launch exit 0; `systemctl is-enabled getty@tty1.service` printed `masked`; `LoadState=masked`,
`ActiveState=inactive`, `NRestarts=0`; the paired values were `1000`, `degraded`, {`getty@tty1.service`,
`systemd-binfmt.service`}, `active`, `cgroup:[4026532183]` for the workstation, equal to its W1 baseline, and `1000`,
`degraded`, {`systemd-binfmt.service`}, `active`, `cgroup:[4026532408]` for the new distribution. W7's owner probe
printed `1000:1000` on 3.0.1. F1's journal line printed the read-only flush message without `sudo`. F2: linger `yes`,
and the distribution was listed in all twelve idle polls (`.wslconfig` has `instanceIdleTimeout=-1`). F3: a user-owned
directory and socket, user manager `running`; after F4, F5 and Docker's rootless setup (Docker Engine 29.8.2),
`docker --context rootless info` listed `name=rootless` and `docker --context rootless run --rm hello-world` printed
`Hello from Docker!`: microsoft/WSL#41492 does not affect a new distribution on this host. The second storage count
rose by one line inside W4's install window (15573.8 s), as in run 2 and the probe. Second-instance probes: user
manager `running`, `/dev/dxg` present, `nvidia-smi` exit 0, system `Python 3.14.4`; uv and Node are not installed
before stage 2, so those two probes are owed.

Run 3 also found three command defects, each corrected and re-run on the same distribution. (1) With the `bootcmd`,
cloud-init records one recoverable error, `Failed to wait for network`, and `cloud-init status --long` exits 2:
cloud-init waits for the network when user-data holds a `bootcmd` (26.1, `cloudinit/cmd/main.py:351-402`), and WSL
masks `systemd-networkd-wait-online.service` (`init.cpp:356-358`). It is harmless and now stated as expected in W5.
(2) Windows PowerShell 5.1 does not escape a double quote inside an argument to a native program, so R1's first probe
returned `stat: missing operand`, and the quoted F10 loop that this repair had introduced returned `unexpected EOF`;
both now carry no double quote (`stat -c %U,%F ...`; `[[ -f $p && -x $p ]]`) and printed the expected lines. (3) F5's
block ran `usermod` unconditionally although its text said otherwise; its second line now guards itself.

**P3's age rule, one exception (added in the coordinator's review of this repair, 2026-10-02).** With the corrected
filter the workstation's kernel journal holds two real driver errors of the same shape, at 7118.5 s (run 2's install)
and 7678.6 s (probe E1's install): each `wsl.exe --install --from-file` on this host left one line in its install
window. P3 as written would stop a second arm that starts within the hour on its predecessor's line. P3 now lets a
run continue when the newest line's kernel time is one that an earlier run of the page recorded as its own
attachment-window line; a line no earlier receipt explains keeps the stop. Overturned when an install leaves more
than its one line, or lines appear outside an install window: then the count is exposure to microsoft/WSL#41482 and
the stop applies. F10's sentence now renames every profile of the example without naming a count, so it holds for
the example with three profiles and with five (pull request 604 added two resume profiles).

Alternatives considered, with what would overturn each rejection:

- **Accept getty as a second by-design failed unit in both distributions.** This hides a real cross-distribution
  effect and changes the workstation's state at every import. Reconsider only if upstream evidence eliminates the
  effect or a separate decision accepts that workstation change; a failed getty is not part of F1's pass condition.
- **Mask it in the workstation as well.** This changes the owner's running distribution and would also protect it
  from other distributions' gettys. It is left to the owner. Reconsider if a run proves the new-distribution mask
  takes effect after the unit started, with the owner's decision required for that broader change.
- **Use a kernel command-line or `.wslconfig` setting.** The page never changes `.wslconfig`; a kernel choice also
  reaches every distribution. Reconsider only with an upstream-supported setting and a separate host-wide decision.
- **Change the image.** The page installs the official image unmodified. Reconsider if Canonical's official image
  stops enabling the getty, or a separate image decision replaces that requirement.

Drop the `bootcmd` when WSL masks `getty@tty1.service` itself or Canonical's image stops enabling it. If a run shows
the mask taking effect after the unit started, the proof fails and masking the workstation is reconsidered.
A host whose other systemd distributions retain an unmasked getty will see both fail when two of them run; changing
those units belongs to the host owner, outside this page.

**Not established.** A live workstation getty surviving a new distribution's first boot follows from the masked
unit never starting, but was not observed: the workstation's getty had already failed in run 2 before E1. The
24.04.5 image's own unit files and path B's first boot are unobserved. A complete recipe run with the amended
template through F3 remains owed; E1 is a probe, not a recipe run. Full image comparisons and full-stack acceptance
remain owed.

The scoped review's points and their repairs are:

- W1's incomplete stop: W1's four baseline conditions and the checklist now stop every incompatible baseline;
  tests remove the stop paragraph, uid, namespace and user-manager conditions separately.
- Receipt equality and abbreviated F1 exceptions: every workstation field requires equality to
  `host.workstation_baseline`; the comparison table, receipt and experiment use F1's complete pass condition.
- Linux entry paths and F10 quoting: the launch forms use full Windows paths in Linux shells, and F10 tests each
  quoted executable path without word splitting.
- Hidden exits: W1 and both W5 halves have five separate commands and receipt entries; F1 and its sudo fallback
  use `journalctl -n 4` directly.
- Test blind spots: the new controls reject every weakened baseline/equality/message instruction, and the full
  original quality rule is compared after removing the dated amendments.
- Preregistered label and stale framing: the page, checklist and named record sentence identify the amendments;
  the W7 sentence describes the 2.7.13 rehearsal in the past, and overturn now concerns a later WSL update.

The command table mirrors the amended operational commands. Historical command text in earlier evidence sections
remains as the command actually run then; it is not a command for the next run. The supplied primary reviews, the
official image's files and the installed commands above are the sources for this bounded repair. The existing
Python `unittest` harness tests repository contracts only; its controls do not qualify a host. The completeness
check leaves the same decision-changing gaps: the corrected full run through F3, the rollback image and path B.
