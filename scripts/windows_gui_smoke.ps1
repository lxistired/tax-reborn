param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [Parameter(Mandatory=$true)][string]$DataDir,
    [switch]$MixedOnly,
    [switch]$EffectiveRegistry
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
            if($candidate -and ($candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -or $candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit -or $candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::CheckBox -or $candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::ComboBox)) {
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
    if ($item.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)) {
        ([System.Windows.Automation.TogglePattern]$pattern).Toggle(); return
    }
    $rect = $item.Current.BoundingRectangle
    if ($rect.IsEmpty -or $item.Current.IsOffscreen) {
        $scrollItem = $null
        if ($item.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern,[ref]$scrollItem)) {
            ([System.Windows.Automation.ScrollItemPattern]$scrollItem).ScrollIntoView()
        } else {
            # WebView focus scrolls an observed input/control into its own
            # scrolling region without guessing a desktop coordinate.
            $item.SetFocus()
        }
        $rect = $item.Current.BoundingRectangle
    }
    # WebView2 can scroll the observed input before UIA refreshes its bounds.
    # The captured address-flow failure shows the field visible in the final
    # screenshot. Wait for the provider's updated rectangle before clicking.
    $visibleUntil=(Get-Date).AddSeconds(5)
    while(($rect.IsEmpty -or $item.Current.IsOffscreen) -and (Get-Date) -lt $visibleUntil) {
        Start-Sleep -Milliseconds 100
        $rect=$item.Current.BoundingRectangle
    }
    if ($rect.IsEmpty -or $item.Current.IsOffscreen) { throw ('The UI control has no visible click target: '+$item.Current.Name) }
    [TaxWindow]::SetCursorPos([int]($rect.Left+$rect.Width/2),[int]($rect.Top+$rect.Height/2)) | Out-Null
    [TaxWindow]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
    [TaxWindow]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
}
function Wait-Control([string]$type,[string]$label,[bool]$prefix=$false) {
    $until=(Get-Date).AddSeconds(30)
    while((Get-Date) -lt $until) {
        $items=$script:root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
        foreach($item in $items) {
            if($item.Current.ControlType.ProgrammaticName -eq ('ControlType.'+$type) -and
               (($prefix -and $item.Current.Name.StartsWith($label)) -or (!$prefix -and $item.Current.Name -eq $label))) { return $item }
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Native WebView did not expose $type with label $label"
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
function Save-Native-Export([string]$target, [int]$minimumBytes=1000) {
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
        if((Test-Path $target) -and (Get-Item $target).Length -gt $minimumBytes) { return }
        Start-Sleep -Milliseconds 250
    }
    throw 'The user-selected native export file was not actually saved.'
}
# Owned native TaxML migration on the isolated GitHub Actions Windows desktop.
# These actions are not used on the user's computer or their returns.
function Choose-Owned-Native-File([string]$label,[string[]]$target) {
    foreach($file in $target) { if(!(Test-Path $file)) { throw "Missing owned fixture: $file" } }
    $selection=($target | ForEach-Object { '"'+$_+'"' }) -join ' '
    Click-Observed (Wait-Named ($label+': No file chosen'))
    $oldRoot=$script:root
    $pidCondition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$script:process.Id)
    $nameCondition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty,'Open')
    $dialog=$null; $until=(Get-Date).AddSeconds(60)
    while((Get-Date) -lt $until -and !$dialog) {
        $windows=[System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$pidCondition)
        foreach($window in $windows) {
            foreach($candidate in $window.FindAll([System.Windows.Automation.TreeScope]::Subtree,$nameCondition)) {
                if($candidate.Current.ControlType -eq [System.Windows.Automation.ControlType]::Window -and !$candidate.Current.IsOffscreen -and $candidate.Current.NativeWindowHandle -ne 0) { $dialog=$candidate; break }
            }
            if($dialog) { break }
        }
        if(!$dialog) { Start-Sleep -Milliseconds 250 }
    }
    try {
        if(!$dialog) { throw 'No actual application-owned Open picker appeared.' }
        $script:root=$dialog; Wait-Named 'File name:' 10 | Out-Null
        [TaxWindow]::SetForegroundWindow([IntPtr]::new($dialog.Current.NativeWindowHandle)) | Out-Null
        if($target.Count -gt 1) {
            $folder=Split-Path $target[0]
            foreach($file in $target) { if((Split-Path $file) -ne $folder) { throw 'Owned multi-selection requires one actual fixture folder.' } }
            # The failed native readback exposed2 files instead of3. Navigate
            # the real dialog to the common folder and enter short quoted
            # basenames instead of one long list of fully qualified paths.
            [System.Windows.Forms.SendKeys]::SendWait('%d')
            [System.Windows.Forms.SendKeys]::SendWait($folder+'{ENTER}')
            Start-Sleep -Milliseconds 500
            $selection=($target | ForEach-Object { '"'+(Split-Path $_ -Leaf)+'"' }) -join ' '
        }
        [System.Windows.Forms.SendKeys]::SendWait('%n'); [System.Windows.Forms.SendKeys]::SendWait('^a')
        [System.Windows.Forms.SendKeys]::SendWait($selection)
        Click-Observed (Wait-Named 'Open' 10)
    } finally { $script:root=$oldRoot }
    if($target.Count -gt 1) { Wait-Named ($label+': '+$target.Count+' files') 15 | Out-Null }
    Wait-Named 'Inspect locally' | Out-Null
}
function Set-Owned-Edit([string]$label,[string]$text) {
    $field=Wait-Edit $label
    # A prior Save As returns to WebView2's download/autofill surfaces. UIA
    # focus alone did not deliver keyboard text in the captured CI failure.
    # Use the observed editable control's native ValuePattern, then blur it.
    [TaxWindow]::SetForegroundWindow($script:process.MainWindowHandle) | Out-Null
    Click-Observed $field
    $pattern=$field.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    ([System.Windows.Automation.ValuePattern]$pattern).SetValue($text)
    $field.SetFocus(); [System.Windows.Forms.SendKeys]::SendWait('{TAB}')
    $until=(Get-Date).AddSeconds(10)
    while((Get-Date) -lt $until) {
        $readback=Wait-Edit $label 5
        if([string]$readback.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::ValueProperty) -eq $text) { return }
        Start-Sleep -Milliseconds 100
    }
    throw "Edited field did not retain $label = $text"
}
function Inspect-Owned-Income([string]$fixture) {
    Click-Observed (Wait-Named 'Documents'); Click-Observed (Wait-Named 'Open TaxML / binary .tax')
    $folder=Join-Path (Split-Path $Executable) '_internal/fixtures/taxml'
    Choose-Owned-Native-File 'Choose plaintext TaxML or .tax container' (Join-Path $folder ($fixture+'.xml'))
    Choose-Owned-Native-File 'Choose explicit TaxML wire profile' (Join-Path $folder ($fixture+'-profile.json'))
    Choose-Owned-Native-File 'Choose caller-owned XPRF registries' (Join-Path $folder ($fixture+'.xprf'))
    $format=Wait-Named 'TaxML container declaration'; $format.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
    Click-Observed (Wait-Named 'Acknowledge the selected unverified wire profile')
    Click-Observed (Wait-Named 'Inspect locally')
}
try {
    Launch-App
    $checks.Add('Packaged Windows WebView2 native window loaded the real interview.')
    Save-Screenshot 'windows-native-initial.png'
    if(!$MixedOnly) {
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
    Click-Observed (Wait-Named 'My returns')
    Click-Observed (Wait-Named 'Synthetic examples')
    Click-Observed (Wait-Named 'Open AMT example')
    Wait-Named '$10,963' 120 $false | Out-Null
    Scroll-Top
    Click-Observed (Wait-Named 'Alternative Minimum Tax')
    $iso=Wait-Edit 'Iso adjustment'
    $iso.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    [System.Windows.Forms.SendKeys]::SendWait('0{TAB}')
    Wait-Named '$24,587' 120 $false | Out-Null
    $iso.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    [System.Windows.Forms.SendKeys]::SendWait('100000{TAB}')
    Wait-Named '$10,963' 120 $false | Out-Null
    Scroll-Top
    Click-Observed (Wait-Named 'Save')
    Wait-Named 'Saved on this device' | Out-Null
    Save-Screenshot 'windows-native-AMT-edited-10963.png'
    $checks.Add('Actual specialAMT example refund10963; ISO100000 to0 recomputed24587, restore100000 recomputed10963 andsaved.')
    Close-App; Launch-App
    Wait-Named '$10,963' 120 $false | Out-Null
    Scroll-Top
    Save-Screenshot 'windows-native-AMT-reopened-10963.png'
    $checks.Add('Native positiveAMT inputs andrefund10963 survived normal close/relaunch.')
    Click-Observed (Wait-Named 'Save & export')
    Click-Observed (Wait-Named 'Download official packet')
    $amtPdf=Join-Path $OutputDir 'windows-native-AMT-official-packet.pdf'
    Save-Native-Export $amtPdf
    python scripts/verify_special_amt_packet.py $amtPdf
    if($LASTEXITCODE -ne 0) { throw 'Actual native positiveAMT packet all29PartIII fields failed independentIRS readback.' }
    $checks.Add('Actual native officialAMT packet saved and readback verified all29PartIII fields,2page6251 and1040line17=13624.')
    Click-Observed (Wait-Named 'My returns')
    Click-Observed (Wait-Named 'Synthetic examples')
    Click-Observed (Wait-Named 'Open child income example')
    Wait-Named '$12,484' 120 $false | Out-Null
    Scroll-Top
    Click-Observed (Wait-Named 'Child Interest and Dividends — Form 8814')
    $childInterest=Wait-Edit 'Child taxable interest — Form 8814 line 1a'
    $childInterest.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    [System.Windows.Forms.SendKeys]::SendWait('0{TAB}')
    Wait-Named '$12,868' 120 $false | Out-Null
    $childInterest=Wait-Edit 'Child taxable interest — Form 8814 line 1a'
    $childInterest.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    [System.Windows.Forms.SendKeys]::SendWait('2000{TAB}')
    Wait-Named '$12,484' 120 $false | Out-Null
    Scroll-Top
    Click-Observed (Wait-Named 'Save')
    Wait-Named 'Saved on this device' | Out-Null
    Save-Screenshot 'windows-native-child-income-saved-12484.png'
    $checks.Add('ActualForm8814 childinterest2000 to0 andback recomputedparentrefund12484 to12868 andback; normalnativefields andSave exercised.')
    Close-App; Launch-App
    Wait-Named '$12,484' 120 $false | Out-Null
    Scroll-Top
    Save-Screenshot 'windows-native-child-income-reopened-12484.png'
    $checks.Add('Savedchildfacts/amounts andparentrefund12484 survived normalnativeclose/relaunch.')
    Click-Observed (Wait-Named 'Save & export')
    Click-Observed (Wait-Named 'Download official packet')
    $childPdf=Join-Path $OutputDir 'windows-native-child-income-official-packet.pdf'
    Save-Native-Export $childPdf
    python scripts/verify_child_income_packet.py $childPdf | Set-Content -Encoding utf8 (Join-Path $OutputDir 'windows-native-child-income-packet-readback.json')
    if($LASTEXITCODE -ne 0) { throw 'ActualnativeForm8814 packet failed independentparent/childfield,appearance,ratio andtaxcheckbox checks.' }
    $checks.Add('Actualnative12pagepacket savedto disk; separatechild8814, parent3a/3b/7a/8/16/24/35a, sourceannotations, splitratios and1040checkbox allverified.')
    Click-Observed (Wait-Named 'My returns')
    Click-Observed (Wait-Named 'Synthetic examples')
    Click-Observed (Wait-Named 'Open birthday example')
    Wait-Named '$1,649' 120 $false | Out-Null
    Scroll-Top
    $dob=Wait-Edit 'Date of birth (YYYY-MM-DD)'
    $dob.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    [System.Windows.Forms.SendKeys]::SendWait('2001-01-02{TAB}')
    Wait-Named '$1,000' 120 $false | Out-Null
    Scroll-Top
    Click-Observed (Wait-Named 'Save')
    Wait-Named 'Saved on this device' | Out-Null
    Save-Screenshot 'windows-native-birthday-edited-1000.png'
    $checks.Add('ActualDOB2001-01-01 to2001-01-02 changed EIC/refund649/1649 to0/1000 and saved.')
    Close-App; Launch-App
    Wait-Named '$1,000' 120 $false | Out-Null
    Scroll-Top
    $dob=Wait-Edit 'Date of birth (YYYY-MM-DD)'
    if([string]($dob.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::ValueProperty)) -ne '2001-01-02') { throw 'ChangedDOB did not survive native restart.' }
    $checks.Add('ActualchangedDOB andrefund1000 survived normalnativeclose/relaunch.')
    Click-Observed (Wait-Named 'Save & export')
    Click-Observed (Wait-Named 'Download PDF')
    $birthdayPdf=Join-Path $OutputDir 'windows-native-birthday-DRAFT.pdf'
    Save-Native-Export $birthdayPdf
    $env:TAX_REBORN_SYNTHETIC_EXPORT=$birthdayPdf
    python -c "import os,io; from pathlib import Path; from pypdf import PdfReader; f=PdfReader(io.BytesIO(Path(os.environ['TAX_REBORN_SYNTHETIC_EXPORT']).read_bytes())).get_fields(); p='topmostSubform[0].Page2[0].'; assert str(f[p+'f2_23[0]']['/V'])=='0'; assert str(f[p+'f2_31[0]']['/V'])=='1000'; assert str(f[p+'c2_13[0]']['/V'])=='/1'"
    if($LASTEXITCODE -ne 0) { throw 'ActualnativeDOB PDF amount readback failed.' }
    Remove-Item Env:TAX_REBORN_SYNTHETIC_EXPORT
    $checks.Add('ActualnativeDOB draft PDF saved bysystemSaveAs andEIC0/refund1000 read back.')
    # The previous synthetic workflows are saved before opening this fresh draft.
    Scroll-Top; Click-Observed (Wait-Named 'My returns'); Click-Observed (Wait-Named '+ New return')
    Set-Owned-Edit 'Return name' 'Synthetic Windows TaxML INT DIV migration'
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Inspect-Owned-Income 'synthetic-native-interest'
    Click-Observed (Wait-Named 'Review 1099-INT candidate')
    Set-Owned-Edit '1099-INT payer name' 'Synthetic native Windows bank'
    Click-Observed (Wait-Named 'Confirm supported 1099-INT situation')
    Click-Observed (Wait-Named 'Confirm all TaxML 1099-INT amounts and household')
    Click-Observed (Wait-Named 'Add reviewed 1099-INT')
    Wait-Named '$20' 120 $false | Out-Null
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    $checks.Add('Native Windows system file pickers read owned XML, JSON and XPRF; four-box INT review added a real20 USD draft.')
    Inspect-Owned-Income 'synthetic-native-dividend'
    Click-Observed (Wait-Named 'Review 1099-DIV candidate')
    Set-Owned-Edit '1099-DIV payer name' 'Synthetic native Windows fund'
    Set-Owned-Edit 'Box 4 · Federal income tax withheld' '201.49'
    Click-Observed (Wait-Named 'Confirm qualified dividend eligibility')
    Click-Observed (Wait-Named 'Confirm supported 1099-DIV situation')
    Click-Observed (Wait-Named 'Confirm all TaxML 1099-DIV amounts and household')
    Click-Observed (Wait-Named 'Download corrected XML')
    $xml=Join-Path $OutputDir 'windows-native-dividend-corrected.xml'
    Save-Native-Export $xml 100
    $env:TAX_REBORN_OWNED_XML=$xml
    python -c "import os;from pathlib import Path;p=Path('fixtures/taxml/synthetic-native-dividend.xml').read_bytes();a=Path(os.environ['TAX_REBORN_OWNED_XML']).read_bytes();assert a==p.replace(b'>200.49</td:value>',b'>201.49</td:value>')"
    if($LASTEXITCODE -ne 0) { throw 'Native corrected XML did not preserve all other source bytes.' }
    Remove-Item Env:TAX_REBORN_OWNED_XML
    Click-Observed (Wait-Named 'Add reviewed 1099-DIV')
    Wait-Named '$222' 120 $false | Out-Null
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Save-Screenshot 'windows-native-taxml-INT-DIV-222.png'
    $checks.Add('Native six-box DIV manual eligibility and edited withholding produced222 USD joint INT/DIV refund; system corrected XML readback preserved source bytes.')
    Close-App; Launch-App; Wait-Named '$222' 120 $false | Out-Null
    Scroll-Top; Click-Observed (Wait-Named 'Dividends · 1099-DIV')
    Wait-Named 'Reviewed 1099-DIV import snapshot' | Out-Null
    Click-Observed (Wait-Named 'View source document'); Click-Observed (Wait-Named 'Download source')
    $original=Join-Path $OutputDir 'windows-native-dividend-original.xml'; Save-Native-Export $original 100
    $env:TAX_REBORN_OWNED_XML=$original
    python -c "import os;from pathlib import Path;assert Path(os.environ['TAX_REBORN_OWNED_XML']).read_bytes()==Path('fixtures/taxml/synthetic-native-dividend.xml').read_bytes()"
    if($LASTEXITCODE -ne 0) { throw 'Original native attachment changed after corrected export and relaunch.' }
    Remove-Item Env:TAX_REBORN_OWNED_XML
    $checks.Add('Normal close/relaunch preserved both reviewed records and222 USD result; six-box snapshot and original XML attachment survived and read back byte-identically.')
    Save-Screenshot 'windows-native-taxml-reopened-source.png'
    $receipt.native_taxml_INT_DIV_changed_flow_passed=$true
    Click-Observed (Wait-Named 'Close dialog')
    }
    # New mixed-source flow uses one native Open picker selecting three XPRF
    # files. No JS injection or database seeding supplies the imported values.
    Scroll-Top; Click-Observed (Wait-Named 'My returns'); Click-Observed (Wait-Named '+ New return')
    Set-Owned-Edit 'Return name' 'Synthetic Windows mixed income migration'
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Click-Observed (Wait-Named 'Documents'); Click-Observed (Wait-Named 'Open TaxML / binary .tax')
    $folder=Join-Path (Split-Path $Executable) '_internal/fixtures/taxml'
    Choose-Owned-Native-File 'Choose plaintext TaxML or .tax container' (Join-Path $folder 'synthetic-mixed-income.xml')
    Choose-Owned-Native-File 'Choose explicit TaxML wire profile' (Join-Path $folder 'synthetic-mixed-income-profile.json')
    $registries=@('synthetic-modern-windows-w2.xprf','synthetic-native-interest.xprf','synthetic-native-dividend.xprf') | ForEach-Object { Join-Path $folder $_ }
    Choose-Owned-Native-File 'Choose caller-owned XPRF registries' $registries
    $format=Wait-Named 'TaxML container declaration'; $format.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
    Click-Observed (Wait-Named 'Acknowledge the selected unverified wire profile')
    Click-Observed (Wait-Named 'Inspect locally')
    foreach($label in @('W-2','1099-INT','1099-DIV')) {
        Click-Observed (Wait-Named ('Review '+$label+' candidate'))
        if($label -eq 'W-2') {
            Set-Owned-Edit 'Employer name' 'Synthetic Windows mixed employer'
            $owner=Wait-Control 'ComboBox' 'Whose W-2 is this?'; $owner.SetFocus()
            [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
            Set-Owned-Edit 'Box 7 · Social Security tips' '0'
            Set-Owned-Edit 'Box 10 · Dependent-care benefits' '0'
            Click-Observed (Wait-Named 'Confirm all TaxML W-2 amounts and ownership')
        } else {
            Set-Owned-Edit ($label+' payer name') ('Synthetic Windows mixed '+$label+' payer')
            Click-Observed (Wait-Named ('Confirm supported '+$label+' situation'))
            if($label -eq '1099-DIV') { Click-Observed (Wait-Named 'Confirm qualified dividend eligibility') }
            Click-Observed (Wait-Named ('Confirm all TaxML '+$label+' amounts and household'))
        }
        Click-Observed (Wait-Named ('Add reviewed '+$label))
        Wait-Named 'TaxML inspection results' | Out-Null
        $added=Get-Named ('Review '+$label+' candidate') $false
        if(!$added -or $added.Current.IsEnabled) { throw ('Added source form was not disabled in continued review: '+$label) }
    }
    Save-Screenshot 'windows-native-mixed-three-forms-added.png'
    Click-Observed (Wait-Named 'Close dialog')
    Wait-Named '$344' 120 $false | Out-Null
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    $checks.Add('Native multi-file Open picker supplied three owned XPRF registries; three income types independently reviewed from one XML and each added form disabled.')
    Close-App; Launch-App; Wait-Named '$344' 120 $false | Out-Null
    Save-Screenshot 'windows-native-mixed-reopened-344.png'
    $env:TAX_REBORN_OWNED_DATADIR=$DataDir
    python scripts/verify_windows_mixed_native.py --data-dir $DataDir --output (Join-Path $OutputDir 'windows-native-mixed-readback.json')
    if($LASTEXITCODE -ne 0) { throw 'Native saved mixed-form metadata, ownership, amounts or344 USD calculation failed independent readback' }
    $checks.Add('Normal close/relaunch preserved all three reviewed forms, shared attachment and distinct source paths; independent SQLite readback verified344 USD and actual saved line amounts.')
    Scroll-Top; Click-Observed (Wait-Named 'Documents'); Click-Observed (Wait-Named 'Open TaxML / binary .tax')
    Choose-Owned-Native-File 'Choose plaintext TaxML or .tax container' (Join-Path $folder 'synthetic-mixed-income.xml')
    Choose-Owned-Native-File 'Choose explicit TaxML wire profile' (Join-Path $folder 'synthetic-mixed-income-profile.json')
    Choose-Owned-Native-File 'Choose caller-owned XPRF registries' $registries
    $format=Wait-Named 'TaxML container declaration'; $format.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
    Click-Observed (Wait-Named 'Acknowledge the selected unverified wire profile'); Click-Observed (Wait-Named 'Inspect locally')
    Click-Observed (Wait-Named 'Review 1099-INT candidate')
    Set-Owned-Edit '1099-INT payer name' 'Synthetic Windows mixed 1099-INT payer'
    Click-Observed (Wait-Named 'Confirm supported 1099-INT situation')
    Click-Observed (Wait-Named 'Confirm all TaxML 1099-INT amounts and household')
    Click-Observed (Wait-Named 'Add reviewed 1099-INT')
    Wait-Named 'This source already supplied a 1099-INT. Edit the existing record instead of adding it again.' | Out-Null
    Set-Owned-Edit 'Box 1 · Interest income' '101.24'
    Click-Observed (Wait-Named 'Download corrected XML')
    $mixedXml=Join-Path $OutputDir 'windows-native-mixed-selected-corrected.xml'; Save-Native-Export $mixedXml 100
    python scripts/verify_windows_mixed_native.py --data-dir $DataDir --corrected-xml $mixedXml --output (Join-Path $OutputDir 'windows-native-mixed-final-readback.json')
    if($LASTEXITCODE -ne 0) { throw 'Native corrected selected XML or duplicate refusal failed saved record/readback' }
    Save-Screenshot 'windows-native-mixed-duplicate-corrected.png'
    Click-Observed (Wait-Named 'Close dialog')
    Close-App
    python scripts/verify_windows_mixed_native.py --data-dir $DataDir --corrected-xml $mixedXml --output (Join-Path $OutputDir 'windows-native-mixed-durable-export-readback.json')
    if($LASTEXITCODE -ne 0) { throw 'System-saved corrected XML did not survive normal application close.' }
    Launch-App; Wait-Named '$344' 120 $false | Out-Null
    $checks.Add('Native repeated-source add was refused; system Save As exported only selected interest correction and independent readback after normal App close proved W2/DIV bytes plus saved records unchanged.')
    $receipt.native_mixed_taxml_changed_flow_passed=$true
    # The shipped independent binary samples use the exact file decoder and
    # reviewed-record pipeline; no injected JS, source XML or seeded return.
    Scroll-Top; Click-Observed (Wait-Named 'My returns'); Click-Observed (Wait-Named '+ New return')
    Set-Owned-Edit 'Return name' 'Synthetic Windows binary income migration'
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Click-Observed (Wait-Named 'Documents'); Click-Observed (Wait-Named 'Open TaxML / binary .tax')
    Click-Observed (Wait-Named 'Try independently generated binary samples')
    $binaryOptions=@()
    if($EffectiveRegistry) {
        $binaryOptions=@('--effective-registry','--value-table')
        Click-Observed (Wait-Named 'Load income sample with two registries')
        Click-Observed (Wait-Named 'Selected registry sources')
        $effectiveProfile=Get-Content 'fixtures/binary-tax/merged-profile.json' -Raw | ConvertFrom-Json
        # Expanding details exposes these real UIA text elements below the
        # small runner viewport. Presence is distinct from viewport visibility.
        Wait-Named ('Visible fields · '+$effectiveProfile.registry_order[0].Substring(0,12)+' · resource 1') 90 $false | Out-Null
        Wait-Named ('Hidden fields · '+$effectiveProfile.registry_order[1].Substring(0,12)+' · resource 1') 90 $false | Out-Null
        Save-Screenshot 'windows-native-effective-registry-sources.png'
        Click-Observed (Wait-Named 'Selected registry sources')
    } else { Click-Observed (Wait-Named 'Load binary income sample') }
    foreach($label in @('W-2','1099-INT','1099-DIV')) {
        Click-Observed (Wait-Named ('Review '+$label+' candidate'))
        if($label -eq 'W-2') {
            Set-Owned-Edit 'Employer name' 'Synthetic Windows binary employer'
            $owner=Wait-Control 'ComboBox' 'Whose W-2 is this?'; $owner.SetFocus()
            [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
            Set-Owned-Edit 'Box 7 · Social Security tips' '0'
            Set-Owned-Edit 'Box 10 · Dependent-care benefits' '0'
            Click-Observed (Wait-Named 'Confirm all TaxML W-2 amounts and ownership')
        } else {
            Set-Owned-Edit ($label+' payer name') ('Synthetic Windows binary '+$label+' payer')
            Click-Observed (Wait-Named ('Confirm supported '+$label+' situation'))
            if($label -eq '1099-DIV') { Click-Observed (Wait-Named 'Confirm qualified dividend eligibility') }
            Click-Observed (Wait-Named ('Confirm all TaxML '+$label+' amounts and household'))
        }
        Click-Observed (Wait-Named ('Add reviewed '+$label)); Wait-Named 'TaxML inspection results' | Out-Null
    }
    Click-Observed (Wait-Named 'Close dialog'); Wait-Named '$344' 120 $false | Out-Null
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Close-App; Launch-App; Wait-Named '$344' 120 $false | Out-Null
    Save-Screenshot 'windows-native-binary-income-reopened-344.png'
    python scripts/verify_binary_native.py @binaryOptions --data-dir $DataDir --output (Join-Path $OutputDir 'windows-native-binary-income-readback.json')
    if($LASTEXITCODE -ne 0) { throw 'Saved binary income and source receipts failed readback' }
    Scroll-Top; Click-Observed (Wait-Named 'Documents'); Click-Observed (Wait-Named 'Open TaxML / binary .tax')
    Click-Observed (Wait-Named 'Try independently generated binary samples')
    if($EffectiveRegistry) {
        Click-Observed (Wait-Named 'Load source with indexed table values')
        Wait-Named 'Income additions are blocked by 2 unresolved source facts. Filing-status setup is checked separately.' | Out-Null
    }
    else { Click-Observed (Wait-Named 'Load nested binary sample') }
    Click-Observed (Wait-Named 'Inspect / edit binary fields')
    if($EffectiveRegistry) {
        Wait-Named 'value_table · fields 12–12 · saved last-used record 3' 90 $false | Out-Null
        Wait-Named 'OWNED_AMOUNT [3]' 90 $false | Out-Null
        Save-Screenshot 'windows-native-derived-table-boundary-and-values.png'
    }
    Set-Owned-Edit 'Binary WAGES [0]' '1234.57'
    Click-Observed (Wait-Named 'Confirm binary source corrections'); Click-Observed (Wait-Named 'Download corrected binary')
    $binaryCopy=Join-Path $OutputDir 'windows-native-nested-corrected.taxbin'; Save-Native-Export $binaryCopy 100
    Save-Screenshot 'windows-native-binary-structures-exported.png'
    Click-Observed (Wait-Named 'Close dialog'); Close-App
    python scripts/verify_binary_native.py @binaryOptions --data-dir $DataDir --corrected-binary $binaryCopy --output (Join-Path $OutputDir 'windows-native-binary-final-readback.json')
    if($LASTEXITCODE -ne 0) { throw 'System-saved full binary correction failed independent structure readback' }
    Launch-App; Wait-Named '$344' 120 $false | Out-Null
    $receipt.native_binary_income_and_recursive_source_passed=$true
    if($EffectiveRegistry) {
        $receipt.native_effective_registry_passed=$true
        $receipt.native_derived_value_table_preservation_passed=$true
        $checks.Add('Ordered two-carrier field selection preserved visible/hidden sources; reviewed income344 saved and cold-reopened; actual system binary export retained nested tables/child/links with complete readback.')
    }
    $checks.Add('Binary income decoded, three forms reviewed, real344 USD recalculated and saved/relaunched; system-saved nested binary edit retained child/table/link/other facts by independent readback.')

    Remove-Item Env:TAX_REBORN_OWNED_DATADIR
    if(!$MixedOnly) {
    # Create a separate owned synthetic return in the same real SQLite
    # workspace, then operate its new interview and system export through UIA.
    $env:TAX_REBORN_OWNED_DATADIR=$DataDir
    python -c "import os,sys;sys.path.insert(0,'tests');import server,tax_engine;from payment_voucher_qa import cases,return_for;d=return_for(tax_engine,cases()[0]);d['filing_details'].update(balance_due_payment_method='unanswered',paper_payment_confirmed=False);server.Store(os.environ['TAX_REBORN_OWNED_DATADIR']).save({'data':d})"
    if($LASTEXITCODE -ne 0) { throw 'Owned payment-voucher return was not saved.' }
    Remove-Item Env:TAX_REBORN_OWNED_DATADIR
    Scroll-Top; Click-Observed (Wait-Named 'My returns'); Wait-Named 'Synthetic voucher fifteen-percent-owed' | Out-Null
    Click-Observed (Wait-Named 'Open'); Wait-Named '$2,435' 120 $false | Out-Null
    Click-Observed (Wait-Named 'Balance due & payment voucher')
    $method=Wait-Control 'ComboBox' 'Balance-due payment method'; $method.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
    $choice=Wait-Control 'ComboBox' 'Paper voucher amount'; $choice.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
    Set-Owned-Edit 'Entered check or money-order amount' '1000.25'
    Click-Observed (Wait-Control 'CheckBox' 'I verified the paper payment amount and method' $true)
    Set-Owned-Edit 'Entered check or money-order amount' '1000.26'
    $confirmation=Wait-Control 'CheckBox' 'I verified the paper payment amount and method' $true
    $toggle=$confirmation.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if(([System.Windows.Automation.TogglePattern]$toggle).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) { throw 'Payment edit did not invalidate confirmation.' }
    Click-Observed $confirmation
    Click-Observed (Wait-Named 'Interest · 1099-INT')
    Click-Observed (Wait-Named '+ Add another 1099-INT')
    Click-Observed (Wait-Named 'Remove 1099-INT 2')
    Click-Observed (Wait-Named 'Balance due & payment voucher')
    $confirmation=Wait-Control 'CheckBox' 'I verified the paper payment amount and method' $true
    $toggle=$confirmation.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if(([System.Windows.Automation.TogglePattern]$toggle).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) { throw 'Record addition/removal did not invalidate paper-payment confirmation.' }
    Click-Observed $confirmation
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Click-Observed (Wait-Named 'Download official packet')
    $voucherPdf=Join-Path $OutputDir 'windows-native-payment-voucher.pdf'; Save-Native-Export $voucherPdf
    $env:TAX_REBORN_OWNED_VOUCHER_PDF=$voucherPdf
    python -c "import os,sys,io;sys.path.insert(0,'tests');from pathlib import Path;from pypdf import PdfReader;import official_forms;from payment_voucher_qa import verify_packet;p=Path(os.environ['TAX_REBORN_OWNED_VOUCHER_PDF']).read_bytes();verify_packet(p,'1000.26',official_forms);f=PdfReader(io.BytesIO(p)).get_fields();assert f['topmostSubform[0].Page2[0].f2_35[0]']['/V']=='2435'"
    if($LASTEXITCODE -ne 0) { throw 'Native system-saved payment-voucher fields failed readback.' }
    Remove-Item Env:TAX_REBORN_OWNED_VOUCHER_PDF
    Close-App; Launch-App; Wait-Named '$2,435' 120 $false | Out-Null
    Wait-Named 'Form1040 line37 amount owed: $2,435' 120 $false | Out-Null
    $amount=Wait-Edit 'Entered check or money-order amount'; if([string]$amount.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::ValueProperty) -ne '1000.26') { throw 'Native voucher amount did not survive relaunch.' }
    Save-Screenshot 'windows-native-payment-voucher-reopened.png'
    $checks.Add('Native payment choice/custom cents/confirmation invalidation/system1040-V PDF and normal relaunch passed;2435 balance remained unchanged by1000.26 voucher.')
    $receipt.native_payment_voucher_changed_flow_passed=$true
    Click-Observed (Wait-Named 'Personal details for forms')
    $format=Wait-Control 'ComboBox' 'Mailing address format'; $format.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}{DOWN}{TAB}')
    Set-Owned-Edit 'City or town' 'Berlin'
    Set-Owned-Edit 'Foreign country name' 'Germany'
    Set-Owned-Edit 'Foreign province, state or county' 'Berlin'
    Set-Owned-Edit 'Foreign postal code' '10115'
    Scroll-Top; Wait-Named '$2,435' 120 $false | Out-Null
    Click-Observed (Wait-Named 'Balance due & payment voucher')
    $confirmation=Wait-Control 'CheckBox' 'I verified the paper payment amount and method' $true
    $toggle=$confirmation.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    if(([System.Windows.Automation.TogglePattern]$toggle).Current.ToggleState -ne [System.Windows.Automation.ToggleState]::Off) { throw 'Mailing address change did not invalidate paper-payment confirmation.' }
    $choice=Wait-Control 'ComboBox' 'Paper voucher amount'; $choice.SetFocus()
    [System.Windows.Forms.SendKeys]::SendWait('{HOME}{TAB}')
    Click-Observed (Wait-Control 'CheckBox' 'I verified the paper payment amount and method' $true)
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Click-Observed (Wait-Named 'Download official packet')
    $foreignPdf=Join-Path $OutputDir 'windows-native-foreign-address.pdf'; Save-Native-Export $foreignPdf
    $env:TAX_REBORN_OWNED_FOREIGN_PDF=$foreignPdf
    python -c "import os,sys;sys.path.insert(0,'tests');from pathlib import Path;import official_forms;from foreign_address_qa import CASES,verify_packet;print(verify_packet(Path(os.environ['TAX_REBORN_OWNED_FOREIGN_PDF']).read_bytes(),CASES[0],official_forms))"
    if($LASTEXITCODE -ne 0) { throw 'Native system-saved foreign address fields failed readback.' }
    Remove-Item Env:TAX_REBORN_OWNED_FOREIGN_PDF
    Close-App; Launch-App; Wait-Named '$2,435' 120 $false | Out-Null
    Click-Observed (Wait-Named 'Personal details for forms')
    foreach($pair in @(@('Foreign country name','Germany'),@('Foreign province, state or county','Berlin'),@('Foreign postal code','10115'),@('US state','IL'),@('US ZIP code','60000'))) {
        $field=Wait-Edit $pair[0]
        if([string]$field.GetCurrentPropertyValue([System.Windows.Automation.ValuePattern]::ValueProperty) -ne $pair[1]) { throw ('Reopened mailing address differs: '+$pair[0]) }
    }
    Save-Screenshot 'windows-native-foreign-address-reopened.png'
    $checks.Add('Native foreign format/country/province/postal edit invalidated paper confirmation; system1040/1040-V PDF separate rows and blank US fields verified, inputs and2435 balance survived relaunch.')
    $receipt.native_foreign_address_changed_flow_passed=$true
    $env:TAX_REBORN_OWNED_DATADIR=$DataDir
    python -c "import os,sys,json;sys.path.insert(0,'tests');import server,tax_engine;from payment_voucher_qa import cases,return_for;from foreign_address_qa import CASES,apply_address;d=apply_address(return_for(tax_engine,cases()[0]),CASES[0]);d['name']='Synthetic legacy foreign address';del d['filing_details']['mailing_address_type'];d['identity'].update(state='',zip='');store=server.Store(os.environ['TAX_REBORN_OWNED_DATADIR']);saved=store.save({'data':d});r=saved['result'];r['form_readiness']['missing_identity']=['State','ZIP code'];conn=store.connect();c=conn.__enter__();c.execute('UPDATE returns SET result=? WHERE id=?',(json.dumps(r),saved['id']));conn.__exit__(None,None,None)"
    if($LASTEXITCODE -ne 0) { throw 'Owned legacy address fixture failed' }
    Remove-Item Env:TAX_REBORN_OWNED_DATADIR
    Scroll-Top; Click-Observed (Wait-Named 'My returns'); Wait-Named 'Synthetic legacy foreign address' | Out-Null
    Click-Observed (Wait-Named 'Open'); Wait-Named '$2,435' 120 $false | Out-Null
    Click-Observed (Wait-Named 'Personal details for forms')
    $format=Wait-Control 'ComboBox' 'Mailing address format'
    Scroll-Top; Save-Screenshot 'windows-native-legacy-foreign-selector.png'
    Click-Observed (Wait-Named 'Save & export'); Click-Observed (Wait-Named 'Download official packet')
    $legacyPdf=Join-Path $OutputDir 'windows-native-legacy-foreign-address.pdf'; Save-Native-Export $legacyPdf
    $env:TAX_REBORN_OWNED_FOREIGN_PDF=$legacyPdf
    python -c "import os,sys;sys.path.insert(0,'tests');from pathlib import Path;import official_forms;from foreign_address_qa import CASES,verify_packet;print(verify_packet(Path(os.environ['TAX_REBORN_OWNED_FOREIGN_PDF']).read_bytes(),CASES[0],official_forms))"
    if($LASTEXITCODE -ne 0) { throw 'Native legacy address packet readback failed' }
    Remove-Item Env:TAX_REBORN_OWNED_FOREIGN_PDF
    $checks.Add('Native legacy foreign address without selector loaded with fresh readiness and system-exported1040/1040-V packet; stale cached state/ZIP gaps did not block current address.')
    $receipt.native_legacy_foreign_address_migration_passed=$true
    }
    # Exercise the new setup migration through the installed GUI, not a seeded
    # return or an injected worker command. Keep it separate from income tests.
    Scroll-Top; Click-Observed (Wait-Named 'My returns'); Click-Observed (Wait-Named '+ New return')
    Set-Owned-Edit 'Return name' 'Synthetic Windows22 filing-status migration'
    Click-Observed (Wait-Named 'Wages & salaries · W-2'); Click-Observed (Wait-Named '+ Add another W-2')
    Set-Owned-Edit 'Employer name' 'Synthetic Windows22 Employer'
    Set-Owned-Edit 'Box 1 · Wages, tips, other compensation' '60000'
    Wait-Named '$5,075' 120 $false | Out-Null
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Click-Observed (Wait-Named 'Documents'); Click-Observed (Wait-Named 'Open TaxML / binary .tax')
    Click-Observed (Wait-Named 'Try independently generated binary samples'); Click-Observed (Wait-Named 'Load filing-status sample')
    Click-Observed (Wait-Named 'Review filing-status setup')
    Wait-Named 'FS5 · Qualifying surviving spouse · unused' 120 $false | Out-Null
    Click-Observed (Wait-Named 'Confirm filing-status source and replacement'); Click-Observed (Wait-Named 'Apply reviewed filing status')
    Wait-Named '$2,946' 120 $false | Out-Null
    Scroll-Top; Click-Observed (Wait-Named 'Save'); Wait-Named 'Saved on this device' | Out-Null
    Close-App; Launch-App; Wait-Named '$2,946' 120 $false | Out-Null
    Click-Observed (Wait-Named 'Reviewed filing-status source history')
    Save-Screenshot 'windows-native-filing-status-cold-reopen.png'
    python scripts/verify_setup_native.py --data-dir $DataDir --output (Join-Path $OutputDir 'windows-native-filing-status-readback.json')
    if($LASTEXITCODE -ne 0) { throw 'Native filing-status source or calculation did not survive normal restart' }
    Click-Observed (Wait-Named 'View setup source'); Click-Observed (Wait-Named 'Inspect / correct source')
    Click-Observed (Wait-Named 'Review filing-status setup')
    Click-Observed (Wait-Named 'Confirm filing-status source and replacement'); Click-Observed (Wait-Named 'Apply reviewed filing status')
    Wait-Named 'This source already supplied return setup' 120 $false | Out-Null
    Save-Screenshot 'windows-native-filing-status-duplicate-refused.png'
    $receipt.native_filing_status_binary_review_passed=$true
    $checks.Add('Installed binary filing-status review changed Single to MFJ, real tax5075 to2946; saved source history survived cold restart, source/registry reopened and duplicate application was refused.')
    $receipt.native_gui_tested=$true; $receipt.all_passed=$true
} catch {
    $receipt.error=$_.Exception.Message
    $receipt.script_stack=$_.ScriptStackTrace
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
