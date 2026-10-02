# Coordinator's review of the 26.04.1 rehearsal (2026-10-02)

The receipt beside this file is the worker's record and is unchanged. This note adds what the coordinator did and
checked afterwards.

## What the rehearsal showed

Stage 1 works for the 26.04.1 image on this host: signed sums, schema check, install, first launch through cloud-init
(path A) and the file-ownership probe all held. The first boot then stopped at F1: `systemctl is-system-running --wait`
printed `degraded`, and `user@1000.service` had failed with `Failed to spawn executor: Device or resource busy`.

## Cause: distributions share one cgroup tree on WSL 2.7.13

Checked from the workstation's distribution at 2026-10-02T02:40Z, with a third distribution also running:

- `/sys/fs/cgroup/system.slice/cron.service/cgroup.procs` printed `0 <pid> 0`: one local process and two processes
  from other process namespaces, in one cgroup. Same-named system units of every distribution share a cgroup.
- The other running distribution reports its `user@1000.service` as active with
  `ControlGroup=/user.slice/user-1000.slice/user@1000.service`, the workstation's own path.
- The rehearsal's failed unit showed the workstation's accounting (about 1,840 tasks, 16 GiB), as the receipt records.

So a second systemd distribution whose user has the same uid cannot start its user manager while the first one runs,
and a stop or restart of a system unit in one distribution acts on a cgroup that holds another distribution's
processes.

## Upstream state (microsoft/WSL release notes, read 2026-10-02)

- 2.9.8 (pre-release, 2026-08-24): "Protect critical WSL processes under heavy load with cgroup & isolate distro
  cgroups" (pull request 40519).
- 2.9.13 (pre-release, 2026-09-25): "Create new namespaces for distro cgroups" (pull request 41512).
- 3.0.1 (stable, 2026-09-29) is the first stable release after those. The host runs 2.7.13; the 2.7 line (2.7.14,
  2026-09-11) has neither change.
- Issue 41492 (rootless Docker and Podman cannot start a container after the hierarchy moved) is still open, last
  updated 2026-09-28. Whether 2.9.13's namespaces close it on 3.0.1 is not verified here.

## What the coordinator did

- Removed the failed rehearsal by the recipe's failure path at 2026-10-02T02:40:47Z: terminate, export, unregister.
  Export: `StackRehearsal2604-rehearsal.tar`, sha256
  `3dadd24ab1af5e9639d26f5ecd3fff36a9df5e3b1dfa204e5f8a70cbaa42e9ff`, 1,276,456,960 bytes. The default distribution
  is unchanged.
- Did not touch the other distributions.

## Consequences for the recipe

1. The recipe's uid-1000 user cannot have a working user manager beside the workstation on WSL 2.7.x. Either the
   host first moves to a WSL release with isolated distro cgroups, or the new distribution's user gets another uid
   (which removes the user-manager collision only; system units still share cgroups).
2. W5's proof should name the launch warning `wsl: Failed to start the systemd user session`.
3. P3/W5: six new storage-error lines appeared about 15 seconds before cloud-init started, when the new disk was
   attached; the rule "equal to the baseline" does not hold on a host that attaches a disk.
4. The rootless-container check (issue 41492) belongs right after F3 on whichever WSL release the host ends on.

## Runs on WSL 3.0.1 (2026-10-02)

`runs-on-wsl-3.0.1.json` holds the compact, sanitized record of three units on the updated host, each on its own
throwaway name: run 2 (08:32Z to 08:39Z, the recipe before its repair, stopped at W5's paired rule on the shared VM
console), probe E1 (08:42Z, outside the recipe, the template plus the `bootcmd` mask) and run 3 (10:54Z to 11:01Z, the
repaired recipe, P1 to F5 with a rootless container). Each step names its raw output by sha256 and keeps a bounded
excerpt; the raw files stay in the coordinator's private state folder. The record is built by a script that replaces
the user name, the Windows computer name, device ids and profile paths and refuses to write if one survives.

These are rehearsals. They qualify neither image arm of the preregistered comparison; stage 2 with its uv and Node
probes, the 24.04.5 rollback arm and path B are still owed.
