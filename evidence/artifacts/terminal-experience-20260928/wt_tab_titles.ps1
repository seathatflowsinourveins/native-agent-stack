# Read-only: per-tab title state through UI Automation. Prints categories and counts only, never session titles.
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cls = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, "CASCADIA_HOSTING_WINDOW_CLASS")
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cls)
$names = @()
foreach ($w in $wins) {
    $tabCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)
    foreach ($t in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $tabCond)) { $names += $t.Current.Name }
}
$static = @($names | Where-Object { $_ -like 'NativeStack - *' })
$dynamic = @($names | Where-Object { $_ -notlike 'NativeStack - *' })
$dupMax = 0
if ($dynamic.Count -gt 0) { $dupMax = ($dynamic | Group-Object | Measure-Object -Property Count -Maximum).Maximum }
"tabs=$($names.Count) static_profile_title=$($static.Count) dynamic_title=$($dynamic.Count) dynamic_distinct=$(@($dynamic | Sort-Object -Unique).Count) max_duplicates_among_dynamic=$dupMax"
