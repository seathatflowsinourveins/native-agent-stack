# A new distro from the official Ubuntu WSL image (stage 1 and first boot)

Added after `v2026.09.26.2`, with its templates under [`adoption/templates/wsl/`](../templates/wsl/) and the record
[`docs/decisions/2026-10-01-new-wsl-distro-recipe.md`](../../docs/decisions/2026-10-01-new-wsl-distro-recipe.md), which
holds the decisions, their alternatives, the command table and every source. Status: documented, not run. No host has
executed these steps; the first one that does starts with the rehearsal of R1 and records the stage-1 receipt described
at the end.

This page creates a second WSL 2 distribution on the existing Windows host from Canonical's published
`ubuntu-24.04.5-wsl-amd64.wsl`, gives it its default user without a prompt through cloud-init, and proves systemd, linger
and the user bus before stage 2, the repository's bootstrap. The workstation's distribution keeps running, stays the
default and is never shut down.

The page runs twice on a host: first as a rehearsal on a throwaway name, which R1 then removes, and then for the real
`<Name>` ([Rehearsal first](#rehearsal-first)). Each run starts with P1 to P3, `sh` checks in the workstation's
distribution that change nothing on the host; it shares the kernel and already has Ubuntu's keyring and cloud-init.
Stage 1 (W1 to W7) runs on the
Windows host in PowerShell. A session inside the workstation's WSL distribution runs each
PowerShell block as a `.ps1` file with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w step.ps1)"`
([Windows-side commands from WSL](linux-wsl2.md#windows-side-commands-from-wsl)). Open each block's file with
`Start-Transcript -LiteralPath 'Z:\WSL\downloads\<Name>-stage1.log' -Append`, placed in W1 right after its first line
(which creates that folder), and end the file with `Stop-Transcript`. That private transcript is the raw install log the
receipt is cut from. The first boot (F1 to F11) runs inside the new
distribution as `<WSL_USER>`, from an interactive `wsl.exe -d <Name>` or, from a WSL session,
`wsl.exe -d <Name> -- bash -s < steps.sh`. F2's idle observation and F10 run from the Windows side and F11 needs a login
shell instead, as their sections say.

## Names and inputs

| Placeholder | Meaning | Rule |
| --- | --- | --- |
| `<Name>` | the new distribution's name (`--name`) and the user-data file's name | letters, digits, `.`, `_`, `-`; not already registered (W1); a throwaway name for the rehearsal (R1) |
| `<WSL_USER>` | the Linux user cloud-init creates | `^[a-z_][a-z0-9_-]*$`, the rule of the image's `/usr/lib/wsl/wsl-setup` |
| `Z:\WSL\<Name>` | the install location (`--location`); WSL puts `ext4.vhdx` there | must not exist yet (W1) |
| `Z:\WSL\downloads` | the image, its checksum list and the private logs | outside the Windows profile, so its path names no user |
| `<checkout>` | the Windows path of a checkout of `origin/main` holding these templates | from a WSL session: `wslpath -w .` in the checkout |
| `<host>` | the host value file `adoption/hosts/<host>.json` | `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, the bootstrap's `--host` rule |
| `<id>` | the adoption profile stage 2 installs | a `profiles[].id` of `adoption/manifest.json` |

## Host-wide rules

- No `.wslconfig` change, no `wsl --update` and never `wsl --shutdown`, which stops every distribution, the workstation's
  included. The only stop is `wsl --terminate <Name>`, for the new distribution. W1 reads two keys of `.wslconfig` with
  `Select-String`; no command here writes, copies or edits it.
- The default distribution stays the workstation's: nothing here sets a default, W1 records the starred line of
  `wsl.exe --list --verbose` and W4 and W5 prove it unchanged.
- No WSL update is needed to install: `wsl --install --from-file` needs WSL 2.4.4 or later (Microsoft), 2.4.8 (Ubuntu's
  announcement) or 2.4.10 (Ubuntu's install guide), and the host runs 2.7.13. Later releases do change the first launch:
  microsoft/WSL#40941 (after the first-run setup, files created from Windows are owned by 0:0) is fixed by PR #40977,
  which ships first in 2.9.8, a pre-release, and in 3.0.1; tags 2.7.13 and 2.7.14 lack it. On 2.7.13, W7 terminates
  `<Name>` once after the first launch and probes a file's owner before anything else is written from Windows. Updating
  WSL is the keys lane's decision, not this page's.
- `.wslconfig` is global, so the new distribution inherits the workstation's settings, among them
  `networkingMode=mirrored`, `swap` and the two idle keys that W1 reads and F2 observes.
- WSL 2 distributions share one network namespace
  ([Listeners and ports](linux-wsl2.md#listeners-and-ports)): every listener of the new distribution competes with the
  workstation's for the same ports. F8 picks the host file's ports outside the workstation's set.
- The official first launch writes to Windows by design. WSL adds a Start-menu shortcut and a Windows Terminal profile for
  the distribution, and the image's `wsl-setup` copies the Ubuntu Sans Mono font into
  `%LOCALAPPDATA%\Microsoft\Windows\Fonts` and registers it under `HKCU` when that file is missing. The generated
  terminal profile may stay; hide it in Windows Terminal if it duplicates the fragment profile of F10.

## Rehearsal first

### R1. Rehearse on a throwaway name, then remove it

Run the page once on a throwaway distribution before the real one. For that run `<Name>` is a throwaway name that no
other distribution uses, never the real `<Name>` and never the workstation's, and `Z:\WSL\<Name>` is its own new folder.
Run it through F3: P1 to P3, W1 to W7 (W6 only after the W5 marker) and F1 to F3, with the observations no host has
made yet: P3's baseline and W5's second count of storage errors, W5's `cloud-init schema --system` (path A), W7's
file-ownership probe and F2's idle observation. The first real reading of the storage rule thus comes from the throwaway
distribution. Record the rehearsal's name, result, creation path and those observations in the receipt's `rehearsal`
block. Every
host-wide rule holds: the rehearsal names only its own distribution, and R1 terminates and unregisters only that literal
name. A rehearsal that stopped before W4 installed nothing, and R1 has nothing to remove.

After the rehearsal's F3, read the list first and remove the throwaway distribution. When every proof held, no export is
needed:

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --list --quiet
wsl.exe --terminate '<Name>'
wsl.exe --unregister '<Name>'
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
wsl.exe --list --verbose
```

Proof: the first `--list --quiet` names the throwaway distribution; the last `--list --verbose` no longer lists it, and
its starred line is still W1's. A failed rehearsal's export goes into the `rehearsal` block with its SHA-256 and size,
and the real run waits until the failure is understood. The rehearsal's private transcript and its user-data file under
`%USERPROFILE%\.cloud-init` stay; record whether WSL's Start-menu entry and terminal profile for the throwaway name
outlive `--unregister`. Then run the page again from P1 for the real `<Name>`, without R1.

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
SUMS_DIR="$(mktemp -d)"
curl -fsSL -o "$SUMS_DIR/SHA256SUMS" https://releases.ubuntu.com/24.04.5/SHA256SUMS
curl -fsSL -o "$SUMS_DIR/SHA256SUMS.gpg" https://releases.ubuntu.com/24.04.5/SHA256SUMS.gpg
gpgv --homedir "$SUMS_DIR" --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg "$SUMS_DIR/SHA256SUMS.gpg" "$SUMS_DIR/SHA256SUMS"
grep ' \*ubuntu-24\.04\.5-wsl-amd64\.wsl$' "$SUMS_DIR/SHA256SUMS"
```

Proof: both downloads exit 0; `gpgv` exits 0 and prints `using RSA key 843938DF228D22F7B3742BC0D94AA3F0EFE21092` and
`Good signature from "Ubuntu CD Image Automatic Signing Key (2012) <cdimage@ubuntu.com>"`; `grep` prints
`bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e *ubuntu-24.04.5-wsl-amd64.wsl`, the hash W2 pins. A
`BAD signature`, a missing key or any other nonzero exit stops the run with nothing installed.

### P2. The user-data schema

Added after `v2026.09.26.2`: this renders `adoption/templates/wsl/cloud-init.user-data.template` with `<WSL_USER>`
before any boot and validates it with cloud-init's own schema check. The render is F8's `string.Template` program, which
writes the same bytes as W3's literal replace (W3 says why). Run it from the root of the checkout that `<checkout>` names.
The workstation's cloud-init checks against its own version's schema, which `cloud-init --version` records; the image
runs 26.1.

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
and leaves out the driver's registration line, `hv_vmbus: registering driver hv_storvsc`, which every boot logs. A count
over the whole boot cannot tell errors that are happening now from an old burst, so the count is
a baseline, not a verdict: the newest error line's age decides here, and W5 counts again after the first launch.

```sh
sudo journalctl -k -b 0 --no-pager | grep hv_storvsc | grep -vc 'registering driver hv_storvsc'
sudo journalctl -k -b 0 --no-pager -o short-monotonic --no-hostname | grep hv_storvsc | grep -v 'registering driver hv_storvsc' | tail -n 1
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

Proof, recorded in the receipt's `host` block:

- `wsl.exe --version` starts with `WSL version:` and a version of 2.4.10 or later.
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
- `Free` on `Z:` is recorded. The image unpacks to about 1.3 GB before stage 2 adds its tools.

Stop on any other result.

### W2. Download and verify the image

The expected sha256 is published twice, by Canonical next to the image and by Microsoft's WSL distribution catalog.
This block reads the catalog at the commit of 2026-09-14 (#41465), whose `Ubuntu-24.04` entry is this image. It is the
only hash check before W4 installs the file: at WSL 2.7.13, `wsl --install --from-file` checks no hash
(`WslClient.cpp:500-537`). The online `wsl --install Ubuntu-24.04` does compare its download with the catalog entry's
`Sha256` (`WslInstall.cpp:36-50`, `:315`), but it reads the catalog from WSL's `master` branch at install time; this
page installs a pinned file whose hash the operator sees, and P1 has tied that hash to Canonical's signature.

```powershell
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -UseBasicParsing -Uri 'https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl' -OutFile 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl'
Invoke-WebRequest -UseBasicParsing -Uri 'https://releases.ubuntu.com/24.04.5/SHA256SUMS' -OutFile 'Z:\WSL\downloads\SHA256SUMS'
$Expected = 'bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e'
$Published = (Select-String -LiteralPath 'Z:\WSL\downloads\SHA256SUMS' -Pattern ' \*ubuntu-24\.04\.5-wsl-amd64\.wsl$').Line.Split(' ')[0]
$Listed = ((Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/microsoft/WSL/8bc98bc33b246fe66710eec9eaa1b24c323da987/distributions/DistributionInfo.json').Content | ConvertFrom-Json).ModernDistributions.Ubuntu | Where-Object Name -eq 'Ubuntu-24.04'
$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl').Hash.ToLowerInvariant()
"computed $Actual published $Published listed $($Listed.Amd64Url.Sha256) url $($Listed.Amd64Url.Url)"
if ($Actual -ne $Expected -or $Published -ne $Expected -or $Listed.Amd64Url.Sha256 -ne $Expected) { throw 'sha256 mismatch: do not install' }
```

Proof: the printed line shows one hash three times, `bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e`, and
the URL `https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl`; the file is 388,975,696 bytes. A `throw`
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
wsl.exe --install --from-file 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl' --name '<Name>' --location 'Z:\WSL\<Name>' --no-launch
$LASTEXITCODE
wsl.exe --list --verbose
```

Proof: the output is `Installing: Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl`, then
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

- The launch prints `Provisioning the new WSL instance <Name>` and `This might take a while...`, and `$LASTEXITCODE`
  prints `0`. The image's `wsl-setup` prints both lines, not WSL: lines 117-118 at its version 0.5.10~24.04.2, Launchpad
  tag `import/0.5.10_24.04.2`, commit `74bfc89113bc7d46a4d9feb1e69cd6951fbc6908`.
- `id -un` prints `<WSL_USER>` and `id -u` prints `1000`.
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
  `:1286-1293`), but no new instance has run it after the marker yet. Record the output (`schema_system`).
- `/etc/wsl.conf` holds `[boot]`, `systemd=true`, `[user]` and `default=<WSL_USER>`, each once.
- The marker file exists, and `sudo -l` lists `(ALL) NOPASSWD: ALL`.
- The starred line of `--list --verbose` is still W1's (`default_distribution_after`).

On both paths, right after the launch and before W6 or W7, count the storage errors again in the workstation
distribution, where P3 ran:

```sh
sudo journalctl -k -b 0 --no-pager | grep hv_storvsc | grep -vc 'registering driver hv_storvsc'
```

Proof: the count equals P3's baseline; record it as `second_count`. A larger count means storage errors during W4 to
W5. Record both counts and the new lines (P3's second line with `tail -n` set to the difference, without device ids),
treat a failed W5 as exposure to microsoft/WSL#41482 rather than a cloud-init failure, and do not continue to stage 2
(F9) until that is decided: its workaround changes the global WSL configuration and shuts WSL down, both outside this
page.

How to tell that cloud-init did not provision the instance: the launch output contains
`Create a default Unix user account:` and `OOBE command "/usr/lib/wsl/wsl-setup" failed, exiting`, and the exit code is
not 0. WSL keeps the first-run setup pending. Go to W6.

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
wsl.exe --import '<Name>' 'Z:\WSL\<Name>' 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl' --version 2
wsl.exe -d '<Name>' -u root --exec cloud-init status --wait --long
```

An imported distribution starts as root and skips the first-run command. Whether cloud-init provisions it is not
documented. The `cloud-init status` line therefore only records the import's first boot:
- `done` or `error` when cloud-init ran;
- `disabled` with `boot_status_code: disabled-by-generator` when it found no datasource (`cloudinit/cmd/status.py:298-300`).

The next commands skip what already exists. Run them as root inside `<Name>`: in a shell from
`wsl.exe -d <Name> -u root`, or from a WSL session through `wsl.exe -d <Name> -u root -- bash -s < path-b.sh`.

```sh
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

Proof: `visudo` prints `parsed OK`; `<Name>` is absent from `--list --running`; `id -un` prints `<WSL_USER>`. Then repeat
W5's checks from `id -u` on, with three differences:
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
observed anywhere; this probe is the first observation.

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
systemctl --failed --no-legend
systemctl list-unit-files --type=service --no-pager
```

Proof: `running`, no failed unit, and the service list prints. Ubuntu's own setup tests require `running` for a new
instance. On `degraded`, record `systemctl --failed` and stop for review.

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

Proof: both apt commands exit 0, and `dpkg-query` prints a version for each of the three packages, which the image lacks.

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
`<DISTRO>` is `<Name>`, `<WSL_USER>` the new user and `<PROJECT>` `/home/<WSL_USER>/code/native-agent-stack`. Rename the
three profiles, for example to `<Name> - Shell`, `<Name> - Codex` and `<Name> - Claude`, and save the file as
`<Name>.json` in the same Fragments folder. Windows Terminal derives a fragment profile's identity from the folder name
and the profile name, so the workstation's identically named profiles would collide with these. Then prove the profile
launch shape from Windows:

```powershell
wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'type -P claude codex'
wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'for p in $(type -P claude codex); do test -f $p && test -x $p && echo executable: $p; done'
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
  - the clone's commit, the subordinate-id outcome and F11's `jcodemunch_registration`;
  - the `rehearsal` block of R1, the `pre_checks` of P1 and P2, the `storage_errors` of P3 and W5, W1's `idle_keys`,
    W5's `schema_system`, W7's `ownership_probe` and F2's `idle_observation`.
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
- whether binfmt registrations survive `wsl --terminate` (WSL's `protectBinfmt`);
- whether `useradd` allocated the subordinate ids on 24.04.5 (F5 records it);
- whether a terminate clears the 0:0 file owner of microsoft/WSL#40941 (W7 records it);
- whether `hv_storvsc` errors break a first launch on this kernel (microsoft/WSL#41482; P3 records a baseline and
  stops on an error line less than one hour old, and W5 counts again after the first launch);
- the bounded comparison against Ubuntu 26.04.1 LTS, WSL's current default `Ubuntu`.

## Boundaries

A new distribution on the existing WSL kernel and Windows installation is not a new physical machine. Stage 1 proves the
image, the install, the default user and the systemd preconditions only; stage 2, native sign-in, services and
model-mediated behavior each need their own evidence ([`adoption/README.md`](../README.md), "Native verification tiers").
F11's commands and proofs come from a source read, not a run, and a recorded registration does not show that a session
or subagent uses jCodeMunch.
