# A new distro from the official Ubuntu WSL image (stage 1 and first boot)

Added after `v2026.09.26.2`, with its templates under [`adoption/templates/wsl/`](../templates/wsl/) and the record
[`docs/decisions/2026-10-01-new-wsl-distro-recipe.md`](../../docs/decisions/2026-10-01-new-wsl-distro-recipe.md), which
holds the decisions, their alternatives, the command table and every source. After the WSL 2.7.13 rehearsal stopped
at F1 on shared cgroups, run 2 on WSL 3.0.1.0 passed stage 1 and W5's path-A proofs, showed distinct cgroup namespaces,
and stopped at W5's paired rule on a shared-console collision. The template's getty mask was probed once; a complete
recipe run with it through F3 is still owed. Start with R1 and record the stage-1 receipt described at the end.

This page creates a second WSL 2 distribution on the existing Windows host from the selected Canonical image,
`ubuntu-<RELEASE>-wsl-amd64.wsl`, gives it its default user without a prompt through cloud-init, and proves systemd, linger
and the user bus before stage 2, the repository's bootstrap. The workstation's distribution keeps running, stays the
default and is never shut down.

The page rehearses both image arms on separate throwaway names, which R1 then removes, before running for the real
`<Name>` ([Rehearsal first](#rehearsal-first)). Each run starts with P1 to P3, `sh` checks in the workstation's
distribution that change nothing on the host; it shares the kernel and already has Ubuntu's keyring and cloud-init.
Stage 1 (W1 to W7) runs on the
Windows host in PowerShell. A session inside the workstation's WSL distribution runs each
PowerShell block as a `.ps1` file with
`/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w step.ps1)"`
([Windows-side commands from WSL](linux-wsl2.md#windows-side-commands-from-wsl)). Open each block's file with
`Start-Transcript -LiteralPath 'Z:\WSL\downloads\<Name>-stage1.log' -Append`, placed in W1 right after its first line
(which creates that folder), and end the file with `Stop-Transcript`. That private transcript is the raw install log the
receipt is cut from. The first boot (F1 to F11) runs inside the new
distribution as `<WSL_USER>`, from an interactive `/mnt/c/Windows/System32/wsl.exe -d <Name>` or, from a WSL session,
`/mnt/c/Windows/System32/wsl.exe -d <Name> -- bash -s < steps.sh`. F2's idle observation and F10 run from the Windows
side and F11 needs a login shell instead, as their sections say.

## Names and inputs

Canonical's [26.04 release notes](https://documentation.ubuntu.com/release-notes/26.04/) and Microsoft's
[creation commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands) support the distribution and creation
route. Microsoft's command documentation is pinned in the decision record at `MicrosoftDocs/WSL`
`7b28cc1ee9b8ff672ada5e1c6c326d3573d703e5`, `WSL/basic-commands.md` and `WSL/build-custom-distro.md`.
These sources do not establish full-stack compatibility for either arm.

| Placeholder | Meaning | Rule |
| --- | --- | --- |
| `<RELEASE>` | `26.04.1` default or `24.04.5` rollback | the clean install uses 26.04.1; rollback applies only to a release-caused 26.04 failure with no in-release remedy; use the same release in W2, W4 and W6 |
| `<Name>` | the new distribution's name (`--name`) and the user-data file's name | letters, digits, `.`, `_`, `-`; not already registered (W1); a throwaway name for the rehearsal (R1) |
| `<Survivor>` | the already-running workstation distribution's name | W1's starred distribution; every removal checks interop there |
| `<COMMON_UNIT>` | a system service unit active in both distributions | include `.service`; for example, `cron.service` when both run it; W5 verifies it before reading its cgroup |
| `<WSL_USER>` | the Linux user cloud-init creates | `^[a-z_][a-z0-9_-]*$`, the rule of the image's `/usr/lib/wsl/wsl-setup` |
| `Z:\WSL\<Name>` | the install location (`--location`); WSL puts `ext4.vhdx` there | must not exist yet (W1) |
| `Z:\WSL\downloads` | the image, its checksum list and the private logs | outside the Windows profile, so its path names no user |
| `<checkout>` | the Windows path of a checkout of `origin/main` holding these templates | from a WSL session: `wslpath -w .` in the checkout |
| `<host>` | the host value file `adoption/hosts/<host>.json` | `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, the bootstrap's `--host` rule |
| `<id>` | the adoption profile stage 2 installs | a `profiles[].id` of `adoption/manifest.json` |

The controlled release pins below come from Canonical's signed sums and Microsoft's catalog at
`8bc98bc33b246fe66710eec9eaa1b24c323da987`. The merged
[definitive manifest](../../evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json) names
Ubuntu 26.04.1 LTS (Canonical WSL image) as the single default. Ubuntu 24.04.5 is the named rollback, used only for a
release-caused 26.04 failure with no in-release remedy. The rehearsal's host cgroup failure is not such a release
failure, and neither image has full new-host acceptance.

| Release | Image file | Catalog entry | SHA-256 | Observed download bytes |
| --- | --- | --- | --- | --- |
| 26.04.1 | `ubuntu-26.04.1-wsl-amd64.wsl` | `Ubuntu-26.04` | `48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104` | 418,495,746; rehearsal run 2, 2026-10-02 |
| 24.04.5 | `ubuntu-24.04.5-wsl-amd64.wsl` | `Ubuntu-24.04` | `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e` | 388,975,696; historical artifact check |

## Host-wide rules

- No `.wslconfig` change, no `wsl --update` and never `wsl --shutdown`, which stops every distribution, the workstation's
  included. The only stop is `wsl --terminate <Name>`, for the new distribution. W1 reads two keys of `.wslconfig` with
  `Select-String`; no command here writes, copies or edits it.
- The default distribution stays the workstation's: nothing here sets a default, W1 records the starred line of
  `wsl.exe --list --verbose` and W4 and W5 prove it unchanged.
- This recipe adopts stable WSL 3.0.1 or later for a second systemd distribution, and requires it before W4 or any W6
  import. WSL 2.7.13, the release of the 2026-10-02 rehearsal, has a shared cgroup tree: equal user uids collide, and a
  system-unit stop or restart can act on another distribution's processes.
  Microsoft's [2.9.8 pre-release notes](https://github.com/microsoft/WSL/releases/tag/2.9.8) name
  [PR #40519](https://github.com/microsoft/WSL/pull/40519), which isolates distro cgroups; the
  [2.9.13 pre-release notes](https://github.com/microsoft/WSL/releases/tag/2.9.13) name
  [PR #41512](https://github.com/microsoft/WSL/pull/41512), which creates their namespaces. Neither pre-release is
  adopted: [3.0.1](https://github.com/microsoft/WSL/releases/tag/3.0.1) is the first stable release with both. The host
  was updated to WSL 3.0.1.0 on 2026-10-02 and passed its check (rootless container, interop, user manager);
  run 2 observed distinct cgroup namespaces, local process ids and two active user managers while both distributions
  ran. W1 records the version; W5 must repeat the isolation proof before F1 changes anything.
- An install with a single systemd distribution, with no second systemd distribution running, can still use WSL
  2.4.10 or later. That is the conservative install-only minimum: Microsoft gives 2.4.4, Ubuntu's announcement
  2.4.8 and Ubuntu's install guide 2.4.10. This page keeps the workstation running and therefore requires 3.0.1.
  Later releases also change the first launch:
  microsoft/WSL#40941 (after the first-run setup, files created from Windows are owned by 0:0) is fixed by PR #40977,
  which ships first in 2.9.8, a pre-release, and in 3.0.1; tags 2.7.13 and 2.7.14 lack it. On 2.7.13, W7 terminated
  `<Name>` once after the first launch and probed a file's owner before anything else was written from Windows. Updating
  WSL is the keys lane's action, and the cgroup prerequisite must hold before this page proceeds.
- `.wslconfig` is global, so the new distribution inherits the workstation's settings, among them
  `networkingMode=mirrored`, `swap` and the two idle keys that W1 reads and F2 observes.
- WSL 2 distributions share one network namespace
  ([Listeners and ports](linux-wsl2.md#listeners-and-ports)): every listener of the new distribution competes with the
  workstation's for the same ports. F8 picks the host file's ports outside the workstation's set.
- The VM console is shared: both distributions expose `/dev/tty1` as character device 4,1 of the same kernel.
  Their enabled `getty@tty1.service` units use `TTYPath=/dev/tty1`, `TTYVHangup=yes`, `Restart=always` and
  `RestartSec=0`, so competing gettys receive SIGHUP and restart until both hit the start limit.
  Source review at microsoft/WSL tag `3.0.1`:
  [`src/linux/init/init.cpp:363-365`](https://github.com/microsoft/WSL/blob/3.0.1/src/linux/init/init.cpp#L363-L365)
  masks `console-getty.service` because the tty devices are shared
  ([PR #14490](https://github.com/microsoft/WSL/pull/14490), merged 2026-04-09, "Fixes #13595");
  [`validate-modern.py:27-40`](https://github.com/microsoft/WSL/blob/3.0.1/distributions/validate-modern.py#L27-L40)
  discourages that unit but does not list `getty@tty1.service`; a maintainer in
  [issue #13595](https://github.com/microsoft/WSL/issues/13595) recommends disabling getty and adjacent units in WSL.
  The user-data masks `getty@tty1.service` in the new distribution before systemd starts it (W5); the workstation's
  unit is never touched. A host whose other systemd distributions keep an unmasked getty will see both fail whenever
  two of them run; masking it there is the host owner's decision, outside this page.
- The official first launch writes to Windows by design. WSL adds a Start-menu shortcut and a Windows Terminal profile for
  the distribution, and the image's `wsl-setup` copies the Ubuntu Sans Mono font into
  `%LOCALAPPDATA%\Microsoft\Windows\Fonts` and registers it under `HKCU` when that file is missing. The generated
  terminal profile may stay; hide it in Windows Terminal if it duplicates the fragment profile of F10.

## Rehearsal first

Run 2 on WSL 3.0.1 passed stage 1 and W5's path-A proofs and showed distinct cgroup namespaces, then stopped at W5's
paired rule on the console collision. Probe E1 tested the template's getty mask once outside the recipe; a complete
recipe run with it through F3 is still owed.

### R1. Rehearse on a throwaway name, then remove it

Run the page once on a throwaway distribution before the real one. For that run `<Name>` is a throwaway name that no
other distribution uses, never the real `<Name>` and never the workstation's, and `Z:\WSL\<Name>` is its own new folder.
Run it through F3: P1 to P3, W1 to W7 (W6 only after the W5 marker) and F1 to F3, recording P3's baseline and W5's
second count of storage errors, W5's `cloud-init schema --system` (path A), W7's file-ownership probe and F2's idle
observation. Run 2 observed the storage readings and image schema on 3.0.1; the corrected template and complete run
through F3 remain owed. Record the rehearsal's name, result, creation path and those observations in the receipt's
`rehearsal` block. Every host-wide rule holds: the rehearsal names only its own distribution, and R1 terminates and
unregisters only that literal name. A rehearsal that stopped before W4 installed nothing, and R1 has nothing to remove.

Rehearse both `26.04.1` default and `24.04.5` rollback on separate throwaway names, with the same checkout, user-data,
profile, Windows driver and host-wide settings. 26.04.1 is the single default for the clean install; 24.04.5 returns
only on a release-caused 26.04 failure with no in-release remedy. Comparison arms stay on throwaway distributions.
Before removal, extend each successful run through F9 using the existing bootstrap and its native recipes, then run
the comparison probes below from the workstation's second-instance session (the PowerShell block is launched through
the same Windows-side route as W1). Each `wsl.exe -d` targets that arm's literal throwaway `<Name>` and its default user.
F1 to F3 and the probes test first boot and the user manager from a second instance; they do not assume the 24.04.5
historical receipts are acceptance on this new host.

The following criteria are the preregistered ones for both arms with the amendments of 2026-10-02 made before any
comparison ran, recorded in the [decision record](../../docs/decisions/2026-10-01-new-wsl-distro-recipe.md).
Preserve a failed or skipped criterion with its returned output; neither a missing comparison nor a host version
check qualifies an arm. Both arms' full new-host acceptance is owed; run 2 stopped at W5's paired rule.

| Criterion | Same required observation for each arm | Primary source or accepted recipe |
| --- | --- | --- |
| `first_boot` | W5 exits 0 without the user/OOBE failure markers; default uid 1000, retained cloud-init results, the selected image's own schema check and F1's pass condition | W5, cloud-init tag 26.1; Microsoft creation docs pinned above; each image's inspected `wsl-setup` |
| `systemd_user_from_second_instance` | F2 records linger and idle behavior; F3 and the second-instance probes show a user-owned directory/socket and user manager `running` | F1 to F3; Microsoft systemd guide at the pinned revision; systemd v255 references in the decision record; 259 lifecycle acceptance remains owed |
| `wsl_gpu` | `/dev/dxg` is a character device and native `nvidia-smi` exits 0 with the Windows-provided GPU visible on the same driver; record limited WSL features and any failure | [Microsoft GPU guide](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute), [NVIDIA WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html); no Linux driver installation |
| `uv_cpython_3_13` | The bootstrap's uv runs a separate managed CPython 3.13 and prints `Python 3.13.x`, exit 0; the system Python version is recorded separately | F9 and `adoption/bootstrap.md`'s `uv run --no-project --python 3.13` prerequisite command; installed uv 0.12.17 `run --help` confirms both selectors |
| `node_24` | The bootstrap's selected Node starts and prints `v24.21.0`, exit 0; retain any loader/package failure | F4, F9 and `adoption/pins-linux-x86_64.json`'s official Node 24.21.0 tarball |

```powershell
wsl.exe -d '<Name>' --exec bash -lc 'stat -c "%U %F" "/run/user/$(id -u)" "/run/user/$(id -u)/bus"'
wsl.exe -d '<Name>' --exec systemctl --user is-system-running --wait
wsl.exe -d '<Name>' --exec test -c /dev/dxg
wsl.exe -d '<Name>' --exec /usr/lib/wsl/lib/nvidia-smi
wsl.exe -d '<Name>' --exec bash -lc 'python3 --version'
wsl.exe -d '<Name>' --exec bash -lc 'uv run --no-project --python 3.13 python --version'
wsl.exe -d '<Name>' --exec bash -lc 'node --version'
```

Record these per-arm observations in `comparison_arms` alongside each rehearsal's schema, ownership, storage and idle
observations. The inspected 26.04.1 system interpreter is Python 3.14.4-1ubuntu0.1 (its `python3` metapackage is
3.14.3-0ubuntu2); it is not the toolkit's CPython 3.13 migration acceptance. uv selects 3.13 separately.
GPU visibility and interpreter/version startup are bounded criteria; the full stack, GPU workloads and model behavior
still require their own native acceptance. Complete every criterion for the default before accepting the clean install;
the same criteria apply if a release-caused failure makes the rollback necessary.

After F3 and the preregistered comparisons, read the list first and remove the throwaway distribution. When every proof held, no export is
needed:

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --list --quiet
wsl.exe --terminate '<Name>'
wsl.exe --unregister '<Name>'
wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'
if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }
wsl.exe --list --verbose
```

When a proof failed after W4 installed it, keep the failed rehearsal first, by W6's export rule: the export comes before
`--unregister` in the same block, and a nonzero exit throws while the name is still registered. A rehearsal that took
path B already exported its first attempt in W6; this export keeps the state it failed in.

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --list --quiet
wsl.exe --terminate '<Name>'
wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-rehearsal.tar'
$LASTEXITCODE
if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }
(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-rehearsal.tar').Hash.ToLowerInvariant()
(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-rehearsal.tar').Length
wsl.exe --unregister '<Name>'
wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'
if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }
wsl.exe --list --verbose
```

After every `--unregister`, the check runs in `<Survivor>`: `/proc/sys/fs/binfmt_misc/WSLInterop` must exist and the
Windows executable `/mnt/c/Windows/System32/cmd.exe /d /c ver` must launch with exit 0. Linux shells on this page call Windows executables by full path, because a distribution may set `appendWindowsPath=false` (the workstation does), and then a bare name is not found even when interop works. On WSL 2.7.13 the rehearsal's unregister removed this VM-wide
registration on the surviving distribution, and `sudo systemctl restart systemd-binfmt` there restored it. That restart
is no remedy on the adopted release: on 3.0.1 the registration survived both unregisters of 2026-10-02, in run 2 and
probe E1. WSL mounts `/proc/sys/fs/binfmt_misc/status` read-only, so that one distribution
cannot flush the VM-wide registrations ([PR #40621](https://github.com/microsoft/WSL/pull/40621)), and that restart
itself exits 1 (F1 gives the reason). The guard stops the block when either observation fails. A failed check on 3.0.1
is a finding for review, not a fault to repair: stop, do not import or provision another distribution, and record these
observations from a native shell in the surviving distribution, after the new distribution has been removed:

```sh
test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver
ls /proc/sys/fs/binfmt_misc
systemctl status systemd-binfmt.service --no-pager
```

Proof: nothing here repairs anything. The first line repeats the check from a native shell, the second lists the
registered formats, which shows whether `WSLInterop` is among them, and the third prints the unit's state and log
lines. Record the returned output of all three, and of the failed check, in the receipt (`interop_after_unregister`),
then stop for review: never restart, stop or start a unit, and never import or provision another distribution. W5's
failed-proof removal and W6's removal use this same check and recovery. If W5 already removed a failed rehearsal,
record its export and do not remove that name again in R1.

Proof: the first `--list --quiet` names the throwaway distribution; the last `--list --verbose` no longer lists it, and
its starred line is still W1's. A failed rehearsal's export goes into the `rehearsal` block with its SHA-256 and size,
and the real run waits until the failure is understood. The rehearsal's private transcript and its user-data file under
`%USERPROFILE%\.cloud-init` stay; record whether WSL's Start-menu entry and terminal profile for the throwaway name
outlive `--unregister`. After the required comparison records, run the page again from P1 for the default real
`<Name>`, or the qualified rollback, without R1.

## Pre-checks in the workstation distribution

P1 to P3 run as `sh` in the workstation's distribution, before W1, so before anything is downloaded on Windows or
installed. They write only into new temporary directories and change nothing on the host. They need an existing Ubuntu
distribution with `ubuntu-keyring`, `gpgv`, `curl` and `cloud-init`; this page's host class has one, the workstation's.

### P1. Signed checksums

W2 checks the image against the hash this page pins and against Canonical's `SHA256SUMS`, and nothing there checks that
list's signature. Canonical signs it in `SHA256SUMS.gpg`, beside it. Ubuntu's verification tutorial
(https://ubuntu.com/tutorials/how-to-verify-ubuntu, read 2026-10-01) fetches the keys from a keyserver and runs
`gpg --verify`, noting "Ubuntu and most variants come with the relevant keys pre-installed". This block uses the keyring
the workstation's Ubuntu installs, from the `ubuntu-keyring` package, and `gpgv`, with no key import. Both files go into
an empty temporary directory, which is also `gpgv`'s home, so no GnuPG home of the user is read or written.

```sh
for RELEASE in 26.04.1 24.04.5; do
SUMS_DIR="$(mktemp -d)"
curl -fsSL -o "$SUMS_DIR/SHA256SUMS" "https://releases.ubuntu.com/$RELEASE/SHA256SUMS" || exit 1
curl -fsSL -o "$SUMS_DIR/SHA256SUMS.gpg" "https://releases.ubuntu.com/$RELEASE/SHA256SUMS.gpg" || exit 1
gpgv --homedir "$SUMS_DIR" --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg "$SUMS_DIR/SHA256SUMS.gpg" "$SUMS_DIR/SHA256SUMS"
if [ "$?" -ne 0 ]; then exit 1; fi
grep -F " *ubuntu-$RELEASE-wsl-amd64.wsl" "$SUMS_DIR/SHA256SUMS" || exit 1
done
```

Proof: both downloads exit 0; `gpgv` exits 0 and prints `using RSA key 843938DF228D22F7B3742BC0D94AA3F0EFE21092` and
`Good signature from "Ubuntu CD Image Automatic Signing Key (2012) <cdimage@ubuntu.com>"` for each release; `grep` prints
each image's signed line with its exact hash from the release table. Both signed sums must pass, including the arm not
selected for this run. The coordinator's preserved checks already passed for both (decision record, Evidence classes);
reuse matching evidence for this authoring unit. A
`BAD signature`, a missing key or any other nonzero exit stops the run with nothing installed.

### P2. The user-data schema

Added after `v2026.09.26.2`: this renders `adoption/templates/wsl/cloud-init.user-data.template` with `<WSL_USER>`
before any boot and validates it with cloud-init's own schema check. The render is F8's `string.Template` program, which
writes the same bytes as W3's literal replace (W3 says why). Run it from the root of the checkout that `<checkout>` names,
for the selected image's user-data. The workstation's cloud-init checks against its own version's schema, which
`cloud-init --version` records. This host check is not image qualification. The inspected 26.04.1 image packages
cloud-init 26.1-0ubuntu3~26.04.1; the historical 24.04.5 image packages 26.1-0ubuntu1~24.04.1. W5 records the selected
image's version and validates the provisioned user-data with its own `cloud-init schema --system` on path A. Canonical's
[cloud-init WSL guide](https://ubuntu.com/wsl/docs/stable/howto/cloud-init/) assumes 24.04 or 22.04; it does not qualify
26.04. The 26.04.1 rehearsal's own schema check passed on both 2.7.13 and 3.0.1; each run must repeat it, and 24.04.5
remains unrun.

```sh
RENDER_DIR="$(mktemp -d)"
python3 -c 'import string, sys; sys.stdout.write(string.Template(open(sys.argv[1], encoding="utf-8").read()).substitute(WSL_USER=sys.argv[2]))' adoption/templates/wsl/cloud-init.user-data.template '<WSL_USER>' > "$RENDER_DIR/<Name>.user-data"
cloud-init --version
cloud-init schema -c "$RENDER_DIR/<Name>.user-data"
sha256sum "$RENDER_DIR/<Name>.user-data"
```

Proof: `cloud-init schema -c` prints `Valid schema` with the file's path and exits 0; a warning that no datasource was
detected may come first. An invalid file prints `Invalid user-data` and `Error: Invalid schema: user-data` and exits 1:
stop. Record the `sha256sum` value. W3 prints the SHA-256 of the file it writes on Windows, and the two must be equal.

### P3. Kernel storage errors

WSL 2 distributions share one kernel, so the workstation's kernel journal shows the storage errors the new distribution
would meet. microsoft/WSL#41482 (https://github.com/microsoft/WSL/issues/41482, read 2026-10-01) reports continuous
`hv_storvsc` errors with WSL 2.7.12, kernel 6.18.33.2-2 and swap active, and systemd timeouts at boot
(`/sbin/init failed to start within 10000ms`). Its workaround, `swap=0` in the global WSL configuration and a WSL
shutdown, is outside this page. Without `sudo` the user cannot read the kernel journal, and `dmesg` holds only the
recent ring buffer, so this reads the journal of the current boot. It searches for the driver's name, not a device id,
and leaves out the driver's registration line, `hv_vmbus: registering driver hv_storvsc`, which every boot logs, and
the kernel's command-line echo. Run 2's baseline of `2` contained only `Command line:` and `Kernel command line:`
echoes naming `hv_storvsc.storvsc_max_hw_queues=4`; neither is a storage error. A count
over the whole boot cannot tell errors that are happening now from an old burst, so the count is
a baseline, not a verdict: the newest error line's age decides here, and W5 counts again after the first launch.

```sh
sudo journalctl -k -b 0 --no-pager | grep hv_storvsc | grep -Evc 'registering driver hv_storvsc|[Cc]ommand line:'
sudo journalctl -k -b 0 --no-pager -o short-monotonic --no-hostname | grep hv_storvsc | grep -Ev 'registering driver hv_storvsc|[Cc]ommand line:' | tail -n 1
cat /proc/uptime
swapon --show
```

Proof:

- The first line prints the count: record it as the baseline (`storage_errors`). A count of `0` makes the last `grep`
  exit 1, which is not a failure.
- The second line prints the newest error line, with its kernel time in seconds since boot in brackets, or nothing.
  `cat /proc/uptime` prints the seconds since boot now as its first number, and the difference is the line's age.
  An age of less than one hour (3600 seconds) means errors are happening now, and this stops the run before anything is
  installed: record the count, the line's time and its shape without device ids, name microsoft/WSL#41482 and leave the
  next step to the user, because the workaround changes the global WSL configuration and shuts WSL down. An older line,
  or none, lets the run continue. The one-hour threshold is this recipe's choice, not an upstream figure.
- One exception, added on 2026-10-02: a newest line whose kernel time an earlier run of this page already recorded as
  its own attachment-window line (W5, `storage_errors.new_lines`) is known and does not stop the run; record that it
  is the earlier run's line. Run 2 and probe E1 each left exactly one such line in their install windows (7118.5 s and
  7678.6 s), so a second arm rehearsed within the hour would otherwise stop on its predecessor's line. A line that no
  earlier receipt explains keeps the rule.
- The kernel time decides, not the journal's wall-clock stamp: journald stamps a kernel line when it reads it, and a
  restart of the workstation distribution reads the kernel's ring buffer again and stamps old lines anew.
- Record `swapon --show`: active swap is the issue's condition, not a failure by itself.

## Stage 1 on the Windows host

### W1. Preflight and the log folder

The first line creates `Z:\WSL\downloads`, which holds the transcript, so it comes before the transcript starts. Nothing
else in W1 writes.

```powershell
New-Item -ItemType Directory -Force -Path 'Z:\WSL\downloads'
$env:WSL_UTF8 = '1'
wsl.exe --version
wsl.exe --list --verbose
wsl.exe --list --quiet
Test-Path -LiteralPath 'Z:\WSL\<Name>'
Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\<Name>.user-data')
Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml')
Select-String -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\.cloud-init\agent.yaml') -Pattern '^[A-Za-z_][A-Za-z0-9_-]*:' -ErrorAction SilentlyContinue
Select-String -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig') -Pattern '^\s*\[', '^\s*instanceIdleTimeout\s*=', '^\s*vmIdleTimeout\s*=' -ErrorAction SilentlyContinue
Get-PSDrive -Name Z | Select-Object -Property Name, Used, Free
```

Then record this baseline natively in the already-running workstation distribution, as its default user and without
`sudo`. It holds the same five observations that W5 reads from both distributions, taken before anything is imported:

```sh
id -u
systemctl is-system-running
systemctl --failed --no-legend --plain
systemctl is-active "user@$(id -u).service"
readlink /proc/self/ns/cgroup
```

Record each command's exit separately. `systemctl is-system-running` exits 1 for `degraded`, which is expected and
recorded; the proof reads the printed values. The failed-unit value is the first column of each printed row.

Proof, recorded in the receipt's `host` block:

- `wsl.exe --version` starts with `WSL version:` and a version of 3.0.1 or later for this second systemd distribution.
  An older version stops the run before W4 or W6 imports anything. The reason is the shared cgroup tree on 2.7.x;
  PR #40519 isolated distro cgroups and PR #41512 created their namespaces, first together in stable 3.0.1
  (the release notes linked in Host-wide rules).
- Record the five lines as the workstation's baseline (`workstation_baseline`): the uid, the system state, the names of
  the failed units, the user manager's state and the cgroup namespace. `cgroup:[4026531835]` is the kernel's initial
  cgroup namespace, `PROC_CGROUP_INIT_INO` in Linux's
  [`include/linux/proc_ns.h`](https://github.com/torvalds/linux/blob/v6.18/include/linux/proc_ns.h).
  A noninitial namespace is necessary but does not prove isolation. The shell's own
  `/proc/self/ns/cgroup` needs no `sudo` and equals `/proc/1/ns/cgroup` on the updated host. W1's version
  precondition and W5's paired check while both distributions run are required; record what the updated host actually
  prints.
- The workstation's baseline passes only when all four hold: its uid equals the new distribution's planned default
  uid `1000`; its system state is `running` with no failed unit, or `degraded` with its failed set contained in
  {`systemd-binfmt.service`, `getty@tty1.service`}; its user manager is `active`; and its cgroup namespace is not
  `cgroup:[4026531835]`. Anything else stops the run before W4 and before any W6 import, because W5 compares the
  workstation with this baseline and its proof could not hold.
- `getty@tty1.service` is allowed in that failed set only as the leftover of an earlier collision on the shared
  console. When it is there, also run the following read-only command and record it as `getty_tty1_result`;
  `Result=start-limit-hit` is required, and another result stops the run. The workstation's unit messages are not
  proved again here: it is compared with itself, and F1 proves the message for the new distribution.

```sh
systemctl show getty@tty1.service -p Result -p NRestarts
```

- The starred line of `--list --verbose` names the workstation's distribution (`default_distribution_before`).
- `<Name>` is not a line of `--list --quiet`, and the first `Test-Path` prints `False`. WSL refuses a name or an install
  folder another registration already uses and creates the folder itself.
- The second `Test-Path` prints `False`. A Landscape file at that path replaces the local user-data: cloud-init 26.1 loads
  it first and then never reads the file of W3 (`cloudinit/sources/DataSourceWSL.py:241-270` and `:465-476`).
- The third `Test-Path` prints `False`, and the `agent.yaml` `Select-String` line then prints nothing. When `agent.yaml` exists (Ubuntu
  Pro for WSL writes it), that line lists its top-level keys: record them, and stop if `users:` or `write_files:` is among
  them. cloud-init 26.1 merges `agent.yaml` over the user-data one top-level key at a time, and an agent key replaces the
  user-data key entirely (`DataSourceWSL.py:317-336`, called at `:490`). Either key would replace the user or the
  `[user] default` of W3.
- The `.wslconfig` line only reads: it prints the file's section headers and its `instanceIdleTimeout` and
  `vmIdleTimeout` lines, or nothing when the file or the keys are absent. Record both values in the receipt's
  `idle_keys`; a missing key has its default. `instanceIdleTimeout` (under `[general]`, default 15000 ms, `-1` turns it
  off) is how long a distribution stays up after its last Windows-side client exits; `vmIdleTimeout` (under `[wsl2]`,
  default 60000 ms) is the VM's. Without `instanceIdleTimeout=-1`, `<Name>` and its user services stop about
  `instanceIdleTimeout` after the last client exits (15 seconds by default), and issue reports say linger does not
  prevent it; F2 observes it. Changing either key is the user's decision, outside this page.
- `Free` on `Z:` is recorded. The historical 24.04.5 image unpacked to about 1.3 GB; the 26.04.1 unpacked size remains
  unmeasured. Stage 2 adds its tools.

Stop on any other result.

### W2. Download and verify the image

The expected sha256 is published twice, by Canonical next to the image and by Microsoft's WSL distribution catalog.
This block reads the catalog at the commit of 2026-09-14 (#41465), choosing `Ubuntu-26.04` or `Ubuntu-24.04` for the selected
release. It is the
only hash check before W4 installs the file: at WSL 2.7.13, `wsl --install --from-file` checks no hash
(`WslClient.cpp:500-537`). The online `wsl --install Ubuntu-24.04` does compare its download with the catalog entry's
`Sha256` (`WslInstall.cpp:36-50`, `:315`), but it reads the catalog from WSL's `master` branch at install time; this
page installs a pinned file whose hash the operator sees, and P1 has tied that hash to Canonical's signature.

```powershell
$ProgressPreference = 'SilentlyContinue'
$Release = '<RELEASE>'
switch ($Release) {
    '26.04.1' { $Expected = '48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104'; $CatalogName = 'Ubuntu-26.04' }
    '24.04.5' { $Expected = 'bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e'; $CatalogName = 'Ubuntu-24.04' }
    default { throw 'unsupported release: do not download or install' }
}
$Image = "ubuntu-$Release-wsl-amd64.wsl"
$ImagePath = "Z:\WSL\downloads\$Image"
$ImageUrl = "https://releases.ubuntu.com/$Release/$Image"
$SumsPath = "Z:\WSL\downloads\$Release-SHA256SUMS"
Invoke-WebRequest -UseBasicParsing -Uri $ImageUrl -OutFile $ImagePath
Invoke-WebRequest -UseBasicParsing -Uri "https://releases.ubuntu.com/$Release/SHA256SUMS" -OutFile $SumsPath
$Published = (Select-String -LiteralPath $SumsPath -Pattern (' \*' + [regex]::Escape($Image) + '$')).Line.Split(' ')[0]
$Listed = ((Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/microsoft/WSL/8bc98bc33b246fe66710eec9eaa1b24c323da987/distributions/DistributionInfo.json').Content | ConvertFrom-Json).ModernDistributions.Ubuntu | Where-Object Name -eq $CatalogName
$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ImagePath).Hash.ToLowerInvariant()
"computed $Actual published $Published listed $($Listed.Amd64Url.Sha256) url $($Listed.Amd64Url.Url)"
if ($Actual -ne $Expected -or $Published -ne $Expected -or $Listed.Amd64Url.Sha256 -ne $Expected -or $Listed.Amd64Url.Url -ne $ImageUrl) { throw 'sha256 mismatch: do not install' }
(Get-Item -LiteralPath $ImagePath).Length
```

Proof: the printed line shows the selected release's exact hash three times and its actual release URL from the pinned
catalog, as listed in the release table. `Get-FileHash` hashes the entire downloaded image. Record `Length` as this run's
actual image size; run 2 measured 418,495,746 bytes for 26.04.1, while 24.04.5's historical stream measured
388,975,696 bytes. A `throw`
stops stage 1 with nothing installed. Record `.Hash` only: `Get-FileHash` also prints the file's path.

### W3. Render the user-data before any boot

Added after `v2026.09.26.2`: the template is `adoption/templates/wsl/cloud-init.user-data.template`. Its only
placeholder is `${WSL_USER}`, so this literal replace writes the same bytes as Python's `string.Template`, and .NET's
`WriteAllText` writes UTF-8 without a byte order mark, which keeps `#cloud-config` as the file's first bytes. The file name
must be the instance name: the cloud-init WSL datasource reads
`%USERPROFILE%\.cloud-init\<InstanceName>.user-data` before any less specific file. The `Get-FileHash` line prints the
written file's SHA-256 for comparison with P2's, which validated the same render.

```powershell
New-Item -ItemType Directory -Force -Path (Join-Path $env:USERPROFILE '.cloud-init')
$Text = [System.IO.File]::ReadAllText('<checkout>\adoption\templates\wsl\cloud-init.user-data.template').Replace('${WSL_USER}', '<WSL_USER>')
[System.IO.File]::WriteAllText((Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data'), $Text)
Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -TotalCount 1
Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -Pattern '^- name: ', '^    default='
(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data')).Hash.ToLowerInvariant()
Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -SimpleMatch -Pattern '${'
```

Proof: the first line is `#cloud-config`; the two matches end in `<WSL_USER>`; the hash equals P2's `sha256sum` value;
the last command prints nothing. The file holds no secret: the user's password stays locked and sudo needs none.

### W4. Install without launching

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --install --from-file 'Z:\WSL\downloads\ubuntu-<RELEASE>-wsl-amd64.wsl' --name '<Name>' --location 'Z:\WSL\<Name>' --no-launch
$LASTEXITCODE
wsl.exe --list --verbose
```

Proof: the output is `Installing: Z:\WSL\downloads\ubuntu-<RELEASE>-wsl-amd64.wsl` with the selected release filled in, then
`Distribution successfully installed. It can be launched via 'wsl.exe -d <Name>'`; `$LASTEXITCODE` prints `0`;
`--list --verbose` shows `<Name>` as `Stopped` at version 2 with the starred line unchanged. `--install --from-file`
registers the distribution with its first-run setup enabled and `--no-launch` boots nothing, so cloud-init has not run yet.

### W5. First launch, without a terminal

Run nothing in `<Name>` before this launch. WSL runs the image's first-run command, `/usr/lib/wsl/wsl-setup`, as root
only for a launch with no command, which the `cmd.exe` line is; `--exec` probes never run it, and one started while it
runs prints `Waiting for OOBE command to complete for distribution "<Name>"...` and waits. With standard input at end of
file nothing can answer a prompt, so the launch either succeeds unattended or fails at once. `wsl-setup` waits for
cloud-init, reuses the user cloud-init created, keeps the `[user] default` cloud-init appended and writes
`/etc/cloud/cloud-init.disabled`; WSL then makes uid 1000 the default user. Until that launch the registered default
user is root, so an earlier `id -un` printing `root` says nothing about cloud-init.

```powershell
$env:WSL_UTF8 = '1'
cmd.exe /d /c "wsl.exe -d <Name> < NUL"
$LASTEXITCODE
wsl.exe -d '<Name>' --exec id -un
wsl.exe -d '<Name>' --exec id -u
wsl.exe -d '<Name>' --exec systemctl is-enabled getty@tty1.service
wsl.exe -d '<Name>' --exec systemctl show getty@tty1.service -p LoadState -p ActiveState -p NRestarts
wsl.exe -d '<Name>' -u root --exec cloud-init --version
wsl.exe -d '<Name>' -u root --exec cloud-init status --long
wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/result.json
wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/status.json
wsl.exe -d '<Name>' -u root --exec cloud-init schema --system
wsl.exe -d '<Name>' -u root --exec cat /etc/wsl.conf
wsl.exe -d '<Name>' -u root --exec ls -l /etc/cloud/cloud-init.disabled
wsl.exe -d '<Name>' -u root --exec sudo -l -U '<WSL_USER>'
wsl.exe --list --verbose
```

Proof (path A, cloud-init provisioned the instance):

- `wsl: Failed to start the systemd user session` stops the run even when the launch exits 0. Record the warning
  and use the failed-proof recovery below; do not continue to F1 or try W6 as a remedy for that warning.
- The launch prints `Provisioning the new WSL instance <Name>` and `This might take a while...`, and `$LASTEXITCODE`
  prints `0`. The image's `wsl-setup` prints both lines, not WSL: for the historical 24.04.5 image, lines 117-118 at its version 0.5.10~24.04.2, Launchpad
  tag `import/0.5.10_24.04.2`, commit `74bfc89113bc7d46a4d9feb1e69cd6951fbc6908`.
- For 26.04.1, the inspected image packages `wsl-setup` 0.6.3ubuntu~26.04.1, matched to upstream tag `0.6.3`, commit
  `73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8` (`wsl-setup:122-123,155-156` and `ubuntu-insights.sh:15-19,114-142`).
  Its Insights script preserves existing native Linux/Windows consent; it prompts only when stdin is a terminal
  (`-t 0`). W5's NUL input takes its native noninteractive path. No command here invents consent or writes a global
  consent registry value. This source review is not first-boot acceptance.
- `id -un` prints `<WSL_USER>` and `id -u` prints `1000`.
- `systemctl is-enabled getty@tty1.service` prints `masked`; exit 1 is that command's normal exit for a masked unit.
  `systemctl show` prints `LoadState=masked`, `ActiveState=inactive` and `NRestarts=0`. The user-data's `bootcmd`
  masks the unit in cloud-init's network stage, before systemd starts it: the 26.04.1 image's
  `cloud-init-network.service` has `Before=systemd-user-sessions.service`, `getty@.service` has
  `After=systemd-user-sessions.service`, and `/etc/cloud/cloud.cfg` lists `bootcmd` in `cloud_init_modules`.
  These are source reviews of the pinned official image's own files, read for probe E1 on 2026-10-02, not a complete
  recipe run. In that probe the unit was masked and inactive with no restarts, cloud-init finished without errors,
  and the only failed unit was `systemd-binfmt.service`. The journal's `Failed to start getty@tty1.service.` line
  was the refused job of a masked unit, which did not appear in the failed-unit list.
- `cloud-init --version` records the selected image's packaged version before its own schema check; P2 recorded only
  the workstation's version.
- `cloud-init status --long` prints `status: disabled` and `boot_status_code: disabled-by-marker-file`. This line proves
  only that the marker is in place, because cloud-init 26.1 reports `disabled` once `/etc/cloud/cloud-init.disabled`
  exists, whatever its run did (`cloudinit/cmd/status.py:284-286` and `:385-386`).
  - Its `detail:` names `DataSourceWSL` while the provisioning boot is still up, and the marker after a restart.
  - Its `errors` come only from that boot's `/run/cloud-init/status.json` (`:407-419`, `:471-490`).
  - Exit 2 means recoverable errors (warnings) on that boot while the line still says `disabled`
    (`:158-163`, `:254-255`). Record them, as `status.json` below does.
  - `status: error` or exit 1 means that boot's run failed: stop.
- `/var/lib/cloud/data/result.json` holds `"datasource": "DataSourceWSL"` and `"errors": []`. cloud-init writes this file
  only when its final stage ends, and it collects the errors of every stage (`cloudinit/cmd/main.py:1017-1030`). Its
  presence proves the run completed; its empty list proves the run had no errors.
- `/var/lib/cloud/data/status.json` gives `init-local`, `init`, `modules-config` and `modules-final` each a `finished` time
  and empty `errors` (`main.py:915-929` and `:975-1015`). Record any `recoverable_errors` (warnings). Both files sit in
  cloud-init's persistent data directory, with only symbolic links under `/run` (`main.py:880-888`), so they outlive a
  restart.
- `cloud-init schema --system` prints a line matching `^\s*Valid schema user-data$` and exits 0: cloud-init accepted
  the instance's user-data, the check of Canonical's
  [WSL cloud-init how-to](https://ubuntu.com/wsl/docs/stable/howto/cloud-init/) (read 2026-10-01). It needs root
  (cloud-init 26.1, `cloudinit/config/schema.py:1388-1393`). With more than one data part a
  `Found cloud-config data types:` header comes first and the line is indented (`:1443-1458`, `:1492`); an invalid
  schema exits 1 (`:1493-1498`). The `schema` subcommand never reads the marker (`cloudinit/cmd/main.py:1240-1241`,
  `:1286-1293`). The 26.04.1 rehearsal returned `Valid schema user-data` after the marker on both host releases;
  each run must repeat that observation. Record the output (`schema_system`).
- `/etc/wsl.conf` holds `[boot]`, `systemd=true`, `[user]` and `default=<WSL_USER>`, each once.
- The marker file exists, and `sudo -l` lists `(ALL) NOPASSWD: ALL`.
- The starred line of `--list --verbose` is still W1's (`default_distribution_after`).

After the first launch and before F1, prove cgroup isolation from the already-running workstation distribution,
while both distributions run. Keep a client of `<Name>` open during the check. Choose `<COMMON_UNIT>` active in both
distributions, for example `cron.service` when both run it. Run this block natively in the workstation's shell;
the `wsl.exe -d` commands alone target the new distribution:

```sh
systemctl is-active '<COMMON_UNIT>'
/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec systemctl is-active '<COMMON_UNIT>'
cat '/sys/fs/cgroup/system.slice/<COMMON_UNIT>/cgroup.procs'
/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec sh -c 'systemctl is-active "user@$(id -u).service"'
```

Proof: both system-unit checks print `active` and exit 0; `cgroup.procs` contains local process ids and no `0` entry;
the new distribution's `user@<uid>.service` prints `active` and exits 0, for its default user's uid 1000. A `0` entry
is a process from another distribution's process namespace. An empty or unreadable file or a unit not active in both
cannot prove isolation and stops the run. On path B, W6's manual-user relaunch must repeat this proof and the paired
record below before W7 or F1; the initial OOBE prompt failure alone does not establish a default user's manager.
Nothing on the updated host is assumed from its version or namespace value.

Then record the same five observations from both running distributions at once, because a reading of one side does not
show the same uid, distinct namespaces and two healthy managers. Run this block natively in the workstation's shell,
after the cgroup block above and before F1. Its first five lines repeat W1's baseline commands, and its next five run
the same commands inside `<Name>`. Record each command's output and exit in its own receipt entry:

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

Proof: both distributions print the same uid; both user managers print `active`; the new distribution's system state
is `running` with no failed unit, or `degraded` with `systemd-binfmt.service` as its only failed unit (its message is
proved at F1); the two `cgroup:[...]` values differ from each other and neither is `cgroup:[4026531835]`; and all five
workstation values equal its own values recorded in W1 before the import, so the new distribution did not disturb it.
A `getty@tty1.service` in the new distribution's failed set, or one that newly appears in the workstation's, fails the
proof: the mask did not take effect before the unit started. Record all of it, with the WSL version and
kernel from W1 and the image revision from W2, in the receipt's `paired_isolation`: one object for the workstation and
one for `<Name>`, each with `uid`, `system_state`, `failed_units`, `user_manager` and `cgroup_namespace`.

When any W5 proof fails, or the user-session warning appears, stop the run and never stop or restart a unit in either
distribution. Terminate only the new distribution, export its failed state, and unregister only that name. Do not
take path B for any such failure. Record its cause (`cgroup`, `tty` or a short text); this recovery block serves every
failed W5 proof:

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --list --quiet
wsl.exe --terminate '<Name>'
wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-w5-failed.tar'
$LASTEXITCODE
if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }
(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-w5-failed.tar').Hash.ToLowerInvariant()
(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-w5-failed.tar').Length
wsl.exe --unregister '<Name>'
wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'
if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }
wsl.exe --list --verbose
```

Proof: the export exits 0 before deletion, its cause, hash and size are recorded in `w5_failure_export`, and `<Name>` is
gone with the starred line unchanged. The surviving distribution must retain `WSLInterop` and launch the Windows
executable. If it does not, R1's interop recovery (its records, then a stop for review) applies only after the new
distribution is removed. Keep the failure and stop for review; an upstream version claim does not replace the failed
isolation observation.

On both paths, right after the launch and before W6 or W7, count the storage errors again in the workstation
distribution, where P3 ran:

```sh
sudo journalctl -k -b 0 --no-pager | grep hv_storvsc | grep -Evc 'registering driver hv_storvsc|[Cc]ommand line:'
```

Proof: record both counts. On both paths, record P3's baseline before the import and `second_count` after the first launch.
An increase confined to the window in which the new disk is attached, before cloud-init starts, is recorded with the
new lines and does not stop the run. Any storage error after that window, or any provisioning step that fails with a
storage cause, stops the run.

Run 2 observed one real driver error (`cmd 0x2a`, `srb 0x4`, host `0xc00000a1`) at kernel time 7118.5 s, inside W4's
install window: the new disk was unmounted at 7126.9 s and cloud-init's `init-local` started at 7134.15 s. The written
window rule recorded that line without stopping the run; the second count of `3` also included the two command-line
echoes that the corrected filter now drops.

When the count increases, read the new lines with P3's second command and `tail -n` set to the difference, without
device ids. Compare their kernel times with the attachment window and W5's retained `status.json` `init-local` start.
If the window cannot be established, stop for review. Record the window and its lines in `storage_errors.new_lines`;
apply the same stop rule to later provisioning. A failure with a storage cause is exposure to microsoft/WSL#41482 and
stops the run before stage 2 (F9); its workaround changes the global WSL configuration and shuts WSL down, both
outside this page. A failed W5 without a storage cause keeps its own diagnosis.

How to tell that cloud-init did not provision the instance: the launch output contains
`Create a default Unix user account:` and `OOBE command "/usr/lib/wsl/wsl-setup" failed, exiting`, and the exit code is
not 0. WSL keeps the first-run setup pending. Only that prompt failure, with no other failed W5 proof, permits W6.

### W6. Path B: import and a manual user (only after the W5 marker)

`--unregister` deletes the distribution's disk. Read the list first and run it only on the literal new name, never on the
workstation's.

`--unregister` loses all data of the distribution permanently (Microsoft, "Basic commands for WSL"), including the failed
attempt's cloud-init logs, `/var/log/cloud-init*.log`, the instance directory `/var/lib/cloud/instance` and its
configuration. The transcript keeps only the console markers. Preserve the attempt first. Stop `<Name>`, then export it
with Microsoft's `wsl --export <Distribution Name> <FileName>`, which writes a snapshot of the distribution as a tar
file by default. The export goes into W1's log folder, and its SHA-256 and size go into the receipt's
`failed_attempt_export`. A nonzero export exit throws before `--unregister`, so `<Name>` stays registered with its disk.
To diagnose path A, read in the tar the cloud-init logs, the instance directory and, when the run got that far,
`/var/lib/cloud/data/result.json` and `status.json`. The tar holds the rendered user-data with `<WSL_USER>`, so it stays
private in `Z:\WSL\downloads` like the transcript; only its name, SHA-256 and size enter the receipt.

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --list --quiet
wsl.exe --terminate '<Name>'
wsl.exe --export '<Name>' 'Z:\WSL\downloads\<Name>-failed.tar'
$LASTEXITCODE
if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }
(Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Hash.ToLowerInvariant()
(Get-Item -LiteralPath 'Z:\WSL\downloads\<Name>-failed.tar').Length
wsl.exe --unregister '<Name>'
wsl.exe -d '<Survivor>' --exec sh -c 'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'
if ($LASTEXITCODE -ne 0) { throw 'interop failed: recover in the surviving distribution before continuing' }
wsl.exe --import '<Name>' 'Z:\WSL\<Name>' 'Z:\WSL\downloads\ubuntu-<RELEASE>-wsl-amd64.wsl' --version 2
wsl.exe -d '<Name>' -u root --exec cloud-init status --wait --long
```

Before the import, the surviving distribution's `WSLInterop` registration must exist and its Windows executable must
launch. If the guard throws, do not import: take R1's interop recovery there, which records the observations and stops
for review. W1's WSL 3.0.1 precondition still applies to this import.

An imported distribution starts as root and skips the first-run command. Whether cloud-init provisions it is not
documented. The `cloud-init status` line therefore only records the import's first boot:
- `done` or `error` when cloud-init ran;
- `disabled` with `boot_status_code: disabled-by-generator` when it found no datasource (`cloudinit/cmd/status.py:298-300`).

The next commands skip what already exists. Run them as root inside `<Name>`: in a shell from
`/mnt/c/Windows/System32/wsl.exe -d <Name> -u root`, or from a WSL session through
`/mnt/c/Windows/System32/wsl.exe -d <Name> -u root -- bash -s < path-b.sh`.

An import's first boot starts the getty before the first line below can run. The paired proof after the relaunch
decides: if the workstation's values differ from its baseline, stop and use W5's recovery block.

```sh
systemctl mask --now getty@tty1.service
id -u '<WSL_USER>' || useradd --create-home --uid 1000 --groups adm,cdrom,sudo,dip,plugdev --shell /bin/bash '<WSL_USER>'
printf '%s ALL=(ALL) NOPASSWD:ALL\n' '<WSL_USER>' > /etc/sudoers.d/90-wsl-default-user
chmod 0440 /etc/sudoers.d/90-wsl-default-user
visudo -cf /etc/sudoers.d/90-wsl-default-user
grep -q '^\[user\]' /etc/wsl.conf || printf '\n[user]\ndefault=%s\n' '<WSL_USER>' >> /etc/wsl.conf
touch /etc/cloud/cloud-init.disabled
```

The last line writes the marker the official first-run command writes after cloud-init. `/etc/wsl.conf` takes effect at
the next start, so terminate the new distribution only and wait until it is no longer running:

```powershell
wsl.exe --terminate '<Name>'
wsl.exe --list --running
wsl.exe -d '<Name>' --exec id -un
```

Proof: `visudo` prints `parsed OK`; `<Name>` is absent from `--list --running`; `id -un` prints `<WSL_USER>`. Repeat W5's
cgroup-isolation proof and its paired record while both distributions run, before W7 or F1, with their same failure
recovery. Then repeat W5's checks from `id -u` on, with three differences:
- `cloud-init status --long` reports `boot_status_code: disabled-by-marker-file` because the root block wrote the marker.
- `result.json` and `status.json` exist only if cloud-init ran on the import (open question 1). Record their contents, or
  their absence, instead of treating absence as a failure.
- skip `cloud-init schema --system`: when cloud-init never ran on the import, it exits 1 with
  `Error: Config file ... does not exist` (cloud-init 26.1, `cloudinit/config/schema.py:1428-1433`; a source reading, not
  a run). Record `skipped (path B)` as `schema_system`.

Record `path B` in the receipt.

### W7. Terminate once, then the file-ownership probe

Both paths run this, after W5's proof (path A) or after W6 (path B). On WSL 2.7.13 a file that Windows creates in a new
distribution after the first-run setup can be owned by 0:0. microsoft/WSL#40941
(https://github.com/microsoft/WSL/issues/40941, read 2026-10-01) reports it, and a contributor's reproduction ends: "The
file created will be 0:0 until the next wsl --shutdown", a command this page never runs. The fix, PR #40977
(https://github.com/microsoft/WSL/pull/40977, read 2026-10-01), explains: "Because the uid was cached before the OOBE is
complete. And this only recovers after a distro termination." It ships first in WSL 2.9.8, a pre-release, and in 3.0.1;
tags 2.7.13 and 2.7.14 lack it. So this step terminates `<Name>` once, relaunches it for the F steps and reads the owner
of an empty file created from Windows under the new user's home. Whether a terminate clears the state has not been
observed on WSL 3.0.1 on this host; the 2.7.13 rehearsal returned `1000:1000`, and this run must repeat the probe.

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --terminate '<Name>'
wsl.exe --list --running --quiet
wsl.exe -d '<Name>' --exec id -un
New-Item -ItemType File -Path '\\wsl.localhost\<Name>\home\<WSL_USER>\wsl-owner-probe'
wsl.exe -d '<Name>' --exec stat -c %u:%g '/home/<WSL_USER>/wsl-owner-probe'
Remove-Item -LiteralPath '\\wsl.localhost\<Name>\home\<WSL_USER>\wsl-owner-probe'
```

Proof: `<Name>` is absent from `--list --running --quiet` right after the terminate; `id -un` prints `<WSL_USER>`;
`stat` prints `1000:1000`; `Remove-Item` prints nothing. Record the owner as `ownership_probe`. `0:0` means the state
persists after a terminate: record it, and write nothing into the distribution from Windows (no
`\\wsl.localhost\<Name>` writes, no Explorer copies) until a WSL release with the fix or a decision changes that.

## First boot inside the new distribution

Run F1 to F8 as `<WSL_USER>` in `<Name>`, except F2's idle observation, which runs from the workstation's session.

### F1. systemd

```sh
systemctl is-system-running --wait
systemctl --failed --no-legend --plain
journalctl -b 0 -t systemd-binfmt --no-pager -n 4
systemctl list-unit-files --type=service --no-pager
```

Proof: `running` with no failed unit, or `degraded` when `systemctl --failed --no-legend --plain` lists exactly
`systemd-binfmt.service` and that unit's log, from the `journalctl` line, holds
`Failed to flush binfmt_misc rules, ignoring: Read-only file system`;
the service list prints. Ubuntu's own setup tests require `running` for a new instance, so `degraded` passes only in
that one case. Any other failed unit stops the run: record `systemctl --failed` and stop for review. `<WSL_USER>` reads
that log without `sudo` because it is in `adm` (the user-data's `groups`, and W6's `useradd --groups`), which systemd's
tmpfiles rules give read access to the system journal. On `degraded`, if the `journalctl` line prints only
`Hint: You are currently not seeing messages from other users and the system.` or `-- No entries --`, the user cannot
read the journal: repeat that line once with `sudo`, record both outputs and judge the second.
`getty@tty1.service` must not appear in `systemctl --failed` here.

```sh
sudo journalctl -b 0 -t systemd-binfmt --no-pager -n 4
```

The log line is selected by identifier (`-t systemd-binfmt`), not by unit: on the updated host
`journalctl -u systemd-binfmt.service` returned only systemd's four lines about the unit, because the unit's own
early-boot message is not attributed to it, while the identifier query returned the message.

The exception has a reason. On the adopted release WSL mounts `/proc/sys/fs/binfmt_misc/status` read-only, so that one
distribution cannot flush the VM-wide registrations ([PR #40621](https://github.com/microsoft/WSL/pull/40621)), and
`systemd-binfmt.service` fails at every boot with that message and exit 1. Upstream calls the error benign
([issue #41226](https://github.com/microsoft/WSL/issues/41226), a contributor's answer of 2026-08-04: "The systemd error
is benign and won't affect registration of user defined binfmt settings.").

### F2. Linger

```sh
sudo loginctl enable-linger "$(id -un)"
loginctl show-user "$(id -un)" --property=Linger --value
```

Proof: `yes`. With linger, logind starts the user manager at boot and keeps it after logout, which the repository's
`systemd --user` services and runners expect. Linger does not keep the distribution itself running: WSL stops a
distribution `instanceIdleTimeout` after its last Windows-side client exits (W1 reads the key; a negative value never
stops it, WSL 2.7.13 `LxssUserSession.cpp:2658-2676`), and issue reports say linger alone does not prevent that
(microsoft/WSL#13416 and #9968).

Then observe it. First close every client of `<Name>`: its terminals, editors, Explorer windows on
`\\wsl.localhost\<Name>` and `wsl.exe -d <Name>` processes (a `bash -s` run of F1 and F2 ends with its script). Then,
from the workstation's session, list the running distributions every 10 seconds for two minutes:

```powershell
$env:WSL_UTF8 = '1'
foreach ($Poll in 1..12) { Start-Sleep -Seconds 10; [DateTime]::UtcNow.ToString('HH:mm:ss'); wsl.exe --list --running --quiet }
```

Proof: twelve UTC times, each followed by the running distributions. Record in `idle_observation` whether `<Name>` is in
every list, or the time of the first list without it, beside W1's two keys. With `instanceIdleTimeout=-1` it should stay
listed; with the default it should leave after about 15 seconds. Whether `wsl.exe --list --running` itself counts as a
client is not verified. F3 starts `<Name>` again if it stopped.

### F3. User bus

```sh
stat -c '%U %F' "/run/user/$(id -u)" "/run/user/$(id -u)/bus"
systemctl --user is-system-running --wait
```

Proof: `<WSL_USER> directory`, then `<WSL_USER> socket` (a symbolic link fails), then `running`. This is the native
`systemd --user` bus that the guarded runners require ([`adoption/tools/README.md`](../tools/README.md) and
[`adoption/lifecycle.md`](../lifecycle.md)).

Right after the bus proof, check that Docker Engine / Moby starts a rootless container as `<WSL_USER>`, without sudo.
This check is owed on the first run after the WSL update: [microsoft/WSL#41492](https://github.com/microsoft/WSL/issues/41492)
reports that rootless Docker and Podman cannot start a container after the cgroup hierarchy moved, and remains open.
No new distribution has been observed on 3.0.1. Use Docker's
[supported rootless setup](https://docs.docker.com/engine/security/rootless/) and its `rootless` context.
If the engine is not installed yet, record `owed`, complete F4 and F5 and that setup, then return here before F9 or
accepting R1. An owed check is not a pass.

```sh
docker --context rootless info --format '{{json .SecurityOptions}}'
docker --context rootless run --rm hello-world
```

Proof: the first command exits 0 and includes `name=rootless` before the run command is attempted; the second exits
0 and prints `Hello from Docker!`. Record both outputs. A missing rootless mode, a failed container start or a
cgroup error stops the run; retain the failure with issue 41492 and do not accept the engine from its version alone.

### F4. Packages

Changed after `v2026.09.26.2`: `adoption/bootstrap-linux.sh` installs `ca-certificates curl git tar gzip xz-utils jq` and
then requires `curl git tar sha256sum realpath flock jq mktemp`; this step installs that list now, plus `libatomic1` and
`uidmap`. `uidmap` provides `newuidmap` and `newgidmap`, which rootless Docker needs for the Harbor harness. `libatomic1`
matches the workstation profile; the Node 24.21.0 binary that `pins-linux-x86_64.json` pins lists no `libatomic.so.1`
(checked 2026-10-01).

```sh
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl git tar gzip xz-utils jq libatomic1 uidmap
dpkg-query -W -f='${Package} ${Version}\n' jq libatomic1 uidmap
```

Proof: both apt commands exit 0, and `dpkg-query` prints a version for each of the three packages. The historical
24.04.5 image lacked them; do not assume the selected 26.04.1 image has the same package gaps.

### F5. Subordinate ids

Rootless Docker needs at least 65,536 subordinate uids and gids for the user. The image ships empty `/etc/subuid` and
`/etc/subgid` with `SUB_UID_COUNT 65536` in `/etc/login.defs`, so `useradd` should have allocated a range; check, and add
one only when the first `grep` prints nothing.

```sh
grep "^$(id -un):" /etc/subuid /etc/subgid
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$(id -un)"
grep "^$(id -un):" /etc/subuid /etc/subgid
```

Proof: `/etc/subuid:<WSL_USER>:100000:65536` and `/etc/subgid:<WSL_USER>:100000:65536`, or another range of 65,536.
Record whether the range came from `useradd` or from `usermod`.

65,536 stays the stage-1 value. Docker's
[rootless troubleshooting page](https://docs.docker.com/engine/security/rootless/troubleshoot/) (read 2026-10-01) says
of `docker: failed to register layer: Error processing tar file(exit status 1): lchown <FILE>: invalid argument`: "This
error occurs when the number of available entries in `/etc/subuid` or `/etc/subgid` is not sufficient. The number of
entries required vary across images. However, 65,536 entries are sufficient for most images." A wider range is
therefore an image-set need. The unit that pulls the images (the evaluation harness unit) adds it only when that error
appears, and records the image and the error. The workstation's wider range is a host observation for one benchmark
image set, not a requirement of this page.

### F6. Login shell hand-off

A Windows Terminal profile starts its client through a Bash login shell, which reads only the first of
`~/.bash_profile`, `~/.bash_login` and `~/.profile`. Claude Code with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` can leave an
empty `~/.bash_profile` that hides `~/.profile`
([Windows Terminal profiles and the login shell](linux-wsl2.md#windows-terminal-profiles-and-the-login-shell)). The image's
`/etc/skel` has no `.bash_profile`, so this writes the hand-off line before anything else can create one.

```sh
test -e ~/.bash_profile || printf '%s\n' 'if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi' > ~/.bash_profile
cat ~/.bash_profile
```

Proof: `cat` prints exactly the hand-off line. Anything else means a file existed: read it before going on.

### F7. Clone origin/main

`adoption/bootstrap-linux.sh --configure-full-profile` refuses a checkout whose `HEAD` is not `origin/main`, so this host
starts from a clone of `main`, not from the release checkout described in
[Get the catalog](linux-wsl2.md#get-the-catalog).

```sh
mkdir -p ~/code
git clone https://github.com/seathatflowsinourveins/native-agent-stack.git ~/code/native-agent-stack
git -C ~/code/native-agent-stack rev-parse HEAD
git -C ~/code/native-agent-stack ls-remote origin refs/heads/main
```

Proof: the two commands print the same commit. Record it as the receipt's `catalog_revision`.

### F8. Host value file

Added after `v2026.09.26.2`: `adoption/templates/wsl/host.new-distro.json.template` has the keys of
`adoption/hosts/example.json` with ports outside the workstation's. Exclusion set: `3710`, `3800`, `8231`, `13000`,
`13100`, `14318`, `14333`, `16333`, `18080`, `18231`, `18525`, `18888`, `18889`, `19090`, `19093`, `20128`, `20129`,
`31415`, `49374` and `49474`. These are the example's four ports, the gateway and memory services, the 2026-09-25
relocations and the observability backend's fixed ports. When the observability layer is installed here later, move its
ports with `--port-overrides` ([Listeners and ports](linux-wsl2.md#listeners-and-ports)).

```sh
cd ~/code/native-agent-stack
ss -ltnH '( sport = :24318 or sport = :29374 or sport = :26333 or sport = :28231 )'
python3 -c 'import string, sys; sys.stdout.write(string.Template(open(sys.argv[1], encoding="utf-8").read()).substitute(WSL_USER=sys.argv[2]))' adoption/templates/wsl/host.new-distro.json.template "$(id -un)" > 'adoption/hosts/<host>.json'
python3 -m json.tool 'adoption/hosts/<host>.json'
git check-ignore 'adoption/hosts/<host>.json'
```

Proof: `ss` prints nothing, because no distribution listens on those ports in the shared namespace; `json.tool` prints the
nine keys; `git check-ignore` prints the path, so the host file never enters a commit. If `ss` shows a listener, choose
another free port outside the exclusion set and edit the rendered file.

### F9. Stage 2 (outside this page)

Changed after `v2026.09.26.2`: `adoption/bootstrap-linux.sh` installs the pinned tools for `<id>` (step 2 of
[`adoption/bootstrap.md`](../bootstrap.md)). Native sign-in comes next and is never copied from another machine
(step 3: `codex login`, then `claude`). The second run is the whole-profile configuration; it needs `--profile` (an
empty profile exits 1) and the host file from F8.

```sh
cd ~/code/native-agent-stack
adoption/bootstrap-linux.sh --profile '<id>'
adoption/bootstrap-linux.sh --profile '<id>' --configure-full-profile --host '<host>'
```

Proof: as in [`adoption/bootstrap.md`](../bootstrap.md); stage 2 records its own receipts.

### F10. Windows Terminal profiles and the PATH proof

After stage 2, install the profile example for `<Name>` as step 5 of
[Windows Terminal profiles and the login shell](linux-wsl2.md#windows-terminal-profiles-and-the-login-shell) describes:
`<DISTRO>` is `<Name>`, `<WSL_USER>` the new user and `<PROJECT>` `/home/<WSL_USER>/code/native-agent-stack`. Rename every
profile of the example by replacing its `WSL` prefix with `<Name>`, for example `<Name> - Shell`, `<Name> - Codex` and
`<Name> - Claude` (and the resume profiles when the example carries them), and save the file as
`<Name>.json` in the same Fragments folder. Windows Terminal derives a fragment profile's identity from the folder name
and the profile name, so the workstation's identically named profiles would collide with these. Then prove the profile
launch shape from Windows:

```powershell
wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'type -P claude codex'
wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'for n in claude codex; do p="$(type -P "$n")"; test -f "$p" && test -x "$p" && echo "executable: $p"; done'
```

Proof: the first line prints two absolute paths, and the second prints `executable:` followed by each of them.
`type -P` finds files where `command -v` would also accept a shell function. It can still print a stale hashed or a
non-executable path and exit 0 (step 2 of
[Windows Terminal profiles and the login shell](linux-wsl2.md#windows-terminal-profiles-and-the-login-shell)). The
second line therefore tests each printed path as a regular file (`test -f`) that is executable (`test -x`). A missing
`executable:` line fails the proof.

### F11. jCodeMunch for this clone

Added after `v2026.09.26.2`. Stage 2's Claude profile step copies the SubagentStart carrier blocks of
`adoption/hooks/claude/` (changed after `v2026.09.26.2`) into `~/.claude/hooks/`. Four of the six name jCodeMunch tools
as a retrieval lane: the full block and the researcher block name `route`, `menu` and `order`, and the builder and
reviewer blocks name `route` and `order`. The user-scope MCP template leaves jCodeMunch out on purpose, because it
registers per project
([2026-09-25 addendum](../../docs/decisions/2026-09-23-claude-user-profile.md#addendum-2026-09-25-jcodemunch-registers-per-project-not-at-user-scope)),
and no script runs that registration, so without this step those lanes name a server the clone has not registered.
F9's stage 2 does not install the server either: no adoption profile pins `jcodemunch-mcp`, and only the
`uv tool install` line of [`adoption/bootstrap.md`](../bootstrap.md) step 4a installs it. After F9 alone,
`not installed` is the expected outcome.

Run F11 as `<WSL_USER>` inside `<Name>` in a login shell, such as the `<Name> - Shell` profile: F10's proof found
`claude` from a login shell, and a non-login `bash -s` may not. First test for the binary:

```sh
test -x "${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/jcodemunch-mcp"
```

When it exits 1, record `not installed` and skip the rest of F11. Otherwise register the server from the clone's root
with the command step 4a gives under "jCodeMunch, per project"; a local-scope entry belongs to the project in the
current directory:

```sh
cd ~/code/native-agent-stack
claude mcp add --scope local jcodemunch \
  -e "CODE_INDEX_PATH=$HOME/.code-index" -e JCODEMUNCH_SHARE_SAVINGS=0 \
  -- "${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/jcodemunch-mcp"
claude mcp get jcodemunch
```

Proof:

- `claude mcp add` prints an `Added ...` line. Claude Code's [MCP page](https://code.claude.com/docs/en/mcp) (read
  2026-10-01) says: "`claude mcp add` confirms a successful add by printing an `Added ...` line, which means the
  configuration was written", and "Local scope is the default. A local-scoped server loads only in the project where
  you added it and stays private to you. Claude Code stores it in `~/.claude.json` under that project's path, so the
  same server won't appear in your other projects."
- `claude mcp get jcodemunch` names the local scope and the command, which ends in `/bin/jcodemunch-mcp`, with a status.
  On Claude Code 2.1.282 the addendum saw `Local config (private to you in this project)` and a `Connected` status;
  record what this run prints.
- On a re-run `claude mcp add` fails because the name exists at that scope (the MCP page's example prints
  `MCP server sentry already exists in local config`); `claude mcp get` alone is then the proof.

Record `jcodemunch_registration` in the receipt: `registered` with the scope and command lines of `claude mcp get`,
`not installed`, or `skipped` with the reason, for example when stage 2 has not run. A later baseline capture freezes
whichever state exists, so the receipt states it either way and never hides it. F11 rests on a source read (step 4a's
block, the addendum and the MCP page); no host has run it on a new distribution.

## Stage-1 receipt

Added after `v2026.09.26.2`. Tick [`adoption/templates/wsl/first-boot-checklist.md`](../templates/wsl/first-boot-checklist.md)
as the steps pass. Then fill a copy of
[`adoption/templates/wsl/stage1-receipt.example.json`](../templates/wsl/stage1-receipt.example.json) from the private
transcript and the F outputs:

- **Raw log.** It stays private: the transcript in `Z:\WSL\downloads` and the F outputs. It is never committed.
- **Sanitize.** In everything copied into the receipt, replace the Windows user name with `<win-user>`, the profile path
  with `%USERPROFILE%`, the Linux user name with `<WSL_USER>`, its home with `~`, and the checkout path with
  `<checkout>`. Drop any GUID. A path or name that survives fails `python3 scripts/validate.py`.
- **Content.** The receipt keeps:
  - each W and F command with its exit code and a short output excerpt;
  - the three hashes and the `wsl.exe --version` lines;
  - the default distribution before and after;
  - `creation_path` (`A` or `B`), with the W5 markers when B was taken;
  - on path B, `failed_attempt_export`: the file name, SHA-256 and size of W6's export of the failed attempt;
  - W1's `workstation_baseline`, W5's common-unit process ids and active user manager and its `paired_isolation`, any
    `w5_failure_export` with its `cause`, each removal's interop check and the records of any stop for review,
    F1's outcome (`running`, or `degraded` with its two proving outputs) and F3's rootless-container result or `owed`;
  - the clone's commit, the subordinate-id outcome and F11's `jcodemunch_registration`;
  - the `rehearsal` block of R1, the `pre_checks` of P1 and P2, the `storage_errors` of P3 and W5, W1's `idle_keys`,
    W5's `schema_system`, W7's `ownership_probe` and F2's `idle_observation`.
  - all five workstation values equal to `host.workstation_baseline`; its optional `getty_tty1_result` is present only
    when W1's extra command ran; and `getty_mask` under `first_launch`, with `is_enabled`, `load_state`, `active_state`
    and `n_restarts` from W5's two proof commands.
  - the selected release and actual image size, with the two fixed `supported_images` pins and both `comparison_arms`.
    The checked-in example is a synthetic fixture with unrun comparison arms; fill actual results from the native logs
    and replace the synthetic fixture labels in a contributed receipt only with the operations it actually observed.
- **Contribute.** On a branch of current `main`, copy it to `evidence/receipts/wsl-new-distro-stage1-<host>-<YYYYMMDD>.json`
  and add a `receipts[]` row to `manifests/evidence.json` with the same `id`, `kind`, `component_ids`, `claim` and
  `limitations` and its `path`. Its claim quotes only that run's output. Follow
  [`docs/contributing-evidence.md`](../../docs/contributing-evidence.md) and the
  [hot-file protocol](../../docs/lanes.md#hot-file-protocol).

## Open questions

Kept open in the record, each with the observation that would settle it:

- whether cloud-init provisions an imported distribution (path B records `cloud-init status`);
- what keeps `<Name>` running with no client attached: with `instanceIdleTimeout=-1` the setting does, by WSL's source,
  and issue reports say linger alone does not (F2 records it; whether `wsl.exe --list --running` counts as a client is
  not verified);
- whether a rootless container starts in the new distribution on the updated host (F3; microsoft/WSL#41492 remains
  open); run 2 observed cgroup isolation with both distributions running, and each run must repeat W5's paired record;
  a binfmt loss after unregister has R1's required check and its stop-for-review recovery;
- whether `useradd` allocated the subordinate ids on the selected release (F5 records it);
- whether a terminate clears the 0:0 file owner of microsoft/WSL#40941 (W7 records it);
- whether `hv_storvsc` errors break a first launch on this kernel (microsoft/WSL#41482; P3 records a baseline and
  stops on an error line less than one hour old, and W5 counts again after the first launch);
- completion of the preregistered comparison of Ubuntu 26.04.1 default and 24.04.5 rollback on throwaway names;
  the default's run 2 stopped at W5's paired rule on 3.0.1, and full acceptance with the corrected template is owed.

## Boundaries

A new distribution on the existing WSL kernel and Windows installation is not a new physical machine. Stage 1 proves the
image, the install, the default user and the systemd preconditions only; stage 2, native sign-in, services and
model-mediated behavior each need their own evidence ([`adoption/README.md`](../README.md), "Native verification tiers").
F11's commands and proofs come from a source read, not a run, and a recorded registration does not show that a session
or subagent uses jCodeMunch.
