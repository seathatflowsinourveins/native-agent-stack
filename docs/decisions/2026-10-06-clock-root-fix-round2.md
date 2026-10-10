# Windows Time startup and persistence, round 2 — 2026-10-06

Status: source-reviewed implementation candidate; host apply and attended-boot
acceptance remain pending. This foundation unit supports clock readiness for
the repository's independently qualified US-equities paper operation. It
changes neither a broker adapter nor a trading gate owned by the custodian.

The command center's 2026-10-06 ruling drops the Linux clock takeover:
[WSL clock disposition](2026-10-06-wsl-clock-disposition.md). PHC0/323 is the
WSL platform agent, surviving NativeStack retirement; native chronyd stays
observe-only on 3323. D0 checks the platform while the outside NTP monitor
and this Windows remedy retain their separate acceptance requirements.

Windows Time's documented high-accuracy startup choice is Automatic. The
read-only reference-host observation at 2026-10-06T11:03:59Z instead returned
numeric Start=2 with delayed startup, RUNNING, two START triggers, no STOP
trigger, SynchronizeTime Ready/enabled and backoff Minutes=15/MaxTimes=7.
The [administrator script and one-page runbook](../../adoption/templates/windows/clock-root-fix-r2.md)
prepare the adjudicated changes: export TriggerInfo for the record, set only
the startup type to Automatic, set Minutes=1 while preserving MaxTimes=7,
configure the three bounded debug-log values and re-pause quality updates with
the Windows-local run date. Every write has an immediate printed read-back.
[Automatic, MicrosoftDocs 16dafadd](https://github.com/MicrosoftDocs/windowsserverdocs/blob/16dafaddc757fb0b4ad7e5f8da33fbfc888fbcd4/WindowsServerDocs/networking/windows-time-service/configuring-systems-for-high-accuracy.md#L54-L56),
[backoff/defaults, ef9afdb7](https://github.com/MicrosoftDocs/windowsserverdocs/blob/ef9afdb74d7e649d54aeaf104efe28dcd857ff2f/WindowsServerDocs/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings.md#L375-L376).

Two broader workflow proposals were rejected by the command-center
adjudication. Deleting all triggers would remove an unidentified start path
without closing an observed STOP-trigger defect. The KB's Manual/stopped
starting state and immediate-stop symptom do not match the observed host.
The vendor Automatic setting is used while preserving its START triggers.
MaxTimes=0 is also omitted: the tools document describes a doubling count,
while the installed administrative-template help describes attempts before
rediscovery. Both agree on Minutes and the default MaxTimes=7; the first-retry
reduction needs only Minutes=1. Its effect on the event-47 path remains to be
measured. [KB 2385818 at 3b8ed12f](https://github.com/MicrosoftDocs/SupportArticles-docs/blob/3b8ed12fb8f2d0d4438f0d24ec32a15794867e27/support/windows-client/active-directory/w32time-not-start-on-workgroup.md).

The supported diagnostic settings are FileLogName, string FileLogEntries
`0-300` and DWORD FileLogSize=10000000. The attended boot, rather than a service
restart in this script, activates them. PauseQualityUpdatesStartTime is a date
string; the vendor policy body and installed WindowsUpdate.admx text field
support that form. A policy-date read-back does not prove an existing pending
restart was cancelled. [KB 816043, ms.date 2025-05-08, 3b8ed12f](https://github.com/MicrosoftDocs/SupportArticles-docs/blob/3b8ed12fb8f2d0d4438f0d24ec32a15794867e27/support/windows-server/active-directory/turn-on-debug-logging-in-windows-time-service.md#L24-L49),
[pause policy, revision 2025-09-30](https://learn.microsoft.com/en-us/windows/deployment/update/waas-configure-wufb#pause-quality-updates).

The [D0 extension](../../scripts/d0_check.py) closes a demonstrated verification
gap in the existing agent-only census (original SHA256
`4b5d02b55f65fa255ad53ae9a38144a70a0cb8f0cce8458573c661165340601b`).
It reads the native SCM, Registry and ScheduledTasks interfaces and fails on
delayed/non-2 startup, non-RUNNING state, STOP/unknown triggers or non-1/7
backoff. START triggers and the task state remain observations. Its
[oneshot](../../adoption/templates/systemd/clock-persistence-check.service)
starts with the distro's user manager and uses the existing paper-alert
failure handler. This supplies configuration persistence evidence, not UTC
accuracy, and does not steer the clock. [Integration and rollback](../../adoption/templates/windows/README.md),
[systemd v259.5 at b3d8fc43](https://github.com/systemd/systemd/tree/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man),
[SERVICE_TRIGGER actions, 2021-04-02](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_trigger).

The remaining exposure is assessed by an attended boot, independent UTC
observations and the trading custodian's point-of-use gate. Changing a startup
setting reduces the configuration delay; it does not guarantee removal of
RTC error, acquisition time, slew, estimator uncertainty or steady-state peer
loss. A start-only gate is also distinct from protection during a session.
The kernel's clock chain does not expose the host's sync state, though a WSL
process can read Windows status through interop. [WSL 3.0.1 agent](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3665-L3713),
[matching kernel handler](https://github.com/microsoft/WSL2-Linux-Kernel/blob/14794180686c2fb6307fbe359c359bec765249f3/drivers/hv/hv_util.c#L464-L489).

The proposed global chrony-wait/user-manager ordering is rejected. The
packaged unit's `Before=time-sync.target`, `Wants=time-sync.target` and
`TimeoutStartSec=180` do not make the target fail closed on a timeout. Ordering
the whole user manager after that target would delay every user unit and
login, including observability. Retargeting its chronyc port to the independent
monitor changes its measurement source but not those ordering and timeout
properties. Keep readiness at the point of use. This is source/installed-unit
review, not a measured timeout experiment.
[systemd ordering and weak dependencies](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.unit.xml),
[chronyc waitsync, chrony 4.8](https://chrony-project.org/doc/4.8/chronyc.html).

Local evidence: 16 focused fixtures pass; the installed Windows PowerShell
5.1 parser accepts the administrator script; the installed systemd verifier
accepts the unit; a native read-only D0 run fails on the two actual pre-fix
values. The synthetic target snapshot is not a post-fix host result. The
unsigned UNC preview was refused before execution; the runbook uses a
reviewed local copy while preserving execution policy.
[PowerShell 5.1 policies, 9a8a7830](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/9a8a7830dbbb55ab46555c79e800ca0b0bd0552e/reference/5.1/Microsoft.PowerShell.Core/About/about_Execution_Policies.md).

Reopen this choice if the accepted boot still has a late startup/first sync,
the first retry retains a 900-second delay despite a ready network, any STOP
trigger or service self-stop appears, persistence reverts after an update, or
independent observations show residual offset beyond the adopted bounds.
Classify offsets from printed numeric fields, rather than treating every
`why=bound` WARN as dispersion-only. Historic peer-loss overlap is insufficient
to claim that a boot-only fix protects a running session. Prefer a future
documented vendor readiness mechanism if it closes that demonstrated gap;
do not add another clock writer, force a step or relax the trading threshold.
