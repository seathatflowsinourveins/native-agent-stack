#Requires -Version 5.1
<#
User-run administrator step; CLOCK-R2, 2026-10-06. Review before execution.
Allowed writes: one TriggerInfo export; W32Time start=auto; backoff Minutes=1;
three KB 816043 logging values; the Windows Update quality-pause start date.

S1 Automatic (ms.date 2025-02-25):
https://github.com/MicrosoftDocs/windowsserverdocs/blob/16dafaddc757fb0b4ad7e5f8da33fbfc888fbcd4/WindowsServerDocs/networking/windows-time-service/configuring-systems-for-high-accuracy.md#L47-L50
S2 NtpClient defaults/backoff (ms.date 2025-09-18):
https://github.com/MicrosoftDocs/windowsserverdocs/blob/ef9afdb74d7e649d54aeaf104efe28dcd857ff2f/WindowsServerDocs/networking/windows-time-service/Windows-Time-Service-Tools-and-Settings.md
S3 KB 816043 (ms.date 2025-05-08; adjudication source pin):
https://github.com/MicrosoftDocs/SupportArticles-docs/blob/3b8ed12fb8f2d0d4438f0d24ec32a15794867e27/support/windows-server/active-directory/turn-on-debug-logging-in-windows-time-service.md
S4 Pause quality updates (Microsoft Learn revision 2025-09-30):
https://learn.microsoft.com/en-us/windows/deployment/update/waas-configure-wufb#pause-quality-updates
S5 sc.exe config / reg.exe export (Microsoft commands, revisions 2023-02-03):
https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-config
https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/reg-export
S6 Pending-restart scheduling (Microsoft Learn revision 2025-09-30):
https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart
MaxTimes stays at 7. All triggers stay intact. The next attended boot activates
the logging/backoff settings; this script does not restart or resync anything.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$serviceKey = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time'
$ntpKey = "$serviceKey\TimeProviders\NtpClient"
$configKey = "$serviceKey\Config"
$updateKey = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$triggerNative = 'HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TriggerInfo'
$scExe = Join-Path $env:SystemRoot 'System32\sc.exe'
$regExe = Join-Path $env:SystemRoot 'System32\reg.exe'
$earliestApply = [DateTimeOffset]::Parse('2026-10-07T00:06:00Z')
$earliestBoot = [DateTimeOffset]::Parse('2026-10-07T04:45:00Z')

function Show-RegistryValue {
    param([string]$Path, [string]$Name)
    $key = Get-Item -LiteralPath $Path
    $value = $key.GetValue($Name, $null,
        [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    if ($null -eq $value) {
        Write-Host "READ $Path\$Name=<absent>"
    } else {
        $kind = $key.GetValueKind($Name)
        Write-Host "READ $Path\$Name=$value type=$kind"
    }
    return $value
}

function Set-CheckedRegistryValue {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
    param([string]$Path, [string]$Name, [object]$Value,
          [ValidateSet('DWord', 'String')][string]$Kind)
    if ($PSCmdlet.ShouldProcess("$Path\$Name", "Set $Kind to $Value")) {
        New-ItemProperty -LiteralPath $Path -Name $Name -Value $Value `
            -PropertyType $Kind -Force -Confirm:$false | Out-Null
        $actual = Show-RegistryValue -Path $Path -Name $Name
        $actualKind = (Get-Item -LiteralPath $Path).GetValueKind($Name).ToString()
        if ([string]$actual -cne [string]$Value -or $actualKind -ine $Kind) {
            throw "Read-back mismatch for $Name; stop and review the printed values."
        }
    } else {
        Write-Host "PLAN $Path\$Name -> $Value ($Kind)"
        $null = Show-RegistryValue -Path $Path -Name $Name
    }
}

function Invoke-NativeChecked {
    param([string]$Executable, [string[]]$NativeArguments)
    $output = @(& $Executable @NativeArguments 2>&1)
    $code = $LASTEXITCODE
    foreach ($line in $output) { Write-Host $line }
    if ($code -ne 0) { throw "Native command failed: $Executable, exit=$code" }
    return ($output -join "`n")
}

function Show-RebootState {
    $wu = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
    $cbs = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
    Write-Host "READ RebootRequired=$wu CBSRebootPending=$cbs"
    if ($wu -or $cbs) {
        $local = $earliestBoot.ToLocalTime().ToString('yyyy-MM-dd h:mm tt zzz')
        Write-Host "PENDING RESTART: use Settings > Windows Update > Schedule the restart."
        Write-Host "Choose an attended acceptance boot no earlier than $local (2026-10-07T04:45:00Z), after owner safe-point and R1 clearance."
        Write-Host 'Re-check the time configuration after the update; a pause-date write does not prove a queued restart was cancelled.'
    }
}

try {
    if (-not $WhatIfPreference) {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Open PowerShell as administrator after the command-center review.'
        }
        if ([DateTimeOffset]::UtcNow -lt $earliestApply) {
            throw 'Apply no earlier than 2026-10-07T00:06:00Z, after the paper owner confirms paper-ext-20261006 is inactive.'
        }
    }
    Write-Host 'CLOCK-R2: the paper owner must confirm inactivity before the actual apply.'
    foreach ($path in @($serviceKey, $ntpKey, $configKey, $updateKey)) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Required existing key missing: $path" }
    }
    $maxTimes = Show-RegistryValue -Path $ntpKey -Name 'ResolvePeerBackoffMaxTimes'
    if ($null -eq $maxTimes) {
        Write-Host 'READ effective ResolvePeerBackoffMaxTimes=7 (documented default; registry value absent).'
    } elseif ([int]$maxTimes -ne 7) {
        throw 'MaxTimes differs from 7; this script has no authority to change it.'
    }
    Show-RebootState

    # S5: export for the record before changing the start type. No trigger edit.
    $documents = [Environment]::GetFolderPath('MyDocuments')
    if (-not (Test-Path -LiteralPath $documents -PathType Container)) {
        throw 'The existing Documents directory is required for the TriggerInfo export.'
    }
    $stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $export = Join-Path $documents "w32time-TriggerInfo-$stamp.reg"
    if (Test-Path -LiteralPath $export) { throw "Export already exists: $export" }
    if ($PSCmdlet.ShouldProcess($export, 'Export W32Time TriggerInfo for the record')) {
        $null = Invoke-NativeChecked -Executable $regExe -NativeArguments @('export', $triggerNative, $export)
        $record = Get-Content -LiteralPath $export
        if (-not ($record -match '\[HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\W32Time\\TriggerInfo')) {
            throw 'TriggerInfo export did not read back with the expected registry header.'
        }
        foreach ($line in $record) { Write-Host "EXPORT READ $line" }
        Write-Host "READ TriggerInfoExport=$export sha256=$((Get-FileHash -LiteralPath $export -Algorithm SHA256).Hash)"
    }

    # S1/S5: startup type only. Rollback is sc.exe config w32time start= delayed-auto.
    if ($PSCmdlet.ShouldProcess('W32Time startup type', 'sc.exe config w32time start= auto')) {
        $null = Invoke-NativeChecked -Executable $scExe -NativeArguments @('config', 'w32time', 'start=', 'auto')
        $qc = Invoke-NativeChecked -Executable $scExe -NativeArguments @('qc', 'w32time')
        $start = Show-RegistryValue -Path $serviceKey -Name 'Start'
        $delay = Show-RegistryValue -Path $serviceKey -Name 'DelayedAutoStart'
        if ([int]$start -ne 2 -or ($null -ne $delay -and [int]$delay -ne 0) -or $qc -match '\(DELAYED\)') {
            throw 'Automatic read-back failed; stop and review before any further writes.'
        }
    }
    $null = Invoke-NativeChecked -Executable $scExe -NativeArguments @('qtriggerinfo', 'w32time')

    # S2: only Minutes. The conflicting MaxTimes=0 proposal is not used.
    Set-CheckedRegistryValue -Path $ntpKey -Name 'ResolvePeerBackoffMinutes' -Value 1 -Kind DWord

    # S3: KB 816043's three values; activation is the attended boot, not a restart here.
    Set-CheckedRegistryValue -Path $configKey -Name 'FileLogName' `
        -Value (Join-Path $env:SystemRoot 'Temp\w32time-clock-r2.log') -Kind String
    Set-CheckedRegistryValue -Path $configKey -Name 'FileLogEntries' -Value '0-300' -Kind String
    Set-CheckedRegistryValue -Path $configKey -Name 'FileLogSize' -Value 10000000 -Kind DWord

    # S4: the Windows-local run date. At 00:06Z on 10-07 it is 2026-10-06 in EDT.
    $runDate = (Get-Date).ToString('yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
    Set-CheckedRegistryValue -Path $updateKey -Name 'PauseQualityUpdatesStartTime' -Value $runDate -Kind String
    Show-RebootState
    if ($WhatIfPreference) {
        Write-Host 'CLOCK-R2 PLAN complete. Values above are existing values; no write was performed.'
    } else {
        Write-Host 'CLOCK-R2 configuration read-backs complete. Acceptance requires the attended boot and the corrected A0-A12 plan.'
    }
} catch {
    Write-Error -Message "CLOCK-R2 stopped: $($_.Exception.Message)" -ErrorAction Continue
    exit 1
}
