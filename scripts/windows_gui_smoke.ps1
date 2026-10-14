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
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr value);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint dx,uint dy,uint data,UIntPtr extra);
}
'@
# Keep automation and screenshot coordinates in the same physical pixel space.
# This changes only the synthetic test driver, never the user's display scale.
[TaxWindow]::SetProcessDpiAwarenessContext([IntPtr]::new(-4)) | Out-Null
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
        if ($null -ne $item -and $item.Current.IsEnabled) { return $item }
        if($visible) {
            $candidate=Get-Named $name $false
            if($candidate -and ($candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -or $candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit)) {
                try {
                    $scroll=$null
                    if($candidate.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern,[ref]$scroll)) { ([System.Windows.Automation.ScrollItemPattern]$scroll).ScrollIntoView() }
                    elseif($candidate.Current.IsKeyboardFocusable) { $candidate.SetFocus() }
                } catch {}
            }
        }
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
function Scroll-Top {
    $elements=$script:root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    foreach($element in $elements) {
        $pattern=$null
        if($element.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern,[ref]$pattern)) {
            $scroll=[System.Windows.Automation.ScrollPattern]$pattern
            if($scroll.Current.VerticalScrollable) {
                $scroll.SetScrollPercent([System.Windows.Automation.ScrollPattern]::NoScroll,0)
            }
        }
    }
    # Real mouse-wheel fallback if the web provider does not expose ScrollPattern.
    $rect=$script:root.Current.BoundingRectangle
    [TaxWindow]::SetCursorPos([int]($rect.Left+$rect.Width*0.75),[int]($rect.Top+$rect.Height*0.3)) | Out-Null
    for($step=0;$step -lt 40;$step++) { [TaxWindow]::mouse_event(2048,0,0,120,[UIntPtr]::Zero) }
}
function Save-Screenshot([string]$name,[bool]$strict=$true) {
    $rect = $script:root.Current.BoundingRectangle
    if ($rect.IsEmpty -or $rect.Width -lt 100 -or $rect.Height -lt 100) { throw 'Actual native window has no usable screenshot area.' }
    if ($strict -and ($rect.Width -lt 1000 -or $rect.Height -lt 600)) { throw 'Actual native window is too small for this desktop check.' }
    $bitmap = [System.Drawing.Bitmap]::new([int]$rect.Width,[int]$rect.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen([int]$rect.Left,[int]$rect.Top,0,0,$bitmap.Size)
        $colors = [System.Collections.Generic.HashSet[int]]::new()
        for($x=0;$x -lt $bitmap.Width;$x+=20) { for($y=0;$y -lt $bitmap.Height;$y+=20) { $colors.Add($bitmap.GetPixel($x,$y).ToArgb()) | Out-Null } }
        $bitmap.Save((Join-Path $OutputDir $name),[System.Drawing.Imaging.ImageFormat]::Png)
        if($strict -and $colors.Count -lt 20) { throw 'The actual native screenshot is blank or insufficiently rendered.' }
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
    # The hosted Windows desktop can be smaller than the default 1360x900
    # app. Maximize the actual window so the captured interview is not clipped.
    [TaxWindow]::ShowWindow($script:process.MainWindowHandle,3) | Out-Null
    [TaxWindow]::SetForegroundWindow($script:process.MainWindowHandle) | Out-Null
    $script:root = [System.Windows.Automation.AutomationElement]::FromHandle($script:process.MainWindowHandle)
    # A stable origin restores the user's previous interview page. Wait for
    # the enabled global control instead of demanding a new blank interview.
    Wait-Named 'My returns' 90 | Out-Null
}
function Close-App {
    if($script:process -and !$script:process.HasExited) {
        $script:process.CloseMainWindow() | Out-Null
        if(!$script:process.WaitForExit(15000)) { Stop-Process -Id $script:process.Id -Force; throw 'Native window did not close normally.' }
    }
}
function Save-Native-Export([string]$target) {
    $oldRoot=$script:root
    $condition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$script:process.Id)
    $nameCondition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty,'Save As')
    $until=(Get-Date).AddSeconds(60)
    $dialog=$null
    while((Get-Date) -lt $until) {
        $windows=[System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$condition)
        foreach($window in $windows) {
            # Windows' hosted runner exposes this system picker as a Window
            # containing Pane controls, including the filename and Save. The
            # real failure capture showed the picker already open; requiring
            # ControlType.Edit incorrectly rejected it. Find this app's actual
            # named dialog and use its normal filename keyboard accelerator.
            $dialogs=$window.FindAll([System.Windows.Automation.TreeScope]::Subtree,$nameCondition)
            foreach($candidate in $dialogs) {
                if($candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::Window -and !$candidate.Current.IsOffscreen -and $candidate.Current.NativeWindowHandle -ne 0) {
                    $dialog=$candidate; break
                }
            }
            if($dialog) { break }
        }
        if($dialog) { break }
        Start-Sleep -Milliseconds 250
    }
    try {
        if(!$dialog) { throw 'The native export did not open a user-controlled Save As dialog.' }
        $script:root=$dialog
        Wait-Named 'File name:' 10 | Out-Null
        [TaxWindow]::SetForegroundWindow([IntPtr]::new($dialog.Current.NativeWindowHandle)) | Out-Null
        [System.Windows.Forms.SendKeys]::SendWait('%n')
        [System.Windows.Forms.SendKeys]::SendWait('^a')
        [System.Windows.Forms.SendKeys]::SendWait($target)
        Save-Screenshot 'windows-native-PDF-save-as.png' $false
        Click-Observed (Wait-Named 'Save' 10)
    } finally { $script:root=$oldRoot }
    $until=(Get-Date).AddSeconds(60)
    while((Get-Date) -lt $until) {
        if((Test-Path $target) -and (Get-Item $target).Length -gt 1000) { return }
        Start-Sleep -Milliseconds 250
    }
    throw 'The user-selected native export file was not actually saved.'
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
    $value=$field.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::ValueProperty)
    if([string]$value -ne '7000') { throw "Actual withholding input is not the intended value 7000: $value" }
    # Focusing a low W2 field can scroll the whole interview and put the refund
    # header above the viewport. Read its real value, then bring header/Save back.
    Wait-Named '$1,913' 120 $false | Out-Null
    Scroll-Top
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
    Click-Observed (Wait-Named 'Save & export')
    Click-Observed (Wait-Named 'Download PDF')
    $pdf=Join-Path $OutputDir 'windows-native-export-DRAFT.pdf'
    Save-Native-Export $pdf
    $env:TAX_REBORN_SYNTHETIC_EXPORT=$pdf
    python -c "import os; from pathlib import Path; import forms,tax_engine; d=tax_engine.demo_returns()[0]['data']; d['w2'][0]['federal_withholding']='7000'; r=tax_engine.calculate_return(d); assert r['summary']['refund']==1913; print(forms.verify_fields(Path(os.environ['TAX_REBORN_SYNTHETIC_EXPORT']).read_bytes(),forms.field_values(r)))"
    if($LASTEXITCODE -ne 0) { throw 'The actual native-exported PDF failed field readback.' }
    Remove-Item Env:TAX_REBORN_SYNTHETIC_EXPORT
    $checks.Add('Actual native Save As export saved an IRS1040 draft PDF; field readback matched the edited 1913 USD return.')
    Save-Screenshot 'windows-native-after-PDF-export.png'
    Click-Observed (Wait-Named 'My returns')
    Click-Observed (Wait-Named 'Synthetic examples')
    Click-Observed (Wait-Named 'Open distribution example')
    Wait-Named '$13,780' 120 $false | Out-Null
    Scroll-Top
    Click-Observed (Wait-Named 'Dividends · 1099-DIV')
    $component=Wait-Edit 'Box 2b · Unrecaptured Section 1250 gain'
    if([string]($component.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::ValueProperty)) -ne '10000') { throw 'Actual native1099-DIV Box2b did not retain10000 USD.' }
    $component.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    [System.Windows.Forms.SendKeys]::SendWait('9000{TAB}')
    Wait-Named '$13,850' 120 $false | Out-Null
    Scroll-Top
    Click-Observed (Wait-Named 'Save')
    Wait-Named 'Saved on this device' | Out-Null
    Save-Screenshot 'windows-native-special-edited-13850.png'
    $checks.Add('Actual1099-DIV special distribution example calculated13780 USD, Box2b edit10000 to9000 recomputed13850 USD and saved.')
    Close-App; Launch-App
    Wait-Named '$13,850' 120 $false | Out-Null
    Scroll-Top
    Save-Screenshot 'windows-native-special-reopened-13850.png'
    $checks.Add('Native special distribution saved amounts and13850 USD result survived normal close/relaunch.')
    Click-Observed (Wait-Named 'Save & export')
    Click-Observed (Wait-Named 'Download official packet')
    $specialPdf=Join-Path $OutputDir 'windows-native-special-official-packet.pdf'
    Save-Native-Export $specialPdf
    $env:TAX_REBORN_SYNTHETIC_EXPORT=$specialPdf
    python -c "import os,io; from pathlib import Path; from pypdf import PdfReader; r=PdfReader(io.BytesIO(Path(os.environ['TAX_REBORN_SYNTHETIC_EXPORT']).read_bytes())); f=r.get_fields(); p='f1040sd_1.topmostSubform[0].Page2[0].'; assert str(f[p+'f2_2[0]']['/V'])=='10000'; assert str(f[p+'f2_3[0]']['/V'])=='9000'; assert 'Worksheet line 47: '+chr(36)+'16,150' in '\n'.join(x.extract_text() for x in r.pages); print('Actual native special-rate packet readback: ScheduleD18=10000,19=9000, worksheet47=16150')"
    if($LASTEXITCODE -ne 0) { throw 'Actual special-distribution packet fields/workpaper failed readback.' }
    Remove-Item Env:TAX_REBORN_SYNTHETIC_EXPORT
    $checks.Add('Actual native official packet saved and read backScheduleD18/19=10000/9000 andworksheet47=16150 USD.')
    $receipt.native_gui_tested=$true; $receipt.all_passed=$true
} catch {
    $receipt.error=$_.Exception.Message
    if($root) {
        try { Save-Screenshot 'windows-native-failure.png' $false } catch {}
        try {
            $elements=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
            $names=foreach($element in $elements) { $element.Current.ControlType.ProgrammaticName+' | '+$element.Current.Name }
            $names | Set-Content -Encoding utf8 (Join-Path $OutputDir 'windows-native-failure-hierarchy.txt')
        } catch {}
    }
    throw
} finally {
    $receipt.checks=@($checks); $receipt.checked_at_utc=(Get-Date).ToUniversalTime().ToString('o')
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $OutputDir 'windows-native-gui-smoke.json')
    if($process -and !$process.HasExited) { $process.CloseMainWindow() | Out-Null; if(!$process.WaitForExit(10000)) { Stop-Process -Id $process.Id -Force } }
}
