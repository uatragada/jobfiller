param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$FilePath,
    [int]$TimeoutSeconds = 90,
    [string]$LogPath = (Join-Path $PSScriptRoot "..\artifacts\upload-helper.log")
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

function New-ControlTypeCondition {
    param([System.Windows.Automation.ControlType]$ControlType)

    return New-Object System.Windows.Automation.PropertyCondition -ArgumentList `
        ([System.Windows.Automation.AutomationElement]::ControlTypeProperty), `
        $ControlType
}

function Find-DescendantsByType {
    param(
        [System.Windows.Automation.AutomationElement]$Element,
        [System.Windows.Automation.ControlType]$ControlType
    )

    $condition = New-ControlTypeCondition -ControlType $ControlType
    return @($Element.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition))
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

function Get-ElementSummary {
    param([System.Windows.Automation.AutomationElement]$Element)

    try {
        return "name='$($Element.Current.Name)' id='$($Element.Current.AutomationId)' type='$($Element.Current.ControlType.ProgrammaticName)'"
    }
    catch {
        return "<unavailable>"
    }
}

function Get-FileNameFieldScore {
    param([System.Windows.Automation.AutomationElement]$Element)

    $score = 0
    $name = ""
    $automationId = ""
    $controlType = ""

    try {
        $name = [string]$Element.Current.Name
        $automationId = [string]$Element.Current.AutomationId
        $controlType = [string]$Element.Current.ControlType.ProgrammaticName

        if ($Element.Current.IsEnabled) { $score += 10 }
        if (-not $Element.Current.IsOffscreen) { $score += 5 }
    }
    catch {
        return -1
    }

    if ($automationId -eq "1148") { $score += 100 }
    if ($name -match "(?i)file\s*name") { $score += 80 }
    if ($controlType -match "Edit") { $score += 20 }
    if ($controlType -match "ComboBox") { $score += 10 }
    if ($name -match "(?i)search") { $score -= 50 }
    if ($automationId -match "(?i)search") { $score -= 50 }

    return $score
}

function Set-FileNameField {
    param(
        [System.Windows.Automation.AutomationElement]$Dialog,
        [string]$ResolvedFilePath
    )

    $fields = @()
    $fields += Find-DescendantsByType -Element $Dialog -ControlType ([System.Windows.Automation.ControlType]::Edit)
    $fields += Find-DescendantsByType -Element $Dialog -ControlType ([System.Windows.Automation.ControlType]::ComboBox)

    if ($fields.Count -eq 0) {
        Write-Status "No editable filename field found in dialog."
        return $false
    }

    $rankedFields = $fields | Sort-Object -Descending -Property @{ Expression = { Get-FileNameFieldScore -Element $_ } }

    foreach ($field in $rankedFields) {
        $score = Get-FileNameFieldScore -Element $field
        if ($score -lt 0) {
            continue
        }

        $valuePattern = Get-PatternOrNull -Element $field -Pattern ([System.Windows.Automation.ValuePattern]::Pattern)
        if (-not $valuePattern) {
            continue
        }

        try {
            $field.SetFocus()
        }
        catch {
            # Some fields refuse focus but still accept ValuePattern.SetValue.
        }

        try {
            Write-Status "Setting filename field ($score): $(Get-ElementSummary -Element $field)"
            $valuePattern.SetValue($ResolvedFilePath)
            return $true
        }
        catch {
            Write-Status "Could not set field $(Get-ElementSummary -Element $field): $($_.Exception.Message)"
        }
    }

    return $false
}

function Get-ButtonScore {
    param([System.Windows.Automation.AutomationElement]$Element)

    try {
        if (-not $Element.Current.IsEnabled) {
            return -1
        }

        $name = ([string]$Element.Current.Name -replace "&", "").Trim()
        $automationId = [string]$Element.Current.AutomationId
    }
    catch {
        return -1
    }

    $score = 0
    if ($automationId -eq "1") { $score += 100 }
    if ($name -match "^(Open|Choose|Upload|OK)$") { $score += 80 }
    if ($name -match "Cancel") { $score -= 100 }
    return $score
}

function Invoke-OpenButton {
    param([System.Windows.Automation.AutomationElement]$Dialog)

    $buttons = Find-DescendantsByType -Element $Dialog -ControlType ([System.Windows.Automation.ControlType]::Button)
    $rankedButtons = $buttons | Sort-Object -Descending -Property @{ Expression = { Get-ButtonScore -Element $_ } }

    foreach ($button in $rankedButtons) {
        $score = Get-ButtonScore -Element $button
        if ($score -le 0) {
            continue
        }

        $invokePattern = Get-PatternOrNull -Element $button -Pattern ([System.Windows.Automation.InvokePattern]::Pattern)
        if (-not $invokePattern) {
            continue
        }

        try {
            Write-Status "Invoking upload button ($score): $(Get-ElementSummary -Element $button)"
            $invokePattern.Invoke()
            return $true
        }
        catch {
            Write-Status "Could not invoke button $(Get-ElementSummary -Element $button): $($_.Exception.Message)"
        }
    }

    return $false
}

function Get-CandidateFileDialogs {
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $windowCondition = New-ControlTypeCondition -ControlType ([System.Windows.Automation.ControlType]::Window)
    $windows = @($root.FindAll([System.Windows.Automation.TreeScope]::Children, $windowCondition))

    # Chrome can expose its native file picker as a child window under the
    # browser root instead of as a desktop-level child. Include descendant
    # windows so off-monitor or grouped Chrome windows are still handled.
    foreach ($topLevelWindow in @($windows)) {
        try {
            $windows += @($topLevelWindow.FindAll([System.Windows.Automation.TreeScope]::Descendants, $windowCondition))
        }
        catch {
            Write-Status "Could not inspect child windows for $(Get-ElementSummary -Element $topLevelWindow): $($_.Exception.Message)"
        }
    }

    foreach ($window in $windows) {
        try {
            $name = [string]$window.Current.Name
            $className = [string]$window.Current.ClassName
            $isEnabled = [bool]$window.Current.IsEnabled
        }
        catch {
            continue
        }

        $looksLikeDialog = $className -eq "#32770" -or $name -match "(?i)(open|choose file|file upload|upload)"
        if (-not $looksLikeDialog -or -not $isEnabled) {
            continue
        }

        $fields = @()
        $fields += Find-DescendantsByType -Element $window -ControlType ([System.Windows.Automation.ControlType]::Edit)
        $fields += Find-DescendantsByType -Element $window -ControlType ([System.Windows.Automation.ControlType]::ComboBox)
        $buttons = Find-DescendantsByType -Element $window -ControlType ([System.Windows.Automation.ControlType]::Button)

        if ($fields.Count -gt 0 -and $buttons.Count -gt 0) {
            $window
        }
    }
}

try {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes

    if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
        throw "File does not exist: $FilePath"
    }
    $resolvedFilePath = (Resolve-Path -LiteralPath $FilePath).Path

    Write-Status "Waiting up to $TimeoutSeconds seconds for a Windows file picker."
    Write-Status "Target file: $resolvedFilePath"

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $dialogs = @(Get-CandidateFileDialogs)

        foreach ($dialog in $dialogs) {
            Write-Status "Found candidate dialog: $(Get-ElementSummary -Element $dialog)"

            try {
                $dialog.SetFocus()
            }
            catch {
                Write-Status "Could not focus dialog: $($_.Exception.Message)"
            }

            if (-not (Set-FileNameField -Dialog $dialog -ResolvedFilePath $resolvedFilePath)) {
                continue
            }

            Start-Sleep -Milliseconds 250

            if (Invoke-OpenButton -Dialog $dialog) {
                Write-Status "Submitted file path to the picker."
                exit 0
            }
        }

        Start-Sleep -Milliseconds 250
    }

    Write-Status "Timed out before a usable file picker appeared."
    exit 2
}
catch {
    Write-Status "Failed: $($_.Exception.Message)"
    exit 1
}
