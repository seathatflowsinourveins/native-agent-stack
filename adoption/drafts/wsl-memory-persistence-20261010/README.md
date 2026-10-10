# WSL memory and time persistence drafts — 2026-10-10

These files are **review drafts for the CC**. Nothing has been installed,
enabled, started, stopped, restarted or changed on the host by this lane.
uet#45 remains held at `2001b997b6f6f5529b3a5f44c2cd2f35cf218491`.

This bundle belongs under `adoption/drafts/` because the repository already
keeps uninstalled native host units in
[`memory-maintenance-20261008/`](../memory-maintenance-20261008/README.md).
`adoption/new-wsl/` records client onboarding/configuration; this proposal is a
reviewable host change bundle. The evidence, alternatives and recommendation
are in [the dated decision](../../../docs/decisions/2026-10-10-wsl-memory-time-persistence.md).
No adoption/platform status is advanced.

## Files and exact inverses

[change-plan.json](change-plan.json) is the machine-readable inventory. Every
target is new and was observed absent in [the memory](measurements/memory.json)
or [time](measurements/time.json) snapshots, except the existing masked Windows
file. Recheck these preconditions before applying; if a target has appeared,
preserve it and obtain a new disposition rather than overwrite it.

| Draft | CC destination / action at the planned restart | Exact persistent inverse |
| --- | --- | --- |
| `systemd/user-1000.slice.d/60-native-stack-memory.conf` | New `/etc/systemd/system/user-1000.slice.d/60-native-stack-memory.conf`; `MemoryMax=64G`, `MemoryHigh=infinity` | Remove only this new file; remove the directory only if the CC created it and it is empty. |
| `systemd/native-stack-non-systemd-memory.service` | New `/etc/systemd/system/native-stack-non-systemd-memory.service`; native enablement creates only `/etc/systemd/system/multi-user.target.wants/native-stack-non-systemd-memory.service` | Remove only that new enablement link and service file. Do not stop an unrelated service or remove another link. |
| `sysctl.d/90-native-stack-swappiness.conf` | New `/etc/sysctl.d/90-native-stack-swappiness.conf`; boot applies `vm.swappiness=10` | Remove only this new file. |
| `windows/wslconfig-96GB.fragment.ini` | **Optional reviewed key edit**, never a replacement file: set existing `[wsl2] memory=96GB` in `C:\Users\<PROFILE>\.wslconfig`; preserve every other byte where possible | Restore the CC's complete pre-edit byte backup, SHA-256 `2de9d6a9196acc54ddda90590e55228f9aa4dba2afdfd48a308ca47dfcb87a67`. `windows/wslconfig-104GB.inverse.fragment.ini` shows the original key but is not a byte-exact substitute for the backup. |
| Seven `user-systemd/<name>.timer.d/90-native-stack-explicit-zone.conf` files | Corresponding new `~/.config/systemd/user/<name>.timer.d/90-native-stack-explicit-zone.conf`; UTC for pages refresh and expired WU watch, NY for Git daily/hourly/weekly and backup/prune | Remove only each new drop-in; remove newly created empty directories. Original timer bytes/hashes are retained in the time snapshot. |

The file/link inverse restores the original **persistent** state. The existing
runtime-only settings are untouched by this PR. Removing persistent files does
not itself undo live cgroup or sysctl state; the CC's planned distro/WSL restart
reconstructs that state. Future baseline defaults were not measured and are
not invented as rollback values. The timezone decision keeps
`useWindowsTimezone=true`, America/New_York, chrony, the shell and clock hook;
its guest-setting inverse is therefore a no-op. Each new timer drop-in still
has its own exact removal inverse.

The CC should save original bytes/modes, verify target absence, copy selected
drafts as root/user-owned configuration with mode 0644, and use systemd's
native enablement without `--now` for the new oneshot. Configuration loading,
timer re-evaluation and the WSL restart belong to that reviewed application
turn. Do not enable or reactivate the expired `wu-watch-20261006.timer`.
All other timer active/enabled states are preserved. See
[systemd.unit(5) enablement/drop-ins and sysctl.d(5)](sources.md#memory-and-boot).

## Per-line citations and boot behavior

Each **effective configuration line**, including section headers and empty
reset assignments, has an immediately preceding `# Source:` comment naming a
pinned upstream file:line or a versioned manual entry/section. These comments
are separate lines: systemd's documented comment syntax ignores whole
comment lines; an inline comment can become part of a value
([systemd.syntax(7)](sources.md#memory-and-boot)). Documentation and JSON records
cite claims and operations rather than add invalid comments to JSON.

WSL 3.0.1 creates `non-systemd` before distro init and removes it when the
distro exits. The oneshot therefore reapplies the cap on each **distro boot**,
including a restart that leaves the shared VM alive. `MemoryAccounting=yes`
explicitly activates the memory controller through systemd's ancestry before
ExecStart; kernel controller activation supplies the pre-existing child's
`memory.max`. The command checks writability, writes exactly 42949672960
(40 GiB), reads the result and fails on a mismatch. No wait loop, path watcher,
daemon, process migration or inferred `non-systemd.slice` is introduced.
Sources: [installed-release WSL, systemd and kernel](sources.md#memory-and-boot).

A native boot of these drafts has **not** been run. The service's enablement
does not establish a measured zero-window guarantee before every external
WSL payload can allocate. The CC's restart acceptance checks the loaded
drop-in, oneshot success and cap readback on two distro starts; it also checks
`vm.swappiness`, the Windows memory key, selected PHC0, timezone and effective
timer expressions. This is a future CC application smoke, not a gate on work.

## Validation and receipts

Run from the repository root:

```sh
python3 adoption/drafts/wsl-memory-persistence-20261010/test_drafts.py
python3 scripts/validate.py
```

The six small tests parse the slice, service, sysctl and Windows fragments,
check all per-line citations and inverse preconditions, verify seven timer
resets preserve their original expressions, exercise the helper only against
a temporary regular file (including missing-path refusal), and run the
installed `systemd-analyze verify` on temporary unit fixtures. No test executes
the real ExecStart or a host apply/inverse command.

[measurements/memory.json](measurements/memory.json) and
[measurements/time.json](measurements/time.json) retain UTC command intervals,
outputs and exit codes. `capture_memory_readonly.py` and
`capture_time_readonly.py` reproduce those read-only captures; the Windows
capture masks the profile before emitting any path. The memory capture reads
the selected WSL fields rather than hardcoding them.
[measurements/calendar.json](measurements/calendar.json) and
[measurements/calendar-utc.json](measurements/calendar-utc.json) retain native
fold enumerations. [validation.json](validation.json) records local checks.
The [effective timer readbacks](measurements/effective-timers.json) record
empty DropInPaths for all seven, six active/enabled timers and the
inactive/disabled WU watch; no live state is changed by reading these properties.
The [scoped time audit](local-time-audit.md) lists each classified file:line;
its JSON retains commands and exact origin/main revisions. No host receipt
or platform-status file is changed.

Run suites normally. This proposal adds no RAM-based work gate, test cap,
nice wrapper or new-agent wait; it persists only the CC's requested global
ceilings. Gitleaks is scoped to the PR merge-base range with redaction; it
never scans full history. All upstream sources and selected byte hashes are
in [sources.md](sources.md).
