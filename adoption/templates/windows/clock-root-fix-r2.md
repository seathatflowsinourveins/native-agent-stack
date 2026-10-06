# CLOCK-R2 administrator runbook — 2026-10-06

The command center reviews the exact [script](clock-root-fix-r2.ps1) and its SHA256
before the user applies it. Inactivity must be confirmed by the paper owner:
start no earlier than **8:06 PM EDT October 6 (00:06Z October 7)**, after
`paper-ext-20261006` is inactive. Keep the reviewed console output as the receipt.

Use the exact reviewed copy in an existing local Windows directory. With
RemoteSigned, an unsigned UNC copy can be treated as remote and refused; keep
the current execution policy. In an administrator PowerShell console:

```powershell
Get-FileHash .\clock-root-fix-r2.ps1 -Algorithm SHA256  # match the CC's receipt
.\clock-root-fix-r2.ps1
```

`-WhatIf` provides a read-only preview before the apply window. Its final line is
`CLOCK-R2 PLAN complete`, and its printed registry values are the current values.
Each actual write prints an immediate read-back and stops on mismatch.

| Step | Expected actual read-back |
| --- | --- |
| TriggerInfo record | A new `.reg` file in the existing Documents directory; exported values and SHA256 printed. |
| Startup type | `START_TYPE : 2 AUTO_START`, no `(DELAYED)`; registry `Start=2`, delay absent or `0`. START triggers remain recorded. |
| NtpClient | `ResolvePeerBackoffMinutes=1`, `DWord`. MaxTimes remains `7` (or its documented absent-value default), with no write to it. |
| Debug logging | `FileLogName=<Windows>\Temp\w32time-clock-r2.log`, `String`; `FileLogEntries=0-300`, `String`; `FileLogSize=10000000`, `DWord`. |
| Quality-update pause | `PauseQualityUpdatesStartTime=<Windows-local run date>`, `String`: normally `2026-10-06` at this slot. |
| Pending restart | Both `RebootRequired` and `CBSRebootPending` printed before and after. |

If either reboot flag is true, use **Settings > Windows Update > Schedule the
restart** for the attended acceptance boot, no earlier than **12:45 AM EDT
October 7 (04:45Z)**, after owner safe points and R1 clearance. A registry pause
read-back proves the requested policy value; it does not prove a queued restart
was cancelled. An earlier unplanned restart is non-acceptance and requires a
new plan. The script leaves service execution and the clock alone; the attended
boot activates the diagnostic/backoff settings.

Startup rollback, performed by the user if the command center directs it:

```powershell
sc.exe config w32time start= delayed-auto
sc.exe qc w32time  # read back AUTO_START (DELAYED)
```

This rollback restores only the prior startup setting. It does not import or
delete triggers or change SynchronizeTime. Before the acceptance boot, the
co-op uses the corrected A0–A12 plan and the read-only D0 persistence check;
configuration read-backs alone are not clock acceptance. Final A2: first
Time-Service 35 must be <=75 s after OS StartTime **and** <=network identification
+30 s when that event exists; without it, use <=75 s and record the gap. Missed
relative bounds through +151 s are PARTIAL; >151 s is FAIL. The CC rejected an
absolute-only PASS because it hides a slow DNS/acquisition path.

Sources: [Automatic, 16dafadd, ms.date 2025-02-25](https://github.com/MicrosoftDocs/windowsserverdocs/blob/16dafaddc757fb0b4ad7e5f8da33fbfc888fbcd4/WindowsServerDocs/networking/windows-time-service/configuring-systems-for-high-accuracy.md#L47-L50);
[backoff, ef9afdb7, ms.date 2025-09-18](https://github.com/MicrosoftDocs/windowsserverdocs/blob/ef9afdb74d7e649d54aeaf104efe28dcd857ff2f/WindowsServerDocs/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings.md#L375-L376);
[KB 816043, 3b8ed12f, ms.date 2025-05-08](https://github.com/MicrosoftDocs/SupportArticles-docs/blob/3b8ed12fb8f2d0d4438f0d24ec32a15794867e27/support/windows-server/active-directory/turn-on-debug-logging-in-windows-time-service.md#L24-L49);
[pause policy, 2025-09-30](https://learn.microsoft.com/en-us/windows/deployment/update/waas-configure-wufb#pause-quality-updates);
[sc.exe config, 2023-02-03](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-config);
[reg export, 2023-02-03](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/reg-export);
[restart scheduling, 2025-09-30](https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart);
[PowerShell 5.1 execution policies, 9a8a7830 (2026-08-31)](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/9a8a7830dbbb55ab46555c79e800ca0b0bd0552e/reference/5.1/Microsoft.PowerShell.Core/About/about_Execution_Policies.md).
