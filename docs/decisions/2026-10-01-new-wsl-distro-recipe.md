# Decision: provisional Ubuntu 26.04.1 and 24.04.5 WSL image arms, provisioned by cloud-init (2026-10-01)

**Decided by:** coordinator session `native-agent-stack-c5` (decisions 1 to 5 below), on the research unit's findings of
2026-10-01. Unit W2 of that wave wrote the recipe, the templates and the test, and re-read the sources the same day.
A follow-up unit added F11 and the F5 range rule later that day, on the coordinator's brief. A second follow-up unit
then added the completeness critic's pre-stage-1 checks (R1, P1 to P3, W7, W5's schema check and F2's idle observation)
and corrected three facts, on the coordinator's brief and a research packet of the same day. The coordinator then set
P3's rule: the count is a baseline, an error line less than one hour old stops the run, and W5 counts again after the
first launch.
This record changes nothing on a host. No `wsl.exe` command, import, `.wslconfig` edit or first launch ran for it. The
second follow-up's artifact checks ran P1 to P3's commands in the workstation distribution and changed nothing on the
host (Evidence classes).

**Scope:** [`adoption/platforms/linux-wsl2-new-distro.md`](../../adoption/platforms/linux-wsl2-new-distro.md) and its
pointer section in `adoption/platforms/linux-wsl2.md`; `adoption/templates/wsl/` (`cloud-init.user-data.template`,
`host.new-distro.json.template`, `first-boot-checklist.md`, `stage1-receipt.example.json`); `tests/test_wsl_new_distro_recipe.py`.

**Status:** accepted W-IMG recipe parameterization only. Ubuntu 26.04.1 trial and 24.04.5 fallback are
symmetric provisional arms with no merit precedence. Both new-host acceptance runs remain unrun. The scoped
[experiment](../../blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json) keeps `status: planned`,
decision `trial`, no qualification runs and no usage comparison. Its next test preregisters both R1 rehearsals. The
preserved signature/image inspections are artifact evidence; local consistency checks and synthetic receipt examples
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
  Ubuntu's announcement 2.4.8 and Ubuntu's install guide 2.4.10 (Method 1), so the host's 2.7.13 needs no update to
  install. The research unit read the notes of WSL 2.7.14 (2026-09-11) and 3.0.1 (2026-09-29) and the `microsoft/WSL`
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

| Provisional arm | Actual release URL | Exact image SHA-256 | Catalog entry at `8bc98bc33b246fe66710eec9eaa1b24c323da987` |
| --- | --- | --- | --- |
| 26.04.1 trial | https://releases.ubuntu.com/26.04.1/ubuntu-26.04.1-wsl-amd64.wsl | `48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104` | `Ubuntu-26.04` (also `Ubuntu`) |
| 24.04.5 fallback | https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl | `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e` | `Ubuntu-24.04` |

Both arms use the same R1 preregistered criteria table and native probes in the recipe, on separate throwaway names
under the same host kernel, driver, settings, checkout, user-data and bootstrap profile. R1 keeps its initial run
through F3, then extends successful rehearsals through F9 for the existing toolkit and the bounded comparison probes.
The default-user systemd manager and bus are checked from the workstation's second-instance session. GPU visibility
uses Microsoft's/NVIDIA's native WSL guidance; toolkit runtime checks use the accepted bootstrap and official Node
24.21.0 pin. A version/startup probe or visible GPU does not establish full-stack, CUDA workload or model acceptance.
Both arms have no merit precedence, and both new-host acceptance runs remain unrun.

**Preserved facts, reused rather than rerun.** The coordinator verified both signed sums with `gpgv`, exit 0, using key
`843938DF228D22F7B3742BC0D94AA3F0EFE21092`. The retained logs are each release's `native-signed-sums.stdout` and
`native-signed-sums.stderr`, beside its `SHA256SUMS` and `SHA256SUMS.gpg`. A whole 26.04.1 image was streamed through
`curl | tee` to SHA-256 and tar inspection, exit 0. `image-stream.sha256` matches the exact pin above;
`native-image-inspection.stdout` contains the files and dpkg status. No 26.04.1 image size was observed. The earlier
24.04.5 stream, 388,975,696 bytes, and all earlier P1/P2/P3 receipts below retain their historical artifact scope.

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

## Alternatives

1. **Images.** The former queued Ubuntu 26.04.1 alternative now shares the parameterized recipe with the historical
   24.04.5 fallback. Both are provisional; source/signature/image facts are observed, new-host compatibility is
   unrun. The earlier `python3` 3.14.3 statement described its metapackage, not the 3.14.4 interpreter (correction in W-IMG preregistration).
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
   - Update WSL to 3.0.1 first: it carries the fix for microsoft/WSL#40941, which 2.7.14 lacks. Not chosen: updating
     WSL is the keys lane's decision, and W7's terminate and probe cover the bug on 2.7.13. This record first said that
     neither release changes the first launch, which was wrong.
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

1. **Images.** Explicitly select `<RELEASE>` as 26.04.1 trial or 24.04.5 fallback. Both are symmetric provisional
   arms with no merit precedence. P1 verifies both signed sums; W2 controls each release-to-file-to-SHA-to-catalog
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
   - **Second storage reading (W5).** On both paths, right after the first launch, the same count again in the
     workstation distribution. Equal to the baseline passes. A larger count is recorded with the new lines, a failed
     W5 counts as exposure to microsoft/WSL#41482, and nothing continues to stage 2 until that is decided.
   - **Preflight (W1).** Neither Ubuntu Pro file exists, or `agent.yaml`'s top-level keys are recorded and include
     neither `users` nor `write_files`. W1 also reads `instanceIdleTimeout` and `vmIdleTimeout` of the global WSL
     configuration, without writing it.
   - **After the first launch (W5).** `cloud-init status --long` must print `status: disabled` with
     `boot_status_code: disabled-by-marker-file`. Completion and errors come from `/var/lib/cloud/data/result.json`
     (`DataSourceWSL`, `"errors": []`) and `/var/lib/cloud/data/status.json` (four stages finished without errors). On
     path A, `cloud-init schema --system` must print a line matching `^\s*Valid schema user-data$`; path B skips it.
   - **Terminate once (W7).** After W5 (path A) or W6 (path B): `wsl --terminate <Name>`, a relaunch, and an empty file
     created from Windows under the user's home must read `1000:1000`. `0:0` stops every write from Windows.
   - **How to tell cloud-init did not provision.** The launch prints `Create a default Unix user account:` and
     `OOBE command "/usr/lib/wsl/wsl-setup" failed, exiting` and returns nonzero.
   - **Fallback, path B (W6).** Re-list, then preserve the failed attempt. `wsl --terminate <Name>` and
     `wsl --export <Name> Z:\WSL\downloads\<Name>-failed.tar` keep its cloud-init logs, `/var/lib/cloud/instance` and its
     configuration. Its SHA-256 and size go to the receipt's `failed_attempt_export`. A nonzero export exit throws
     before any deletion. Then `--unregister` the literal new name, `--import ... --version 2`, then a manual user with
     the same groups and NOPASSWD drop-in, `[user] default`, the marker and `wsl --terminate <Name>`.
   - **Stage-1 receipt.** The private PowerShell transcript, sanitized into the shape of
     `adoption/templates/wsl/stage1-receipt.example.json`. Its payload keys are those `scripts/validate.py` compares with a
     `receipts[]` row; `kind` is `native_cli_e2e` and `component_ids` is `systemd` (stack row `255.4-1ubuntu8.17`, the
     image's version).
3. **First boot**, as the user:
   - `systemctl is-system-running --wait` must print `running`; Ubuntu's own setup test asserts that.
   - `loginctl enable-linger`, then `Linger=yes`; then, with no client attached, `wsl.exe --list --running` every 10
     seconds for two minutes records whether `<Name>` stays up (F2).
   - The user bus is a socket owned by the user.
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
   - W1's `Select-String` read is the only command that names `.wslconfig`; the test rejects any other command naming it.
   - The test rejects any recipe command that breaks these rules.
5. **Open questions** stay open; see below.

## Overturn condition

1. **Images.** Select within the measured host scope only after both arms have complete, identically scoped R1
   comparison records for first boot, the systemd user manager from a second instance, WSL GPU visibility,
   uv-managed CPython 3.13 and the pinned Node 24. Preserve failures and skips; missing evidence is not a win.
   Trial/fallback names confer no merit precedence. Re-pin a release only after Canonical's signed sums and the
   pinned Microsoft catalog agree. A W2 mismatch stops the run with nothing installed.
2. **Creation path.** Revisit in two cases:
   - a host run with a correct user-data file still shows the W5 markers;
   - a WSL release changes when the first-run command runs (`WslCoreInstance.cpp:204`) or what a failure leaves
     (`:293-303`).

   The coordinator may instead adopt the in-place repair as the first fallback, ahead of path B.
3. **First boot.** Revisit in four cases:
   - F1 reports `degraded` on a clean run;
   - the bootstrap starts installing `uidmap` or `libatomic1` itself;
   - the Harbor lane retires rootless Docker, which removes `uidmap` and F5;
   - the user-scope MCP template registers jCodeMunch again (the addendum's overturn condition), or a script runs the
     per-project registration, which turns F11 into a check.

   Drop `libatomic1` when the coordinator accepts the `readelf` measurement.
4. **Host-wide.** Revisit when the keys lane updates WSL (re-verify install, import and first run at that tag; from
   2.9.8 or 3.0.1 on, the fix for microsoft/WSL#40941 is present and W7 becomes a check) or when a separate decision
   makes the new distribution the default. Revisit P3 when microsoft/WSL#41482 names a fixed release, or when a run
   shows storage errors that the one-hour threshold, this recipe's choice, misjudges.

## Command table

Every command line of the recipe's `powershell` and `sh` blocks, in order. `tests/test_wsl_new_distro_recipe.py` fails
when a row and the recipe disagree. The proofs are what the run must print; none of them has run on a host as part of
the recipe. P1 to P3's commands ran as artifact checks in the workstation distribution (Evidence classes).

| Step | Shell | Command | Proof |
| --- | --- | --- | --- |
| R1 | powershell | `wsl.exe -d '<Name>' --exec bash -lc 'stat -c "%U %F" "/run/user/$(id -u)" "/run/user/$(id -u)/bus"'` | R1: record the returned exit and output required by the recipe |
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
| R1 | powershell | `wsl.exe --list --verbose` | the throwaway name absent; the starred line equals W1's |
| P1 | sh | `for RELEASE in 26.04.1 24.04.5; do` | both signed-sums arms, each in an empty temporary directory |
| P1 | sh | `SUMS_DIR="$(mktemp -d)"` | an empty temporary directory, also `gpgv`'s home |
| P1 | sh | `curl -fsSL -o "$SUMS_DIR/SHA256SUMS" "https://releases.ubuntu.com/$RELEASE/SHA256SUMS" \|\| exit 1` | P1: record the returned exit and output required by the recipe |
| P1 | sh | `curl -fsSL -o "$SUMS_DIR/SHA256SUMS.gpg" "https://releases.ubuntu.com/$RELEASE/SHA256SUMS.gpg" \|\| exit 1` | P1: record the returned exit and output required by the recipe |
| P1 | sh | `gpgv --homedir "$SUMS_DIR" --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg "$SUMS_DIR/SHA256SUMS.gpg" "$SUMS_DIR/SHA256SUMS"` | exit 0 and `Good signature` by `843938DF228D22F7B3742BC0D94AA3F0EFE21092`; `BAD signature` or a missing key stops the run |
| P1 | sh | `if [ "$?" -ne 0 ]; then exit 1; fi` | P1: record the returned exit and output required by the recipe |
| P1 | sh | `grep -F " *ubuntu-$RELEASE-wsl-amd64.wsl" "$SUMS_DIR/SHA256SUMS" \|\| exit 1` | each release's exact signed image line from the controlled pins |
| P1 | sh | `done` | P1: record the returned exit and output required by the recipe |
| P2 | sh | `RENDER_DIR="$(mktemp -d)"` | an empty temporary directory |
| P2 | sh | `python3 -c 'import string, sys; sys.stdout.write(string.Template(open(sys.argv[1], encoding="utf-8").read()).substitute(WSL_USER=sys.argv[2]))' adoption/templates/wsl/cloud-init.user-data.template '<WSL_USER>' > "$RENDER_DIR/<Name>.user-data"` | the bytes W3 writes, rendered in the workstation |
| P2 | sh | `cloud-init --version` | the workstation's cloud-init version, recorded |
| P2 | sh | `cloud-init schema -c "$RENDER_DIR/<Name>.user-data"` | `Valid schema` and exit 0; `Invalid user-data` (exit 1) stops the run |
| P2 | sh | `sha256sum "$RENDER_DIR/<Name>.user-data"` | the render's SHA-256, equal to W3's |
| P3 | sh | `sudo journalctl -k -b 0 --no-pager \| grep hv_storvsc \| grep -vc 'registering driver hv_storvsc'` | the count, recorded as the baseline (a count of `0` makes the last `grep` exit 1) |
| P3 | sh | `sudo journalctl -k -b 0 --no-pager -o short-monotonic --no-hostname \| grep hv_storvsc \| grep -v 'registering driver hv_storvsc' \| tail -n 1` | the newest error line with its kernel time in brackets, or nothing |
| P3 | sh | `cat /proc/uptime` | the seconds since boot as the first number; minus the line's kernel time, an age under 3600 s stops the run (microsoft/WSL#41482) |
| P3 | sh | `swapon --show` | recorded; active swap is the issue's condition, not a failure by itself |
| W1 | powershell | `New-Item -ItemType Directory -Force -Path 'Z:\WSL\downloads'` | the folder for the transcript and the image exists |
| W1 | powershell | `$env:WSL_UTF8 = '1'` | wsl.exe writes UTF-8 instead of UTF-16 |
| W1 | powershell | `wsl.exe --version` | `WSL version:` 2.4.10 or later; lines recorded |
| W1 | powershell | `wsl.exe --list --verbose` | the starred line is recorded as the default |
| W1 | powershell | `wsl.exe --list --quiet` | `<Name>` is not listed |
| W1 | powershell | `Test-Path -LiteralPath 'Z:\WSL\<Name>'` | `False` |
| W1 | powershell | `Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\<Name>.user-data')` | `False` |
| W1 | powershell | `Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml')` | `False`; when `True`, the next row decides |
| W1 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml') -Pattern '^[A-Za-z_][A-Za-z0-9_-]*:' -ErrorAction SilentlyContinue` | no output, or the top-level keys recorded and neither `users:` nor `write_files:` among them |
| W1 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig') -Pattern '^\s*\[', '^\s*instanceIdleTimeout\s*=', '^\s*vmIdleTimeout\s*=' -ErrorAction SilentlyContinue` | a read only: the section headers and the two idle keys, or nothing; recorded as `idle_keys` |
| W1 | powershell | `Get-PSDrive -Name Z \| Select-Object -Property Name, Used, Free` | `Free` recorded |
| W2 | powershell | `$ProgressPreference = 'SilentlyContinue'` | no progress rendering during the download |
| W2 | powershell | `$Release = '<RELEASE>'` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `switch ($Release) {` | W2: record the returned exit and output required by the recipe |
| W2 | powershell | `'26.04.1' { $Expected = '48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104'; $CatalogName = 'Ubuntu-26.04' }` | the exact selected release hash and catalog entry; neither arm has merit precedence |
| W2 | powershell | `'24.04.5' { $Expected = 'bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e'; $CatalogName = 'Ubuntu-24.04' }` | the exact selected release hash and catalog entry; neither arm has merit precedence |
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
| W2 | powershell | `(Get-Item -LiteralPath $ImagePath).Length` | actual selected-image byte count for this host run; source size of 26.04.1 is unknown |
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
| W5 | powershell | `cmd.exe /d /c "wsl.exe -d <Name> < NUL"` | `Provisioning the new WSL instance <Name>`; no prompt marker |
| W5 | powershell | `$LASTEXITCODE` | `0`; nonzero with the markers means W6 |
| W5 | powershell | `wsl.exe -d '<Name>' --exec id -un` | `<WSL_USER>` |
| W5 | powershell | `wsl.exe -d '<Name>' --exec id -u` | `1000` |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init --version` | selected-image packaged cloud-init version; not the P2 workstation version |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init status --long` | `status: disabled` and `boot_status_code: disabled-by-marker-file`; proves the marker, not the run |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/result.json` | `"datasource": "DataSourceWSL"` and `"errors": []`: the run completed without errors |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/status.json` | each of the four stages `finished` with empty `errors`; `recoverable_errors` recorded |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init schema --system` | path A: a line matching `^\s*Valid schema user-data$` and exit 0; skipped on path B |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /etc/wsl.conf` | `[boot]`, `systemd=true`, `[user]`, `default=<WSL_USER>`, each once |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec ls -l /etc/cloud/cloud-init.disabled` | the marker exists |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec sudo -l -U '<WSL_USER>'` | `(ALL) NOPASSWD: ALL` |
| W5 | powershell | `wsl.exe --list --verbose` | the starred line equals W1's |
| W5 | sh | `sudo journalctl -k -b 0 --no-pager \| grep hv_storvsc \| grep -vc 'registering driver hv_storvsc'` | both paths: equal to P3's baseline; a larger count is exposure to microsoft/WSL#41482, recorded with the new lines, and holds the run before stage 2 |
| W6 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W6 | powershell | `wsl.exe --list --quiet` | read before unregistering: `<Name>` is the new distribution |
| W6 | powershell | `wsl.exe --terminate '<Name>'` | `<Name>` stopped before the export; no other distribution stops |
| W6 | powershell | `wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-failed.tar'` | the failed attempt saved as a tar before `--unregister` deletes its disk |
| W6 | powershell | `$LASTEXITCODE` | `0` |
| W6 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }` | no `throw`; a `throw` stops W6 with `<Name>` still registered |
| W6 | powershell | `(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Hash.ToLowerInvariant()` | the export's SHA-256, recorded in `failed_attempt_export` |
| W6 | powershell | `(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Length` | the export's size in bytes, recorded in `failed_attempt_export` |
| W6 | powershell | `wsl.exe --unregister '<Name>'` | `<Name>` removed, nothing else |
| W6 | powershell | `wsl.exe --import '<Name>' 'Z:\WSL\<Name>' 'Z:\WSL\downloads\ubuntu-<RELEASE>-wsl-amd64.wsl' --version 2` | W6: record the returned exit and output required by the recipe |
| W6 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init status --wait --long` | `done` or `error` when cloud-init ran, `disabled` by `disabled-by-generator` when it found no datasource; recorded (open question 1) |
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
| F1 | sh | `systemctl is-system-running --wait` | `running` |
| F1 | sh | `systemctl --failed --no-legend` | no output |
| F1 | sh | `systemctl list-unit-files --type=service --no-pager` | the service list prints |
| F2 | sh | `sudo loginctl enable-linger "$(id -un)"` | exit 0 |
| F2 | sh | `loginctl show-user "$(id -un)" --property=Linger --value` | `yes` |
| F2 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| F2 | powershell | `foreach ($Poll in 1..12) { Start-Sleep -Seconds 10; [DateTime]::UtcNow.ToString('HH:mm:ss'); wsl.exe --list --running --quiet }` | twelve times and lists with no client attached; whether `<Name>` stays listed, recorded as `idle_observation` |
| F3 | sh | `stat -c '%U %F' "/run/user/$(id -u)" "/run/user/$(id -u)/bus"` | `<WSL_USER> directory`, then `<WSL_USER> socket` |
| F3 | sh | `systemctl --user is-system-running --wait` | `running` |
| F4 | sh | `sudo apt-get update` | exit 0 |
| F4 | sh | `sudo apt-get install -y --no-install-recommends ca-certificates curl git tar gzip xz-utils jq libatomic1 uidmap` | exit 0 |
| F4 | sh | `dpkg-query -W -f='${Package} ${Version}\n' jq libatomic1 uidmap` | three versions |
| F5 | sh | `grep "^$(id -un):" /etc/subuid /etc/subgid` | a range in both files, or nothing |
| F5 | sh | `sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$(id -un)"` | only when the first `grep` printed nothing |
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
| F10 | powershell | `wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'for p in $(type -P claude codex); do test -f $p && test -x $p && echo executable: $p; done'` | `executable:` and each path: both are regular executable files |
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
3. **binfmt after terminate.** Whether binfmt registrations survive `wsl --terminate <Name>` (`protectBinfmt`). Record
   `ls /proc/sys/fs/binfmt_misc` before and after a terminate.
4. **Subordinate ids from `useradd`.** Whether `useradd` allocated subordinate ids on the selected release. cloud-init 26.1 creates
   users with `useradd` (`cloudinit/distros/__init__.py:683` at tag 26.1). useradd(8) says it allocates `SUB_UID_COUNT`
   ids when `/etc/subuid` exists, and the image ships both; F5 records which tool wrote the range.
5. **Both image comparisons.** The preregistered R1 criteria cover 26.04.1 trial and 24.04.5 fallback with no merit
   precedence. Both new-host runs remain unrun; the older 24.04.5 receipts do not settle this question.
6. **File ownership after a terminate (microsoft/WSL#40941).** Whether `wsl --terminate <Name>` clears the 0:0 owner of
   files Windows creates after the first-run setup. The fix's pull request says the state "only recovers after a distro
   termination", the issue's reproduction says it lasts "until the next wsl --shutdown", and no one has observed a
   terminate. W7's probe after its terminate records it, first in the rehearsal.
7. **Kernel storage errors on this host (microsoft/WSL#41482).** Whether `hv_storvsc` errors break a first launch on
   this kernel. On 2026-10-01 P3's count in the workstation's journal of the current boot was 21 (Evidence classes):
   one burst of `cmd 0x2a` write errors (`WRITE_10`) on 2026-09-24 around 03:20Z and none since, where the issue shows
   `cmd 0x28` read errors (`READ_10`). Under the coordinator's rule that count is P3's baseline, and its newest line,
   about 7.4 days old, does not stop the run. W5's second count, first in the rehearsal, shows whether a first launch on
   this kernel meets new errors; the question stays open until a run records it.

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
  - P1: both `curl` lines exited 0. The `gpgv` line exited 0:
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
- **Not run.** Stage 1 and the first boot: nothing in stage 1 has run on a host, the rehearsal included. The first host
  run records `native_proven` evidence in the stage-1 receipt.
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
  both releases' preserved native signature checks above, with no new download for this unit.
- https://documentation.ubuntu.com/release-notes/26.04/ and the Microsoft creation docs pinned above support creation,
  not full-stack compatibility. https://ubuntu.com/wsl/docs/stable/howto/cloud-init/ is explicitly a 24.04/22.04 guide.
- https://github.com/ubuntu/wsl-setup/blob/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/wsl-setup and
  https://github.com/ubuntu/wsl-setup/blob/73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8/ubuntu-insights.sh, tag `0.6.3`.
- https://learn.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute and
  https://docs.nvidia.com/cuda/wsl-user-guide/index.html (preserved CUDA on WSL 13.4 guide): native GPU visibility only;
  `nvidia-smi` has limited WSL features and can be invoked at `/usr/lib/wsl/lib/nvidia-smi`.
- Existing `adoption/bootstrap.md`'s Python 3.13 prerequisite and `adoption/pins-linux-x86_64.json`'s official Node
  24.21.0 tarball pin; native uv `run --help` observation recorded above. No replacement installer was written.
