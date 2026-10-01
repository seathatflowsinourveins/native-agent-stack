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
receipt is cut from. The first boot (F1 to F10) runs inside the new
distribution as `<WSL_USER>`, from an interactive `wsl.exe -d <Name>` or, from a WSL session,
`wsl.exe -d <Name> -- bash -s < steps.sh`.

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
Get-PSDrive -Name Z | Select-Object -Property Name, Used, Free
```

Proof, recorded in the receipt's `host` block:

- `wsl.exe --version` starts with `WSL version:` and a version of 2.4.10 or later.
- The starred line of `--list --verbose` names the workstation's distribution (`default_distribution_before`).
- `<Name>` is not a line of `--list --quiet`, and the first `Test-Path` prints `False`. WSL refuses a name or an install
  folder another registration already uses and creates the folder itself.
- The second `Test-Path` prints `False`. A Landscape file at that path takes precedence, and cloud-init then never reads
  the user-data of W3.
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
wsl.exe -d '<Name>' -u root --exec cat /etc/wsl.conf
wsl.exe -d '<Name>' -u root --exec ls -l /etc/cloud/cloud-init.disabled
wsl.exe -d '<Name>' -u root --exec sudo -l -U '<WSL_USER>'
wsl.exe --list --verbose
```

Proof (path A, cloud-init provisioned the instance):

- The launch prints `Provisioning the new WSL instance <Name>` and `This might take a while...`, and `$LASTEXITCODE`
  prints `0`.
- `id -un` prints `<WSL_USER>` and `id -u` prints `1000`.
- `cloud-init status --long` exits 0 and prints `status: done` and `errors: []`. Exit 2 means recoverable errors: record
  them. Exit 1 means cloud-init crashed: stop.
- `/etc/wsl.conf` holds `[boot]`, `systemd=true`, `[user]` and `default=<WSL_USER>`, each once.
- The marker file exists, and `sudo -l` lists `(ALL) NOPASSWD: ALL`.
- The starred line of `--list --verbose` is still W1's (`default_distribution_after`).

How to tell that cloud-init did not provision the instance: the launch output contains
`Create a default Unix user account:` and `OOBE command "/usr/lib/wsl/wsl-setup" failed, exiting`, and the exit code is
not 0. WSL keeps the first-run setup pending. Go to W6.

### W6. Path B: import and a manual user (only after the W5 marker)

`--unregister` deletes the distribution's disk. Read the list first and run it only on the literal new name, never on the
workstation's.

```powershell
$env:WSL_UTF8 = '1'
wsl.exe --list --quiet
wsl.exe --unregister '<Name>'
wsl.exe --import '<Name>' 'Z:\WSL\<Name>' 'Z:\WSL\downloads\ubuntu-24.04.5-wsl-amd64.wsl' --version 2
wsl.exe -d '<Name>' -u root --exec cloud-init status --wait --long
```

An imported distribution starts as root and skips the first-run command. Whether cloud-init provisions it is not
documented, so the `cloud-init status` result is recorded and the next commands skip what already exists. Run them as
root inside `<Name>`: in a shell from `wsl.exe -d <Name> -u root`, or from a WSL session through
`wsl.exe -d <Name> -u root -- bash -s < path-b.sh`.

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
W5's checks from `id -u` on and record `path B` in the receipt.

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
```

Proof: two absolute paths, each an executable regular file.

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
  - the clone's commit and the subordinate-id outcome.
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
