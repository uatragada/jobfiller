param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [int]$TimeoutSeconds = 60,
    [string]$ButtonName = "Upload resume button. Only, DOC, DOCX, PDF formats are supported. Max file size is (2 MB).",
    [string]$LogPath = (Join-Path $PSScriptRoot "..\artifacts\linkedin-resume-upload.log")
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)

    $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $Message
    Write-Host $line

    if ($LogPath) {
        $logDirectory = Split-Path -Parent $LogPath
        if ($logDirectory -and -not (Test-Path -LiteralPath $logDirectory)) {
            New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
        }
        Add-Content -LiteralPath $LogPath -Value $line
    }
}

function Get-PatternOrNull {
    param(
        [System.Windows.Automation.AutomationElement]$Element,
        [System.Windows.Automation.AutomationPattern]$Pattern
    )

    try {
        return $Element.GetCurrentPattern($Pattern)
    }
    catch {
        return $null
    }
}

function Invoke-ElementClick {
    param([System.Windows.Automation.AutomationElement]$Element)

    $invokePattern = Get-PatternOrNull -Element $Element -Pattern ([System.Windows.Automation.InvokePattern]::Pattern)
    if ($invokePattern) {
        $invokePattern.Invoke()
        return
    }

    $rect = $Element.Current.BoundingRectangle
    if ($rect.Width -le 0 -or $rect.Height -le 0) {
        throw "Element has no clickable bounds."
    }

    Add-Type -AssemblyName System.Windows.Forms
    $x = [int]($rect.X + ($rect.Width / 2))
    $y = [int]($rect.Y + ($rect.Height / 2))
    [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($x, $y)

    Add-Type @'
using System;
using System.Runtime.InteropServices;
public class ResumeUploadMouseClicker {
  [DllImport("user32.dll", SetLastError=true)]
  public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
  public const uint LEFTDOWN = 0x0002;
  public const uint LEFTUP = 0x0004;
}
'@ -ErrorAction SilentlyContinue

    [ResumeUploadMouseClicker]::mouse_event([ResumeUploadMouseClicker]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 100
    [ResumeUploadMouseClicker]::mouse_event([ResumeUploadMouseClicker]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
}

function Find-UploadButton {
    param([string]$ExpectedName)

    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $trueCondition = [System.Windows.Automation.Condition]::TrueCondition
    $elements = @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $trueCondition))

    $buttons = $elements | Where-Object {
        try {
            $_.Current.ControlType.ProgrammaticName -eq "ControlType.Button" -and
                $_.Current.Name -eq $ExpectedName -and
                $_.Current.IsEnabled -and
                -not $_.Current.IsOffscreen
        }
        catch {
            $false
        }
    }

    return @($buttons) | Select-Object -First 1
}

try {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes

    $resolvedFilePath = (Resolve-Path -LiteralPath $FilePath).Path
    if (-not (Test-Path -LiteralPath $resolvedFilePath -PathType Leaf)) {
        throw "File does not exist: $resolvedFilePath"
    }

    $dialogHelper = Join-Path $PSScriptRoot "Upload-ResumeFileDialog.ps1"
    if (-not (Test-Path -LiteralPath $dialogHelper -PathType Leaf)) {
        throw "Missing dialog helper: $dialogHelper"
    }

    Write-Status "Starting resume upload helper for: $resolvedFilePath"
    $dialogLogPath = [System.IO.Path]::ChangeExtension($LogPath, ".dialog.log")
    $dialogProcess = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $dialogHelper,
        "-FilePath", $resolvedFilePath,
        "-TimeoutSeconds", $TimeoutSeconds,
        "-LogPath", $dialogLogPath
    )

    Start-Sleep -Milliseconds 400
    $deadline = (Get-Date).AddSeconds([Math]::Max(5, [Math]::Min($TimeoutSeconds, 20)))
    $uploadButton = $null

    while ((Get-Date) -lt $deadline -and -not $uploadButton) {
        $uploadButton = Find-UploadButton -ExpectedName $ButtonName
        if (-not $uploadButton) {
            Start-Sleep -Milliseconds 250
        }
    }

    if (-not $uploadButton) {
        throw "Could not find LinkedIn's Upload resume button on the current desktop."
    }

    Write-Status "Clicking LinkedIn Upload resume button."
    Invoke-ElementClick -Element $uploadButton

    Write-Status "Waiting for picker helper to finish."
    try {
        Wait-Process -Id $dialogProcess.Id -Timeout $TimeoutSeconds -ErrorAction Stop
    }
    catch {
        Stop-Process -Id $dialogProcess.Id -Force -ErrorAction SilentlyContinue
        throw "Dialog helper timed out."
    }

    if ($dialogProcess.ExitCode -ne 0) {
        throw "Dialog helper failed with exit code $($dialogProcess.ExitCode). See $dialogLogPath"
    }

    Write-Status "Upload handoff completed. Verify the selected resume on LinkedIn."
    exit 0
}
catch {
    Write-Status "Failed: $($_.Exception.Message)"
    exit 1
}
