# A new distro from the official Ubuntu WSL image (stage 1 and first boot)

Added after `v2026.09.26.2`, with its templates under [`adoption/templates/wsl/`](../templates/wsl/) and the record
[`docs/decisions/2026-10-01-new-wsl-distro-recipe.md`](../../docs/decisions/2026-10-01-new-wsl-distro-recipe.md), which
holds the decisions, their alternatives, the command table and every source. Status: documented, not run. No host has
executed these steps; the first one that does records the stage-1 receipt described at the end.

This page creates a second WSL 2 distribution on the existing Windows host from Canonical's published
`ubuntu-24.04.5-wsl-amd64.wsl`, gives it its default user without a prompt through cloud-init, and proves systemd, linger
and the user bus before stage 2, the repository's bootstrap. The workstation's distribution keeps running, stays the
default and is never shut down.

Stage 1 (W1 to W6) runs on the Windows host in PowerShell. A session inside the workstation's WSL distribution runs each
PowerShell block as a `.ps1` file with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w step.ps1)"`
([Windows-side commands from WSL](linux-wsl2.md#windows-side-commands-from-wsl)). Open each block's file with
`Start-Transcript -LiteralPath 'Z:\WSL\downloads\<Name>-stage1.log' -Append`, placed in W1 right after its first line
(which creates that folder), and end the file with `Stop-Transcript`. That private transcript is the raw install log the
receipt is cut from. The first boot (F1 to F11) runs inside the new
distribution as `<WSL_USER>`, from an interactive `wsl.exe -d <Name>` or, from a WSL session,
`wsl.exe -d <Name> -- bash -s < steps.sh`. F11 needs a login shell instead, as its section says.

## Names and inputs

| Placeholder | Meaning | Rule |
| --- | --- | --- |
| `<Name>` | the new distribution's name (`--name`) and the user-data file's name | letters, digits, `.`, `_`, `-`; not already registered (W1) |
| `<WSL_USER>` | the Linux user cloud-init creates | `^[a-z_][a-z0-9_-]*$`, the rule of the image's `/usr/lib/wsl/wsl-setup` |
| `Z:\WSL\<Name>` | the install location (`--location`); WSL puts `ext4.vhdx` there | must not exist yet (W1) |
| `Z:\WSL\downloads` | the image, its checksum list and the private logs | outside the Windows profile, so its path names no user |
| `<checkout>` | the Windows path of a checkout of `origin/main` holding these templates | from a WSL session: `wslpath -w .` in the checkout |
| `<host>` | the host value file `adoption/hosts/<host>.json` | `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, the bootstrap's `--host` rule |
| `<id>` | the adoption profile stage 2 installs | a `profiles[].id` of `adoption/manifest.json` |

## Host-wide rules

- No `.wslconfig` change, no `wsl --update` and never `wsl --shutdown`, which stops every distribution, the workstation's
  included. The only stop is `wsl --terminate <Name>`, for the new distribution.
- The default distribution stays the workstation's: nothing here sets a default, W1 records the starred line of
  `wsl.exe --list --verbose` and W4 and W5 prove it unchanged.
- No WSL update is needed: `wsl --install --from-file` needs WSL 2.4.4 or later (Microsoft), 2.4.8 (Ubuntu's announcement)
  or 2.4.10 (Ubuntu's install guide), and the host runs 2.7.13. WSL 2.7.14 and 3.0.1 change nothing about install, import
  or first launch; updating WSL is the keys lane's decision.
- `.wslconfig` is global, so the new distribution inherits the workstation's settings, among them
  `networkingMode=mirrored` and the idle timeout.
- WSL 2 distributions share one network namespace
  ([Listeners and ports](linux-wsl2.md#listeners-and-ports)): every listener of the new distribution competes with the
  workstation's for the same ports. F8 picks the host file's ports outside the workstation's set.
- The official first launch writes to Windows by design. WSL adds a Start-menu shortcut and a Windows Terminal profile for
  the distribution, and the image's `wsl-setup` copies the Ubuntu Sans Mono font into
  `%LOCALAPPDATA%\Microsoft\Windows\Fonts` and registers it under `HKCU` when that file is missing. The generated
  terminal profile may stay; hide it in Windows Terminal if it duplicates the fragment profile of F10.

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
Get-PSDrive -Name Z | Select-Object -Property Name, Used, Free
```

Proof, recorded in the receipt's `host` block:

- `wsl.exe --version` starts with `WSL version:` and a version of 2.4.10 or later.
- The starred line of `--list --verbose` names the workstation's distribution (`default_distribution_before`).
- `<Name>` is not a line of `--list --quiet`, and the first `Test-Path` prints `False`. WSL refuses a name or an install
  folder another registration already uses and creates the folder itself.
- The second `Test-Path` prints `False`. A Landscape file at that path replaces the local user-data: cloud-init 26.1 loads
  it first and then never reads the file of W3 (`cloudinit/sources/DataSourceWSL.py:241-270` and `:465-476`).
- The third `Test-Path` prints `False`, and the `Select-String` line then prints nothing. When `agent.yaml` exists (Ubuntu
  Pro for WSL writes it), that line lists its top-level keys: record them, and stop if `users:` or `write_files:` is among
  them. cloud-init 26.1 merges `agent.yaml` over the user-data one top-level key at a time, and an agent key replaces the
  user-data key entirely (`DataSourceWSL.py:317-336`, called at `:490`). Either key would replace the user or the
  `[user] default` of W3.
- `Free` on `Z:` is recorded. The image unpacks to about 1.3 GB before stage 2 adds its tools.

Stop on any other result.

### W2. Download and verify the image

The expected sha256 is published twice, by Canonical next to the image and by Microsoft's WSL distribution catalog.
This block reads the catalog at the commit of 2026-09-14 (#41465), whose `Ubuntu-24.04` entry is this image.

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
`%USERPROFILE%\.cloud-init\<InstanceName>.user-data` before any less specific file.

```powershell
New-Item -ItemType Directory -Force -Path (Join-Path $env:USERPROFILE '.cloud-init')
$Text = [System.IO.File]::ReadAllText('<checkout>\adoption\templates\wsl\cloud-init.user-data.template').Replace('${WSL_USER}', '<WSL_USER>')
[System.IO.File]::WriteAllText((Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data'), $Text)
Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -TotalCount 1
Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -Pattern '^- name: ', '^    default='
Select-String -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\<Name>.user-data') -SimpleMatch -Pattern '${'
```

Proof: the first line is `#cloud-config`; the two matches end in `<WSL_USER>`; the last command prints nothing. The file
holds no secret: the user's password stays locked and sudo needs none.

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
wsl.exe -d '<Name>' -u root --exec cat /etc/wsl.conf
wsl.exe -d '<Name>' -u root --exec ls -l /etc/cloud/cloud-init.disabled
wsl.exe -d '<Name>' -u root --exec sudo -l -U '<WSL_USER>'
wsl.exe --list --verbose
```

Proof (path A, cloud-init provisioned the instance):

- The launch prints `Provisioning the new WSL instance <Name>` and `This might take a while...`, and `$LASTEXITCODE`
  prints `0`.
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
- `/etc/wsl.conf` holds `[boot]`, `systemd=true`, `[user]` and `default=<WSL_USER>`, each once.
- The marker file exists, and `sudo -l` lists `(ALL) NOPASSWD: ALL`.
- The starred line of `--list --verbose` is still W1's (`default_distribution_after`).

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
W5's checks from `id -u` on, with two differences:
- `cloud-init status --long` reports `boot_status_code: disabled-by-marker-file` because the root block wrote the marker.
- `result.json` and `status.json` exist only if cloud-init ran on the import (open question 1). Record their contents, or
  their absence, instead of treating absence as a failure.

Record `path B` in the receipt.

## First boot inside the new distribution

Run F1 to F8 as `<WSL_USER>` in `<Name>`.

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
`systemd --user` services and runners expect. Whether a lingering user manager keeps an idle distribution from WSL's idle
timeout is an open question; record what the first days show.

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
  - the clone's commit, the subordinate-id outcome and F11's `jcodemunch_registration`.
- **Contribute.** On a branch of current `main`, copy it to `evidence/receipts/wsl-new-distro-stage1-<host>-<YYYYMMDD>.json`
  and add a `receipts[]` row to `manifests/evidence.json` with the same `id`, `kind`, `component_ids`, `claim` and
  `limitations` and its `path`. Its claim quotes only that run's output. Follow
  [`docs/contributing-evidence.md`](../../docs/contributing-evidence.md) and the
  [hot-file protocol](../../docs/lanes.md#hot-file-protocol).

## Open questions

Kept open in the record, each with the observation that would settle it:

- whether cloud-init provisions an imported distribution (path B records `cloud-init status`);
- whether a lingering user manager keeps the distribution from WSL's idle shutdown;
- whether binfmt registrations survive `wsl --terminate` (WSL's `protectBinfmt`);
- whether `useradd` allocated the subordinate ids on 24.04.5 (F5 records it);
- the bounded comparison against Ubuntu 26.04.1 LTS, WSL's current default `Ubuntu`.

## Boundaries

A new distribution on the existing WSL kernel and Windows installation is not a new physical machine. Stage 1 proves the
image, the install, the default user and the systemd preconditions only; stage 2, native sign-in, services and
model-mediated behavior each need their own evidence ([`adoption/README.md`](../README.md), "Native verification tiers").
F11's commands and proofs come from a source read, not a run, and a recorded registration does not show that a session
or subagent uses jCodeMunch.
