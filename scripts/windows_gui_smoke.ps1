param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [Parameter(Mandatory=$true)][string]$DataDir
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Drawing, System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class TaxWindow {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint dx,uint dy,uint data,UIntPtr extra);
}
'@
New-Item -ItemType Directory -Force -Path $OutputDir,$DataDir | Out-Null
$checks = [System.Collections.Generic.List[string]]::new()
$receipt = @{ platform='windows'; native_gui_tested=$false; all_passed=$false; checks=@(); synthetic_only=$true }
$process = $null
$root = $null

function Get-Named([string]$name, [bool]$visible=$true) {
    $condition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty,$name)
    $found = $script:root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
    foreach ($item in $found) {
        if (!$visible -or (!$item.Current.IsOffscreen -and !$item.Current.BoundingRectangle.IsEmpty)) { return $item }
    }
    return $null
}
function Wait-Named([string]$name,[int]$seconds=90,[bool]$visible=$true) {
    $until = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $until) {
        $item = Get-Named $name $visible
        if ($null -ne $item) { return $item }
        if ($script:process.HasExited) { throw 'The actual native app closed unexpectedly.' }
        Start-Sleep -Milliseconds 250
    }
    throw "The native window did not expose the expected control: $name"
}
function Wait-Edit([string]$name,[int]$seconds=30) {
    $condition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)
    $until=(Get-Date).AddSeconds($seconds)
    while((Get-Date) -lt $until) {
        $items=$script:root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
        foreach($item in $items) { if($item.Current.Name -eq $name) { return $item } }
        Start-Sleep -Milliseconds 250
    }
    throw "Native WebView did not expose the labelled editable field: $name"
}
function Click-Observed($item) {
    $pattern = $null
    if ($item.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)) {
        ([System.Windows.Automation.InvokePattern]$pattern).Invoke(); return
    }
    $rect = $item.Current.BoundingRectangle
    if ($rect.IsEmpty -or $item.Current.IsOffscreen) { throw 'The UI control has no visible click target.' }
    [TaxWindow]::SetCursorPos([int]($rect.Left+$rect.Width/2),[int]($rect.Top+$rect.Height/2)) | Out-Null
    [TaxWindow]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
    [TaxWindow]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
}
function Save-Screenshot([string]$name) {
    $rect = $script:root.Current.BoundingRectangle
    if ($rect.Width -lt 1000 -or $rect.Height -lt 600) { throw 'Actual native window is too small for this desktop check.' }
    $bitmap = [System.Drawing.Bitmap]::new([int]$rect.Width,[int]$rect.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen([int]$rect.Left,[int]$rect.Top,0,0,$bitmap.Size)
        $colors = [System.Collections.Generic.HashSet[int]]::new()
        for($x=0;$x -lt $bitmap.Width;$x+=20) { for($y=0;$y -lt $bitmap.Height;$y+=20) { $colors.Add($bitmap.GetPixel($x,$y).ToArgb()) | Out-Null } }
        $bitmap.Save((Join-Path $OutputDir $name),[System.Drawing.Imaging.ImageFormat]::Png)
        if($colors.Count -lt 20) { throw 'The actual native screenshot is blank or insufficiently rendered.' }
    } finally { $graphics.Dispose(); $bitmap.Dispose() }
}
function Launch-App {
    $script:process = Start-Process -FilePath $Executable -ArgumentList ('--data-dir "'+$DataDir+'"') -PassThru
    $until = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $until) {
        $script:process.Refresh()
        if($script:process.HasExited) { throw 'Native GUI executable exited during startup.' }
        if($script:process.MainWindowHandle -ne [IntPtr]::Zero) { break }
        Start-Sleep -Milliseconds 250
    }
    if($script:process.MainWindowHandle -eq [IntPtr]::Zero) { throw 'No real native window was created.' }
    [TaxWindow]::ShowWindow($script:process.MainWindowHandle,9) | Out-Null
    [TaxWindow]::SetForegroundWindow($script:process.MainWindowHandle) | Out-Null
    $script:root = [System.Windows.Automation.AutomationElement]::FromHandle($script:process.MainWindowHandle)
    Wait-Named "Let's start with you." 90 | Out-Null
}
function Close-App {
    if($script:process -and !$script:process.HasExited) {
        $script:process.CloseMainWindow() | Out-Null
        if(!$script:process.WaitForExit(15000)) { Stop-Process -Id $script:process.Id -Force; throw 'Native window did not close normally.' }
    }
}
try {
    Launch-App
    $checks.Add('Packaged Windows WebView2 native window loaded the real interview.')
    Save-Screenshot 'windows-native-initial.png'
    Click-Observed (Wait-Named 'My returns')
    Click-Observed (Wait-Named 'Synthetic examples')
    Click-Observed (Wait-Named 'Open example')
    Wait-Named '$1,413' 120 | Out-Null
    $checks.Add('Real synthetic W2 example calculated federal refund 1413 USD.')
    Save-Screenshot 'windows-native-calculation-1413.png'
    Click-Observed (Wait-Named 'Save')
    Wait-Named 'Saved on this device' | Out-Null
    Click-Observed (Wait-Named 'Wages & salaries · W-2')
    $field = Wait-Edit 'Box 2 · Federal income tax withheld'
    $scroll=$null
    if($field.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern,[ref]$scroll)) { ([System.Windows.Automation.ScrollItemPattern]$scroll).ScrollIntoView() }
    $field.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    [System.Windows.Forms.SendKeys]::SendWait('7000{TAB}')
    Wait-Named '$1,913' 120 | Out-Null
    Click-Observed (Wait-Named 'Save')
    Wait-Named 'Saved on this device' | Out-Null
    $checks.Add('Actual withholding input changed 6500 to 7000 USD; refund became 1913 USD and was saved.')
    Save-Screenshot 'windows-native-edited-1913.png'
    Close-App; Launch-App
    Click-Observed (Wait-Named 'My returns'); Click-Observed (Wait-Named 'Open')
    Wait-Named '$1,913' 120 | Out-Null
    Save-Screenshot 'windows-native-reopened-1913.png'
    $checks.Add('Normal close/relaunch/reopen preserved the edited return and calculation.')
    $receipt.native_gui_tested=$true; $receipt.all_passed=$true
} catch {
    $receipt.error=$_.Exception.Message
    if($root) { try { Save-Screenshot 'windows-native-failure.png' } catch {} }
    throw
} finally {
    $receipt.checks=@($checks); $receipt.checked_at_utc=(Get-Date).ToUniversalTime().ToString('o')
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $OutputDir 'windows-native-gui-smoke.json')
    if($process -and !$process.HasExited) { $process.CloseMainWindow() | Out-Null; if(!$process.WaitForExit(10000)) { Stop-Process -Id $process.Id -Force } }
}
