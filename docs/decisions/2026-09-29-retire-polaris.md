# Decision: retire the Polaris WSL distro on the workstation (2026-09-29)

**Decision practice (2026-09-29):** retire the unused Polaris distribution on the Windows PC hosting
`nativestack-5975wx-20260925`, preserve the still-used workspace and archive NAS work for later resumption.
The [official WSL export/unregister contract](https://learn.microsoft.com/en-us/windows/wsl/basic-commands) defines distribution lifecycle and irreversible unregister semantics.
A Claude Code session in NativeStack carried out the retirement that day, following the procedure of the
[Vela and VelaNext retirement](2026-09-25-retire-vela-velanext.md).

**Scope:** the Windows Subsystem for Linux distros on that PC, plus the Windows-side items that pointed at Polaris:
one scheduled task and three Windows Terminal profiles. The decision covers no other host or repository record.

## Decision

After the unregister on 2026-09-29, NativeStack was the only distro on that PC and the WSL default; its
virtual disk is on the Z: drive.
Later distribution work is recorded in [the new-WSL distro recipe](2026-10-01-new-wsl-distro-recipe.md).

Before the retirement, Polaris ran the services listed below. Each was classified by what still used it.

| Polaris component | Classification | Outcome |
|---|---|---|
| CLIProxyAPI on 127.0.0.1:8317 (`cliproxy.service`) | Superseded. The workstation gateway is OmniRoute ([account-pool decision](2026-09-27-omniroute-account-pool.md), which lists CLIProxyAPI v7.3.19 as a rejected alternative). No NativeStack configuration and no Windows process connected to 8317. | Retired |
| The photo-archive pipeline: its supervisor service and its monitoring, backup and fixity loops | NAS work. The user will pick it up later in NativeStack. At retirement the merge was complete and fixity reported 0 mismatches; the evidence database was older than the last NAS snapshot. | Archived, not migrated |
| `lane-proxy` container (gVisor) and its bridge networks; `lane-egress`, `polaris-gate`, `polaris-drift` and `memguard` units | Plumbing from the pre-convergence agent estate. `polaris-drift` had already been failing (exit 203). | Removed through Polaris's own dockerd, then retired |
| `wslinterop-guard.timer` | Kept the VM-wide WSLInterop entry alive against a peer distro's shutdown. With one distro left, WSL's generated `systemd-binfmt` override (`/run/systemd/generator/systemd-binfmt.service.d/override.conf`: no unregister on stop, re-registration on start) covers NativeStack. `cmd.exe` ran from NativeStack after the terminate and again after the unregister. | Retired |
| A private project workspace and its Windows Terminal profile | Still in use. | Migrated to NativeStack at the same absolute path |
| Windows scheduled task `\<win-host>Backup` | Ran a meridian backup script that no longer existed (last result 127). | Definition exported, task deleted |

## What was kept

The salvage was written to a private archive outside every repository, with a SHA-256 manifest. Every archive file
was verified against that manifest before the distro was unregistered. The archive holds:

- git bundles of every repository with history that exists only locally: the photo-archive pipeline's `local-full-history` branch
  (343 commits not on GitHub), <windows-computer> with its stash, and the `cc-safety-net` fork. It also holds patches of their
  uncommitted work and a bundle of the migrated workspace;
- the home directory as a tar, with its repositories and their `.git` directories. It keeps the data needed to
  resume the photo-archive pipeline: the evidence database, the inventories and reports, and the operations scripts and units;
- the Claude Code memory folders, and the photo-archive pipeline's and the migrated workspace's project history;
- the definitions of the system units, the Docker objects, the scheduled task and the Windows Terminal settings.

Credential stores were not read or copied. Their locations are listed in the private cleanup log, so the user can
revoke the keys and sign-ins that lived there. Caches, virtual environments, tool installs, transcripts of retired
workspaces and scratch trees were dropped as superseded.

## Consequences for repository records

- **Past records stay valid as history.** For example, the
  [terminal-experience decision](2026-09-28-terminal-experience.md) describes the Polaris profiles as they were
  on 2026-09-28.
- **The migrated workspace runs in NativeStack at the same absolute path it had in Polaris.** That path keeps valid the project's own
  vault bind mount and its Claude Code project folder. The mount comes from its `CLAUDE.md`, as the same fstab
  line Polaris used.
- **Shared network state.** Polaris's rootful Docker owned the `DOCKER*` iptables chains in the network namespace
  that every WSL distro on the VM shares. Its networks were removed through its own daemon before the distro
  stopped: the rules naming its bridges went from 11 to 0, and its NAT rules are gone. The empty base chains, the
  FORWARD drop policy and the unused `docker0` bridge stay in the kernel until the next VM restart; nothing refers
  to them. NativeStack's Docker is rootless and adds no rules there.
- **Disk.** Polaris's 706 GB virtual disk on C: was deleted with the distro.
- **This document is the repository evidence for the retirement.** The archive and the cleanup log are private and
  are not evidence of record.
