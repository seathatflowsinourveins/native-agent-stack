# WSL platform clock disposition — 2026-10-06

Status: command-center ruling `task-ns2604-coop-20261006T215329Z`;
NativeStack retirement leaves the WSL platform time agent in place. The
NativeStack2604 steering takeover is **dropped**, with no rollback needed
because no transfer was applied. This correction supports dependable clock
observation for the independently qualified US-equities paper foundation.

## Source and custody

In WSL 3.0.1, mini_init mounts and chroots into the system distro before
starting its time agent. `StartTimeSyncAgent` writes `refclock PHC /dev/ptp0
poll 3 dpoll -2 offset 0`, `makestep 1.0 3` and `rtcsync`, then execs chronyd
without `-x`. This is a VM/platform service, independent of the registered
user distributions. The Windows service attaches the system distro even
when GUI applications are disabled; GUI enablement is a separate condition.
[System-distro call, microsoft/WSL 91f161fa](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3171-L3222),
[PHC configuration/start](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3665-L3713),
[system-distro selection](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/windows/service/exe/WslCoreVm.cpp#L1506-L1530),
[disk attachment](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/windows/service/exe/WslCoreVm.cpp#L1815-L1819),
[separate GUI flag](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/windows/service/exe/WslCoreVm.cpp#L48).

The command center accepted that source plus its read-only custody check:
only the two user distributions were running; NativeStack had no chronyd
process, active chrony/chronyd/timesyncd service or chrony configuration lines.
Those are **owner-reported observations**, summarized in co-op A12, not a
new NativeStack read by this lane. A system-distro PID listing was unavailable
with GUI disabled; the ruling records that limitation rather than claiming it.

This lane's native tracking read at `2026-10-06T22:00:51Z` returned PHC0 on
`::1:323`, stratum 1, leap Normal, update interval 8 s and System time
0.000002303 s slow, exit 0. The separate `::1:3323` read at
`22:00:52Z` returned NTP reference A29FC801, leap Normal, exit 0. These
are endpoint observations. They establish neither a complete automatic-boot
census nor independent UTC accuracy. WSL's PHC follows the Windows host.

The prior attribution of an unowned port 323 to NativeStack was wrong:
process visibility from one distribution omits the WSL system distro.
Keep the historical `e39bb466` commit; the subsequent fix restores the
platform check and records this correction rather than rewriting history.

## Gate 2 disposition and board carrier

| Function | Replacement | Status | Blocks | Evidence and remaining acceptance |
| --- | --- | --- | --- | --- |
| Shared WSL clock discipline | Existing WSL system-distro PHC agent | superseded | none | Pinned platform source, dated CC ruling and native PHC0 tracking. Monitor deployment/automatic boot and host-time acceptance remain separate work. |

NativeStack2604's chronyd remains `-x` on port 3323, observing NTP. Add no
PHC refclock and remove no observer flag. No service, configuration, install,
system-distro or NativeStack command is part of this disposition.
[chronyd 4.8 `-x` semantics](https://chrony-project.org/doc/4.8/chronyd.html).

The [D0 reader](../../scripts/d0_check.py) checks the platform agent on
port 323, `::1` first with the original IPv4 fallback. An NTP observer on
3323 is not required to return PHC0 and cannot replace that check. The
existing clock-offset checker supplies the outside NTP observation. Keep
PHC-relative health, NTP uncertainty, host-vs-UTC observations and persistence
results distinct. D0 stays disabled until the fix lands and the co-op
installs it; its first automatic boot and actual alert delivery remain pending.

The [CLOCK-R2 administrator runbook](../../adoption/templates/windows/clock-root-fix-r2.md)
remains the host-side remedy and comes first: Automatic startup, backoff
Minutes=1/MaxTimes=7, KB 816043 diagnostics and quality-update re-pause, with
each setting read back. Its final A2 acceptance rule is unchanged. This
plan does not turn configuration or fixture checks into a passed boot.

## Alternatives and overturn condition

Retaining the maintained WSL agent is selected: it already provides the
function across user-distribution retirement. Promoting the native observer
to PHC steering was rejected because it would compete with that platform
agent. Treating the implicit kernel large-offset recovery as complete
small-offset discipline was also rejected; it is a separate mechanism.
[Matching kernel handler, 14794180](https://github.com/microsoft/WSL2-Linux-Kernel/blob/14794180686c2fb6307fbe359c359bec765249f3/drivers/hv/hv_util.c#L464-L489).

Reopen the disposition if an updated WSL source/lifecycle removes the system
agent, a native read no longer finds the expected PHC0 endpoint, owner custody
evidence identifies an additional controlling daemon, or boot/offset monitoring
fails. First gather the supported lifecycle and monitoring evidence; do not
start another steerer as an inferred repair. Absolute UTC readiness remains
subject to the separate Windows/independent-observation acceptance plan.
