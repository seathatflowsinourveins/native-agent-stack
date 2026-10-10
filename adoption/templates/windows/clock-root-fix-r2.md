# CLOCK-R2 administrator runbook — 2026-10-06

The command center reviews the exact [script](clock-root-fix-r2.ps1) and its SHA256
before the user applies it. The paper owner confirmed `paper-ext-20261006`
inactive at **5:12 PM EDT October 6 (21:12Z)**. Keep the reviewed console output.
The script changes settings without restarting the service or stepping the clock.

Use the exact reviewed copy in an existing local Windows directory. With
RemoteSigned, an unsigned UNC copy can be treated as remote and refused; keep
the current execution policy. From the owned WSL worktree, set
`CLOCK_WINDOWS_SCRIPT` to the script's WSL path under Windows `USERPROFILE`
(the private handoff supplies the host-specific path), and replace
`<reviewed-head>` with the command center's reviewed commit:

```bash
rtk proxy git show <reviewed-head>:adoption/templates/windows/clock-root-fix-r2.ps1 > "$CLOCK_WINDOWS_SCRIPT"
```

Then in administrator PowerShell, keep the preview made immediately before apply
as the prior-value receipt:

```powershell
Set-Location $env:USERPROFILE
Get-FileHash .\clock-root-fix-r2.ps1 -Algorithm SHA256  # match the CC's receipt
.\clock-root-fix-r2.ps1 -WhatIf 6>&1 | Tee-Object .\clock-r2-before.txt
.\clock-root-fix-r2.ps1
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UpdatePolicy\Settings' -Name PausedQualityStatus,PausedQualityDate
```

Stream `6>&1` captures the script's `Write-Host` prior values in the preview
receipt. `-WhatIf` ends with `CLOCK-R2 PLAN complete`.
Each actual write prints an immediate read-back and stops on mismatch.

| Step | Expected actual read-back |
| --- | --- |
| TriggerInfo record | A new `.reg` file in the existing Documents directory; exported values and SHA256 printed. |
| Startup type | `START_TYPE : 2 AUTO_START`, no `(DELAYED)`; registry `Start=2`, delay absent or `0`. START triggers remain recorded. |
| NtpClient | `ResolvePeerBackoffMinutes=1`, `DWord`. MaxTimes remains `7` (or its documented absent-value default), with no write to it. |
| Debug logging | `FileLogName=<Windows>\Temp\w32time-clock-r2.log`, `String`; `FileLogEntries=0-300`, `String`; `FileLogSize=10000000`, `DWord`. |
| Quality-update pause | `PauseQualityUpdatesStartTime=<Windows-local run date>`, `String`; read `PausedQualityStatus` (`1` paused, `0` unpaused, `2` auto-resumed) and `PausedQualityDate` from UpdatePolicy\Settings. |
| Pending restart | Both `RebootRequired` and `CBSRebootPending` printed before and after. |

If either reboot flag is true, use **Settings > Windows Update > Schedule the
restart** for the attended acceptance boot, no earlier than **12:45 AM EDT
October 7 (04:45Z)**, after owner safe points and R1 clearance. A registry pause
read-back proves the requested policy value; it does not prove a queued restart
was cancelled. An earlier unplanned restart is non-acceptance and requires a
new plan. The script leaves service execution and the clock alone; the attended
boot activates the diagnostic/backoff settings.

Rollback, only on command-center direction: the **5:40:16 PM EDT (21:40:16Z)**
preview recorded the values below. Compare the new pre-apply receipt first;
if it differs, restore its values. Empty logging strings were present, not absent.

```powershell
sc.exe config w32time start= delayed-auto
sc.exe qc w32time  # read back AUTO_START (DELAYED)
reg.exe add HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient /v ResolvePeerBackoffMinutes /t REG_DWORD /d 15 /f
reg.exe query HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient /v ResolvePeerBackoffMinutes
cmd.exe /d /c 'reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config" /v FileLogName /t REG_SZ /d "" /f'
cmd.exe /d /c 'reg.exe add "HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config" /v FileLogEntries /t REG_SZ /d "" /f'
reg.exe add HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config /v FileLogSize /t REG_DWORD /d 0 /f
reg.exe query HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config
reg.exe add HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate /v PauseQualityUpdatesStartTime /t REG_SZ /d 2026-09-01 /f
reg.exe query HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate /v PauseQualityUpdatesStartTime
```

The TriggerInfo export is a retained record; no trigger was changed or needs import.
Triggers and SynchronizeTime are preserved; an old pause date need not keep updates paused.
The co-op uses A0–A12 and D0; configuration read-backs are not clock acceptance.

**Final A2 (CC 7:18 AM EDT, 11:18Z):** PASS requires the first Time-Service 35 <=75 s after
OS StartTime **and** <=network identification+30 s when that event exists.
Without it, use <=75 s and record the missing relative evidence. Evaluate PASS
first; all remaining cases through +151 s are PARTIAL, including a missed
relative bound and slow +75-to-+151-s results. Attribute each using KB 816043's
debug log to 134/47 or acquisition. >151 s is FAIL and overturns the shortened-window
claim. The +35-to-+45-s prediction and +18.6-to-+34.6-s network range across 39
boots require the relative bound: rejected option 2 could hide a 50-s acquisition.

Sources: [Automatic, 16dafadd, ms.date 2025-02-25](https://github.com/MicrosoftDocs/windowsserverdocs/blob/16dafaddc757fb0b4ad7e5f8da33fbfc888fbcd4/WindowsServerDocs/networking/windows-time-service/configuring-systems-for-high-accuracy.md#L54-L56);
[backoff, ef9afdb7, ms.date 2025-09-18](https://github.com/MicrosoftDocs/windowsserverdocs/blob/ef9afdb74d7e649d54aeaf104efe28dcd857ff2f/WindowsServerDocs/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings.md#L375-L376);
[KB 816043, 3b8ed12f, ms.date 2025-05-08](https://github.com/MicrosoftDocs/SupportArticles-docs/blob/3b8ed12fb8f2d0d4438f0d24ec32a15794867e27/support/windows-server/active-directory/turn-on-debug-logging-in-windows-time-service.md#L24-L49);
[pause policy, 2025-09-30](https://learn.microsoft.com/en-us/windows/deployment/update/waas-configure-wufb#pause-quality-updates);
[sc.exe config, 2023-02-03](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-config);
[reg export, 2023-02-03](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/reg-export);
[restart scheduling, 2025-09-30](https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart);
[PowerShell 5.1 execution policies, 9a8a7830 (2026-08-31)](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/9a8a7830dbbb55ab46555c79e800ca0b0bd0552e/reference/5.1/Microsoft.PowerShell.Core/About/about_Execution_Policies.md);
[Write-Host information stream, same pin](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/9a8a7830dbbb55ab46555c79e800ca0b0bd0552e/reference/5.1/Microsoft.PowerShell.Utility/Write-Host.md#L41-L43),
[stream 6 redirection](https://github.com/MicrosoftDocs/PowerShell-Docs/blob/9a8a7830dbbb55ab46555c79e800ca0b0bd0552e/reference/5.1/Microsoft.PowerShell.Core/About/about_Redirection.md#L41-L49).
