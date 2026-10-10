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
| `windows/wslconfig-96GB.fragment.ini` | **Optional reviewed key edit**, never a replacement file: set existing `[wsl2] memory=96GB` in `C:\Users\<PROFILE>\.wslconfig`; preserve encoding, BOM, CRLF and all other bytes | Restore the CC's complete pre-edit byte backup, SHA-256 `2de9d6a9196acc54ddda90590e55228f9aa4dba2afdfd48a308ca47dfcb87a67`. `windows/wslconfig-104GB.inverse.fragment.ini` shows the original key but is not a byte-exact substitute for the backup. |
| Six `user-systemd/<name>.timer.d/90-native-stack-explicit-zone.conf` files | Corresponding new `~/.config/systemd/user/<name>.timer.d/90-native-stack-explicit-zone.conf`; UTC for pages refresh, NY for Git daily/hourly/weekly and backup/prune | Remove only each new drop-in; remove newly created empty directories. Original timer bytes/hashes are retained in the time snapshot. The expired WU watch stays outside the apply set. |

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
All other timer active/enabled states are preserved. Immediately before copying
each timer drop-in, require the live base file's SHA-256 to equal its
`base_unit_sha256` and its sole `OnCalendar=` to equal `original_calendar`.
If either differs, stop that application and regenerate the record and drop-in
from the new base. `git maintenance start` rewrites Git's three timers using a
fresh random minute; repeat this check and regenerate their explicit-zone
drop-ins after each rerun ([Git 2.53.0 source](sources.md#time-and-calendar)). See
[systemd.unit(5) enablement/drop-ins and sysctl.d(5)](sources.md#memory-and-boot).

For the Windows key edit, first require the live file's hash to equal
`2de9d6a9196acc54ddda90590e55228f9aa4dba2afdfd48a308ca47dfcb87a67`
and save a complete byte backup. Preserve its detected encoding, BOM and line
endings; change only the existing `[wsl2]` `memory=104GB` assignment to
`memory=96GB`. Verify the post-edit byte diff consists exactly of that value
change and verify every other active key is unchanged before restarting.
If the hash or unique assignment differs, obtain a new reviewed edit instead
of using this historical precondition. The inverse restores the complete backup.

Future slice policy changes edit the installed `60-native-stack-memory.conf`.
Its filename sorts after the `50-*.conf` files written by
`systemctl set-property`, so the 60- values win when systemd reloads unit
configuration or loads it at boot. A later set-property call on an active unit
changes the live limits immediately; filename order does not prevent that
runtime change. The CC recorded this at 05:10:02Z when an older boot unit
set MemoryHigh=33G, then disabled that unit and reset both memory.high values
at 05:13:04Z ([precedence and immediate application](sources.md#memory-and-boot)).

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

A native boot has **not been run by this lane**. The CC's receipts record the
05:09:55Z boot that loaded these drafts; the oneshot's fresh read-back reports
success and a 05:09:58Z start. The CC retained memory=104GB and skipped the
optional 96GB key edit after the host/guest-capacity trade-off decision.
[The application and corrective-reset receipts](sources.md#cc-application-records)
are attributed to the CC. This does not establish a measured zero-window
guarantee before every external WSL payload can allocate or an independent
two-distro-start persistence run by this lane.

After boot, reload or any later runtime property change, read both the manager
properties and kernel files. Expected slice values are MemoryMax=68719476736,
MemoryHigh=infinity, memory.max=68719476736 and memory.high=max. Expected
non-systemd values are memory.max=42949672960 and memory.high=max.

```sh
systemctl show user-1000.slice -p MemoryMax -p MemoryHigh -p DropInPaths
cat /sys/fs/cgroup/user.slice/user-1000.slice/memory.max
cat /sys/fs/cgroup/user.slice/user-1000.slice/memory.high
cat /sys/fs/cgroup/non-systemd/memory.max
cat /sys/fs/cgroup/non-systemd/memory.high
systemctl show native-stack-non-systemd-memory.service -p Result -p UnitFileState
```

The 06:23:25Z read-only receipt confirms both high values, both maxima,
enabled/successful oneshot and swappiness=10. Remaining CC acceptance checks
include a second distro start, the Windows key, timezone and effective timers.
Clock acceptance has two distinct checks: `chronyc -h ::1 -p 323 tracking`
and `sources` for WSL's VM-init PHC0, then `chronyc -h 127.0.0.1 -p 3323
tracking` and `sources` for the distro's observe-only `-x` network monitor.
VM PHC0 offsets measure agreement with the Hyper-V host clock; the monitor
estimates error relative to network time. Neither a PHC0 label nor a selected
network source proves UTC accuracy or NTS negotiation. No distro refclock
confirmation or chrony edit is proposed. This is a CC application smoke,
not a gate on work. [Pinned daemon and client semantics](sources.md#time-and-calendar).

## Validation and receipts

Run from the repository root:

```sh
python3 adoption/drafts/wsl-memory-persistence-20261010/test_drafts.py
python3 scripts/validate.py
```

The nine small tests parse the slice, service, sysctl and Windows fragments,
check all per-line citations and both memory/time inverse preconditions, and
verify six timer resets against the recorded base expressions and byte hashes.
Mutations coordinate plan/drop-in `:35` against the recorded `:34`, corrupt
the plan hash or corrupt the recorded byte hash; each must be rejected.
Mocked capture tests require both explicit endpoints and retain a failed VM
query alongside a successful monitor query. Tests also exercise the helper
only against a temporary regular file (including missing-path refusal) and
run installed `systemd-analyze verify` on temporary unit fixtures. No test
executes the real ExecStart or a host apply/inverse command.
The follow-up receipt check compares manager and kernel memory limits and
requires a retained IPv4 :323 failure alongside successful IPv6 PHC0 tracking.

[measurements/memory.json](measurements/memory.json) and
[measurements/time.json](measurements/time.json) retain UTC command intervals,
outputs and exit codes. `capture_memory_readonly.py` and
`capture_time_readonly.py` reproduce those read-only captures; the Windows
capture masks the profile before emitting any path. The time capture explicitly
labels both chrony endpoints and does not look for WSL's VM-init PHC refclock
in distro configuration. The memory capture reads
the selected WSL fields rather than hardcoding them.
[measurements/calendar.json](measurements/calendar.json) and
[measurements/calendar-utc.json](measurements/calendar-utc.json) retain native
fold enumerations. [validation.json](validation.json) records local checks.
[The review correction record](review-corrections.md) maps both P2s and all
eight P3 notes to their dispositions; [regression receipts](measurements/regression-checks.json)
retain red/green command outputs and exit codes.
The [effective timer readbacks](measurements/effective-timers.json) record
empty DropInPaths for all seven, six active/enabled timers and the
inactive/disabled WU watch; these are pre-application observations.
[The post-restart endpoint/base receipt](measurements/time-post-restart.json)
separately retains both chrony reads, observed `-x` process flags, unchanged
base hashes, six present drop-ins and an absent WU-watch drop-in. Target
absence in the original receipt is historical; reapplying drafts must respect
the current files. Its later follow-up binds MemoryHigh and both kernel high
read-backs, plus the paired IPv4 failure/IPv6 success, and cites the CC's
native boot/reset records. An independent two-boot or workload acceptance
run by this lane remains unmeasured. No live state is changed by these reads.
The [scoped time audit](local-time-audit.md) lists each classified file:line;
its JSON retains commands and exact origin/main revisions. No host receipt
or platform-status file is changed.

Run suites normally. This proposal adds no RAM-based work gate, test cap,
nice wrapper or new-agent wait; it persists only the CC's requested global
ceilings. Gitleaks is scoped to the PR merge-base range with redaction; it
never scans full history. All upstream sources and selected byte hashes are
in [sources.md](sources.md).
