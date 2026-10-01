# Decision: a new WSL distribution from Canonical's Ubuntu 24.04.5 image, provisioned by cloud-init (2026-10-01)

**Decided by:** coordinator session `native-agent-stack-c5` (decisions 1 to 5 below), on the research unit's findings of
2026-10-01. Unit W2 of that wave wrote the recipe, the templates and the test, and re-read the sources the same day.
A follow-up unit added F11 and the F5 range rule later that day, on the coordinator's brief.
This record changes nothing on a host. No `wsl.exe` command, import, `.wslconfig` edit or first launch ran for it.

**Scope:** [`adoption/platforms/linux-wsl2-new-distro.md`](../../adoption/platforms/linux-wsl2-new-distro.md) and its
pointer section in `adoption/platforms/linux-wsl2.md`; `adoption/templates/wsl/` (`cloud-init.user-data.template`,
`host.new-distro.json.template`, `first-boot-checklist.md`, `stage1-receipt.example.json`); `tests/test_wsl_new_distro_recipe.py`.

**Status:** selected by source review; not a completed adoption until a host run and the queued comparison. The scoped
convergence experiment record
[`blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json`](../../blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json)
states this: `status: planned`, decision `trial`, no observation and no usage claim, with the research unit's usage
unknown. It names the 26.04.1 comparison (queued, not run) and path B (documented, not run) as the alternatives, and
`python3 scripts/validate_convergence.py` accepts it (exit 0). It pins the recipe, the templates and the test by
SHA-256, so a change to any of them needs a re-pin.

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
  Ubuntu's announcement 2.4.8 and Ubuntu's install guide 2.4.10 (Method 1). WSL 2.7.14 (2026-09-11) and 3.0.1 (2026-09-29)
  change nothing about install, import or first run. The research unit read their release notes and the
  `microsoft/WSL` source at the three tags.
- **Selected image.** `ubuntu-24.04.5-wsl-amd64.wsl` (sha256 `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`)
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

## Alternatives

1. **Image.** Ubuntu 26.04.1 LTS. `resolute` `SHA256SUMS` (2026-08-27) publishes
   `ubuntu-26.04.1-wsl-amd64.wsl` as `48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104`, and
   `DistributionInfo.json` maps both `Ubuntu` (WSL's default) and `Ubuntu-26.04` to it. It brings `python3` 3.14.3, uutils
   coreutils for `sha256sum`, `realpath` and `mktemp`, `sudo-rs` beside `sudo`, and ships `bubblewrap` and `libatomic1`.
   The repository has no evidence for it. Other alternatives:
   - `wsl --install Ubuntu-24.04` from the online catalog installs the same bytes, but it verifies no hash the operator
     can see before install.
   - The `cloud-images.ubuntu.com/wsl` rootfs tarballs: that page says WSL images moved to cdimages and those tarballs are
     not general-purpose.
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
   - Update WSL to 2.7.14 or 3.0.1 first: neither changes install, import or first launch.
   - Apply settings with `wsl --shutdown`: it stops every distribution.
   - Make the new distribution the default now: the workstation stays the default until a separate decision.

## Decision

1. **Image.** Ubuntu 24.04.5 LTS from Canonical's `.wsl` file, pinned by its sha256 and checked against both publications
   before install (W2). The repository has evidence for 24.04, and the bootstrap covers its `python3` 3.12. 26.04.1 LTS
   is queued as a bounded comparison unit before any switch: the bootstrap under `python3` 3.14, uutils coreutils and
   `sudo-rs`.
2. **Creation path.**
   - **Path A.** Render `%USERPROFILE%\.cloud-init\<Name>.user-data` from the template (W3). The user is `<WSL_USER>`,
     uid 1000, in groups `adm, cdrom, sudo, dip, plugdev`, with `sudo: "ALL=(ALL) NOPASSWD:ALL"`, a locked password and
     `[user] default` appended to `/etc/wsl.conf`. Then run
     `wsl --install --from-file <dir>\ubuntu-24.04.5-wsl-amd64.wsl --name <Name> --location Z:\WSL\<Name> --no-launch` (W4),
     then a first launch with standard input at end of file (W5).
   - **Preflight (W1).** Neither Ubuntu Pro file exists, or `agent.yaml`'s top-level keys are recorded and include
     neither `users` nor `write_files`.
   - **After the first launch (W5).** `cloud-init status --long` must print `status: disabled` with
     `boot_status_code: disabled-by-marker-file`. Completion and errors come from `/var/lib/cloud/data/result.json`
     (`DataSourceWSL`, `"errors": []`) and `/var/lib/cloud/data/status.json` (four stages finished without errors).
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
   - `loginctl enable-linger`, then `Linger=yes`.
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
   - The test rejects any recipe command that breaks these rules.
5. **Open questions** stay open; see below.

## Overturn condition

1. **Image.** Switch to 26.04.1 when its bounded comparison passes the same recipe and stage 2. Re-pin when Canonical
   publishes a newer 24.04 point release and `DistributionInfo.json` maps `Ubuntu-24.04` to it. A sha256 mismatch in W2
   stops every run until the hash is re-verified against both publications.
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
4. **Host-wide.** Revisit when the keys lane updates WSL (re-verify install, import and first run at that tag) or when a
   separate decision makes the new distribution the default.

## Command table

Every command line of the recipe's `powershell` and `sh` blocks, in order. `tests/test_wsl_new_distro_recipe.py` fails
when a row and the recipe disagree. The proofs are what the run must print; none of them has run on a host.

| Step | Shell | Command | Proof |
| --- | --- | --- | --- |
| W1 | powershell | `New-Item -ItemType Directory -Force -Path 'Z:\WSL\downloads'` | the folder for the transcript and the image exists |
| W1 | powershell | `$env:WSL_UTF8 = '1'` | wsl.exe writes UTF-8 instead of UTF-16 |
| W1 | powershell | `wsl.exe --version` | `WSL version:` 2.4.10 or later; lines recorded |
| W1 | powershell | `wsl.exe --list --verbose` | the starred line is recorded as the default |
| W1 | powershell | `wsl.exe --list --quiet` | `<Name>` is not listed |
| W1 | powershell | `Test-Path -LiteralPath 'Z:\WSL\<Name>'` | `False` |
| W1 | powershell | `Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\<Name>.user-data')` | `False` |
| W1 | powershell | `Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml')` | `False`; when `True`, the next row decides |
| W1 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml') -Pattern '^[A-Za-z_][A-Za-z0-9_-]*:' -ErrorAction SilentlyContinue` | no output, or the top-level keys recorded and neither `users:` nor `write_files:` among them |
| W1 | powershell | `Get-PSDrive -Name Z \| Select-Object -Property Name, Used, Free` | `Free` recorded |
| W2 | powershell | `$ProgressPreference = 'SilentlyContinue'` | no progress rendering during the download |
| W2 | powershell | `Invoke-WebRequest -UseBasicParsing -Uri 'https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl' -OutFile 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl'` | 388,975,696 bytes saved |
| W2 | powershell | `Invoke-WebRequest -UseBasicParsing -Uri 'https://releases.ubuntu.com/24.04.5/SHA256SUMS' -OutFile 'Z:\WSL\downloads\SHA256SUMS'` | the checksum list saved |
| W2 | powershell | `$Expected = 'bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e'` | the pinned value |
| W2 | powershell | `$Published = (Select-String -LiteralPath 'Z:\WSL\downloads\SHA256SUMS' -Pattern ' \*ubuntu-24\.04\.5-wsl-amd64\.wsl$').Line.Split(' ')[0]` | Canonical's value |
| W2 | powershell | `$Listed = ((Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/microsoft/WSL/8bc98bc33b246fe66710eec9eaa1b24c323da987/distributions/DistributionInfo.json').Content \| ConvertFrom-Json).ModernDistributions.Ubuntu \| Where-Object Name -eq 'Ubuntu-24.04'` | Microsoft's entry at the pinned commit |
| W2 | powershell | `$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl').Hash.ToLowerInvariant()` | the computed value |
| W2 | powershell | `"computed $Actual published $Published listed $($Listed.Amd64Url.Sha256) url $($Listed.Amd64Url.Url)"` | one hash three times and the 24.04.5 URL |
| W2 | powershell | `if ($Actual -ne $Expected -or $Published -ne $Expected -or $Listed.Amd64Url.Sha256 -ne $Expected) { throw 'sha256 mismatch: do not install' }` | no `throw` |
| W3 | powershell | `New-Item -ItemType Directory -Force -Path (Join-Path $env:USERPROFILE '.cloud-init')` | the folder exists |
| W3 | powershell | `$Text = [System.IO.File]::ReadAllText('<checkout>\adoption\templates\wsl\cloud-init.user-data.template').Replace('${WSL_USER}', '<WSL_USER>')` | the template rendered in memory |
| W3 | powershell | `[System.IO.File]::WriteAllText((Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data'), $Text)` | UTF-8 without a byte order mark |
| W3 | powershell | `Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -TotalCount 1` | `#cloud-config` |
| W3 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -Pattern '^- name: ', '^    default='` | two lines ending in `<WSL_USER>` |
| W3 | powershell | `Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -SimpleMatch -Pattern '${'` | no output |
| W4 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W4 | powershell | `wsl.exe --install --from-file 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl' --name '<Name>' --location 'Z:\WSL\<Name>' --no-launch` | `Installing: ...`, then `Distribution successfully installed. ...` |
| W4 | powershell | `$LASTEXITCODE` | `0` |
| W4 | powershell | `wsl.exe --list --verbose` | `<Name>` `Stopped`, version 2; the starred line unchanged |
| W5 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W5 | powershell | `cmd.exe /d /c "wsl.exe -d <Name> < NUL"` | `Provisioning the new WSL instance <Name>`; no prompt marker |
| W5 | powershell | `$LASTEXITCODE` | `0`; nonzero with the markers means W6 |
| W5 | powershell | `wsl.exe -d '<Name>' --exec id -un` | `<WSL_USER>` |
| W5 | powershell | `wsl.exe -d '<Name>' --exec id -u` | `1000` |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init status --long` | `status: disabled` and `boot_status_code: disabled-by-marker-file`; proves the marker, not the run |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/result.json` | `"datasource": "DataSourceWSL"` and `"errors": []`: the run completed without errors |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/status.json` | each of the four stages `finished` with empty `errors`; `recoverable_errors` recorded |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec cat /etc/wsl.conf` | `[boot]`, `systemd=true`, `[user]`, `default=<WSL_USER>`, each once |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec ls -l /etc/cloud/cloud-init.disabled` | the marker exists |
| W5 | powershell | `wsl.exe -d '<Name>' -u root --exec sudo -l -U '<WSL_USER>'` | `(ALL) NOPASSWD: ALL` |
| W5 | powershell | `wsl.exe --list --verbose` | the starred line equals W1's |
| W6 | powershell | `$env:WSL_UTF8 = '1'` | as in W1 |
| W6 | powershell | `wsl.exe --list --quiet` | read before unregistering: `<Name>` is the new distribution |
| W6 | powershell | `wsl.exe --terminate '<Name>'` | `<Name>` stopped before the export; no other distribution stops |
| W6 | powershell | `wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-failed.tar'` | the failed attempt saved as a tar before `--unregister` deletes its disk |
| W6 | powershell | `$LASTEXITCODE` | `0` |
| W6 | powershell | `if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }` | no `throw`; a `throw` stops W6 with `<Name>` still registered |
| W6 | powershell | `(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Hash.ToLowerInvariant()` | the export's SHA-256, recorded in `failed_attempt_export` |
| W6 | powershell | `(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Length` | the export's size in bytes, recorded in `failed_attempt_export` |
| W6 | powershell | `wsl.exe --unregister '<Name>'` | `<Name>` removed, nothing else |
| W6 | powershell | `wsl.exe --import '<Name>' 'Z:\WSL\<Name>' 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl' --version 2` | exit 0 |
| W6 | powershell | `wsl.exe -d '<Name>' -u root --exec cloud-init status --wait --long` | `done` or `error` when cloud-init ran, `disabled` by `disabled-by-generator` when it found no datasource; recorded (open question 1) |
| W6 | sh | `id -u '<WSL_USER>' \|\| useradd --create-home --uid 1000 --groups adm,cdrom,sudo,dip,plugdev --shell /bin/bash '<WSL_USER>'` | uid 1000 exists |
| W6 | sh | `printf '%s ALL=(ALL) NOPASSWD:ALL\n' '<WSL_USER>' > /etc/sudoers.d/90-wsl-default-user` | the drop-in written |
| W6 | sh | `chmod 0440 /etc/sudoers.d/90-wsl-default-user` | mode 0440 |
| W6 | sh | `visudo -cf /etc/sudoers.d/90-wsl-default-user` | `parsed OK` |
| W6 | sh | `grep -q '^\[user\]' /etc/wsl.conf \|\| printf '\n[user]\ndefault=%s\n' '<WSL_USER>' >> /etc/wsl.conf` | one `[user]` section naming the user |
| W6 | sh | `touch /etc/cloud/cloud-init.disabled` | the marker exists |
| W6 | powershell | `wsl.exe --terminate '<Name>'` | exit 0 |
| W6 | powershell | `wsl.exe --list --running` | `<Name>` absent |
| W6 | powershell | `wsl.exe -d '<Name>' --exec id -un` | `<WSL_USER>`; then W5's checks |
| F1 | sh | `systemctl is-system-running --wait` | `running` |
| F1 | sh | `systemctl --failed --no-legend` | no output |
| F1 | sh | `systemctl list-unit-files --type=service --no-pager` | the service list prints |
| F2 | sh | `sudo loginctl enable-linger "$(id -un)"` | exit 0 |
| F2 | sh | `loginctl show-user "$(id -un)" --property=Linger --value` | `yes` |
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
2. **Linger and the idle timeout.** Whether a lingering user manager keeps the distribution from the `instanceIdleTimeout`
   shutdown (default 15000 ms, wsl-config, updated 2026-09-16). Record whether `<Name>` stays running with no client
   attached.
3. **binfmt after terminate.** Whether binfmt registrations survive `wsl --terminate <Name>` (`protectBinfmt`). Record
   `ls /proc/sys/fs/binfmt_misc` before and after a terminate.
4. **Subordinate ids from `useradd`.** Whether `useradd` allocated subordinate ids on 24.04.5. cloud-init 26.1 creates
   users with `useradd` (`cloudinit/distros/__init__.py:683` at tag 26.1). useradd(8) says it allocates `SUB_UID_COUNT`
   ids when `/etc/subuid` exists, and the image ships both; F5 records which tool wrote the range.
5. **The 26.04.1 comparison.** The bounded unit of Alternatives 1.

## Completeness critic (2026-10-01)

The unit closed without the critic that the repository rule requires; a review thread on PR #569 pointed it out. An
independent researcher (Claude Opus, read-only, primary sources fetched 2026-10-01) then asked what the unit did not
look at: candidate classes, kinds of evidence and unread sources. It read about 30 sources and found 11 items. None
overturns the selection. Four change what must happen before stage 1, and they are queued as a follow-up to this
recipe; until that follow-up lands, do not run stage 1 without the checks of items 1 to 4.

| # | What the unit missed | Source read 2026-10-01 | Disposition |
| --- | --- | --- | --- |
| 1 | No dry run. Stage 1 and first boot have never run anywhere; a rehearsal on a throwaway name and location stays inside this record's host-wide rules | this record, "Evidence classes" | Queued before stage 1: a rehearsal that also collects items 2, 3 and 4 |
| 2 | The claim that WSL 2.7.14 and 3.0.1 "change nothing about install, import or first run" is broader than what was checked. `2.7.13...3.0.1` is 677 commits ahead, and listed commits touch first run, import and termination. One of them fixes microsoft/WSL#40941: after the first-run setup, a file created from Windows is owned by 0:0 until the next `wsl --shutdown`, which this recipe forbids. Whether 2.7.13 has the fix is known only negatively | https://github.com/microsoft/WSL/compare/2.7.13...3.0.1 ; https://github.com/microsoft/WSL/issues/40941 | Open question; measured in the rehearsal (create a file from Windows under the user's home, read its owner, terminate the distribution, relaunch, read it again) |
| 3 | The issue tracker was not searched for the selected path. microsoft/WSL#41482 reports continuous `hv_storvsc` read errors and systemd boot timeouts on Ubuntu 24.04 with kernel 6.18.33.2, this host's kernel; the maintainer's workaround needs `swap=0` and `wsl --shutdown`, both ruled out here | https://github.com/microsoft/WSL/issues/41482 | Open question; a read-only pre-check in the current distribution (`journalctl -k` for `hv_storvsc`) before stage 1, since both share the kernel |
| 4 | Whether linger keeps the distribution running. microsoft/WSL#13416 (open: WSL shuts down despite an active systemd service, still reproduced on 2.7.3) and #9968 (open) bear on open question 2 | https://github.com/microsoft/WSL/issues/13416 ; https://github.com/microsoft/WSL/issues/9968 | Open question; observed in the rehearsal with no client attached, because stage 2's user services depend on it |
| 5 | Two upstream verification steps are skipped: Canonical's how-to validates the user data with `sudo cloud-init schema --system`, and `SHA256SUMS.gpg` exists and is never verified (the repository's 2026-09-21 precedent verified Ubuntu's signed sums) | https://documentation.ubuntu.com/wsl/stable/howto/cloud-init/ ; https://releases.ubuntu.com/24.04.5/SHA256SUMS.gpg | Queued before stage 1: both become recipe steps in the follow-up |
| 6 | Other base images were not weighed. Microsoft's distribution list also carries Debian, Fedora, Arch, AlmaLinux, openSUSE, SLE and Kali; stage 2 accepts only `ID=ubuntu` or `debian` (`adoption/bootstrap-linux.sh:175-178`) | https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json | Debian feeds the layer's next landscape sweep; the others are out of scope while stage 2 rejects their `ID` |
| 7 | WSL containers, generally available with 3.0.1 (one VM, network and disk per session, OCI images), were not weighed for disposable clean-install tests | https://devblogs.microsoft.com/commandline/wslc-architecture-deep-dive/ | Feeds the layer's next landscape sweep; unlikely to host stage 2 |
| 8 | The reason given for dismissing `wsl --install Ubuntu-24.04` ("verifies no hash the operator can see") is incomplete: 2.7.13 carries a hash-mismatch message, and a local manifest can be pinned through `DistributionListUrl` | https://raw.githubusercontent.com/microsoft/WSL/2.7.13/localization/strings/en-US/Resources.resw ; https://learn.microsoft.com/en-us/windows/wsl/build-custom-distro | Open question; the selection stands because the online path resolves the list at install time and the registry key is host-wide; the follow-up corrects the stated reason |
| 9 | Creation routes not weighed: a golden copy (`wsl --export`, then `--import-in-place` of a provisioned disk), a Docker-exported root file system, a custom first-run command in `/etc/wsl-distribution.conf`, Ubuntu Pro for WSL | https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro ; https://docs.cloud-init.io/en/latest/reference/datasources/wsl.html | The golden copy feeds the next sweep; a self-built image is out of scope (it breaks the upstream-install rule) and Ubuntu Pro needs a subscription and a server |
| 10 | Package updates between the image build and today were not checked. They are harmless today: `wsl-setup` is unchanged, and cloud-init 26.2 is only proposed | Launchpad, published sources of both packages on noble | Feeds the next sweep |
| 11 | Citation hygiene in a sample of eight: one Microsoft page is dated by a value that matches neither of its metadata dates, the cloud-init datasource page is cited at `latest` (26.2 today) while the image runs 26.1, and W5's expected console lines have no cited source | the pages' own metadata | Open question; the follow-up pins each page by its revision and cites the lines |

Not checked by the critic: file-level WSL source diffs (the comparison view is truncated), whether `wsl --terminate`
clears the ownership bug, the contents of the other images, upstream test suites and community runbooks. Its issue
searches were samples of eight results per query, not sweeps.

## Evidence classes

- **Read today (source review).** The WSL source at tag 2.7.13; `ubuntu/wsl-setup` at
  `86a561d5149a9d76ec3c9b3ce2745e7ebca5f2ad` (`test/systemd-assertions.sh:6-9` asserts `running`, `:30-33` the marker);
  systemd v255 `man/loginctl.xml:186-194` and `man/systemctl.xml:2297-2307`; and the documentation below. For the
  follow-up: step 4a and the addendum, the carrier blocks, the MCP template, the profiles and the Linux pins, Claude
  Code's MCP page and Docker's rootless troubleshooting page.
- **Artifact checks on the authoring host, 2026-10-01** (not runs of the recipe):
  - the image stream's size and sha256, and the files read from it;
  - the gzip size field;
  - the Node 24.21.0 tarball's sha256 and its binary's `NEEDED` list.
- **Local integration.** `tests/test_wsl_new_distro_recipe.py`, checks over repository text and an in-memory render; it
  runs nothing on a host.
- **Not run.** Stage 1 and the first boot. The first host run records `native_proven` evidence in the stage-1 receipt.
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

Read on 2026-10-01 by the research unit or by unit W2:

- Microsoft:
  - https://learn.microsoft.com/en-us/windows/wsl/build-custom-distro (`oobe.command`, `oobe.defaultUid`; the
    `uid`/`defaultUid` 1000 recommendation; `--install --from-file`; WSL 2.4.4; updated 2025-09-12)
  - https://learn.microsoft.com/en-us/windows/wsl/basic-commands (`--install` options including `--location` and
    `--no-launch`; updated 2025-12-01)
  - https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro (`--import` starts as root; user and `[user] default`;
    `wsl --terminate`; updated 2024-07-16)
  - https://learn.microsoft.com/en-us/windows/wsl/wsl-config ("The 8 second rule"; `[user] default`;
    `instanceIdleTimeout` 15000; `distributionInstallPath`; updated 2026-09-16)
  - https://learn.microsoft.com/en-us/windows/wsl/systemd (`systemctl status` and
    `systemctl list-unit-files --type=service`; updated 2025-03-17)
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
    application and profile names; updated 2025-11-12)
- Canonical and Ubuntu:
  - https://documentation.ubuntu.com/wsl/stable/howto/cloud-init/ (`%USERPROFILE%\.cloud-init\<instance>.user-data`; the
    NOPASSWD user example)
  - https://documentation.ubuntu.com/wsl/stable/howto/install-ubuntu-wsl2/ (Method 1, WSL 2.4.10)
  - https://ubuntu.com/blog/ubuntu-wsl-new-format-available (WSL 2.4.8; `wsl --install --from-file`)
  - https://releases.ubuntu.com/24.04.5/SHA256SUMS and https://releases.ubuntu.com/noble/SHA256SUMS
  - https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl (streamed and hashed)
  - https://manpages.ubuntu.com/manpages/noble/en/man8/useradd.8.html (`SUB_UID_COUNT` allocation)
  - https://manpages.ubuntu.com/manpages/noble/en/man8/usermod.8.html (`--add-subuids`, `--add-subgids`)
  - https://github.com/ubuntu/wsl-setup at `86a561d5149a9d76ec3c9b3ce2745e7ebca5f2ad`
- cloud-init:
  - https://docs.cloud-init.io/en/latest/reference/datasources/wsl.html (lookup order, Landscape precedence,
    requirements, the default-user example)
  - https://docs.cloud-init.io/en/latest/reference/modules.html (Users and Groups: `uid`, `lock_passwd` default `true`,
    `sudo`)
  - https://docs.cloud-init.io/en/latest/reference/cli.html (`status --long`, exit codes 0, 1 and 2)
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
