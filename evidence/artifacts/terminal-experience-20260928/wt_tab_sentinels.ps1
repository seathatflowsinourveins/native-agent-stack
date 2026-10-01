param([string[]]$Sentinels = @())
# Read-only: lists Windows Terminal tab names through UI Automation. Prints counts and a hash prefix only;
# raw names are printed solely for trial sentinels (they carry no session content).
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cls = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, "CASCADIA_HOSTING_WINDOW_CLASS")
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cls)
$names = @()
foreach ($w in $wins) {
    $tabCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)
    $tabs = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $tabCond)
    foreach ($t in $tabs) { $names += $t.Current.Name }
}
$distinct = @($names | Sort-Object -Unique)
$joined = (($names | Sort-Object) -join "`n")
$sha = [System.BitConverter]::ToString((New-Object System.Security.Cryptography.SHA256Managed).ComputeHash([Text.Encoding]::UTF8.GetBytes($joined))).Replace("-", "").ToLower().Substring(0, 16)
"windows=$($wins.Count) tabs=$($names.Count) distinct=$($distinct.Count) sha16=$sha"
foreach ($s in $Sentinels) { "sentinel[$s]=" + ($names -contains $s) }
$names | Where-Object { $_ -match '^(trial-|title-trial-ok)' } | ForEach-Object { "trial-tab: $_" }
