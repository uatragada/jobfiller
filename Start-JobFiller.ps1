$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$ScriptStartedAt = Get-Date

function Write-Output {
    param([Parameter(ValueFromRemainingArguments = $true)] [object[]]$InputObject)
    foreach ($item in $InputObject) {
        Microsoft.PowerShell.Utility\Write-Host $item
    }
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonCandidates = @(
    $env:JOBFILLER_PYTHON,
    (Join-Path $Root ".venv\Scripts\python.exe"),
    "python",
    "py",
    "python3"
)
$PnpmCandidate = $env:JOBFILLER_PNPM
$NpmCandidate = $env:JOBFILLER_NPM

$BackendHost = "127.0.0.1"
$BackendPortStart = 8001
if ($env:JOBFILLER_BACKEND_PORT) {
    $BackendPortStart = [int]$env:JOBFILLER_BACKEND_PORT
}
$BackendPortMaxScan = $BackendPortStart + 4
if ($env:JOBFILLER_BACKEND_PORT_MAX) {
    $BackendPortMaxScan = [int]$env:JOBFILLER_BACKEND_PORT_MAX
}
if ($BackendPortMaxScan -lt $BackendPortStart) {
    $BackendPortMaxScan = $BackendPortStart
}
$BackendPort = $null
$FrontendPort = 5173
if ($env:JOBFILLER_FRONTEND_PORT) {
    $FrontendPort = [int]$env:JOBFILLER_FRONTEND_PORT
}
$FrontendDir = Join-Path $Root "app\frontend"
$OutputsDir = Join-Path $Root "outputs"
$LogsDir = Join-Path $Root "artifacts"
$BackendLog = Join-Path $LogsDir "jobfiller-backend-current.log"
$BackendErrLog = Join-Path $LogsDir "jobfiller-backend-current.err.log"
$FrontendLog = Join-Path $LogsDir "jobfiller-frontend-current.log"
$FrontendErrLog = Join-Path $LogsDir "jobfiller-frontend-current.err.log"
$StartupLog = Join-Path $LogsDir "app-start.log"
$BackendScanAttempts = 2
$FrontendScanAttempts = 2
$ReuseExistingBackend = ([string]$env:JOBFILLER_REUSE_BACKEND) -match "^(1|true|yes)$"

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
}
if (-not (Test-Path $OutputsDir)) {
    New-Item -ItemType Directory -Path $OutputsDir | Out-Null
}

function Resolve-Executable {
    param(
        [string[]]$Candidates,
        [string]$Label
    )
    foreach ($candidate in $Candidates) {
        if (-not $candidate) { continue }
        if (Test-Path $candidate) {
            return $candidate
        }
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            if ($command.Source -and $command.Source.EndsWith(".ps1", [System.StringComparison]::OrdinalIgnoreCase)) {
                $cmdShim = [IO.Path]::ChangeExtension($command.Source, ".cmd")
                if (Test-Path $cmdShim) {
                    return $cmdShim
                }
            }
            return $command.Source
        }
    }
    throw "Missing $Label. Checked candidates: $($Candidates -join ', ')"
}

function Get-SafeString {
    param([object]$Value)
    if ($null -eq $Value) {
        return ""
    }
    return [string]$Value
}

function Get-PortListeners {
    param([int]$Port)
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    } catch {
        return @()
    }

    $listeners = @()
    foreach ($listenerPid in $connections) {
        $process = Get-Process -Id $listenerPid -ErrorAction SilentlyContinue
        $commandLine = $null
        if ($process) {
            try {
                $commandLine = (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $listenerPid" -ErrorAction SilentlyContinue).CommandLine
            } catch {
                $commandLine = $null
            }
        }

        $listeners += [PSCustomObject]@{
            Port = $Port
            OwningProcess = $listenerPid
            IsActive = [bool]$process
            ProcessName = if ($process) { $process.ProcessName } else { "unknown" }
            CommandLine = $commandLine
        }
    }

    return $listeners
}

function Get-ActivePortListenersByPort {
    param([int]$Port)
    return Get-PortListeners -Port $Port | Where-Object { $_.IsActive }
}

function Get-ListeningProcessIdsByPort {
    param([int]$Port)
    return Get-ActivePortListenersByPort -Port $Port | Select-Object -ExpandProperty OwningProcess -Unique
}

function Is-JobFillerBackendProcess {
    param($Listener)
    if (-not $Listener -or -not $Listener.IsActive) {
        return $false
    }

    $cmd = (Get-SafeString $Listener.CommandLine).ToLowerInvariant()
    return $cmd -like "*uvicorn*" -and $cmd -like "*app.backend.main:app*"
}

function Stop-ProcessesByPort {
    param([int]$Port)
    $listeners = Get-PortListeners -Port $Port
    if (-not $listeners) {
        Write-Output "No listening process found on port ${Port}."
        return
    }

    foreach ($listener in $listeners | Where-Object { $_.IsActive }) {
        try {
            Write-Output "Stopping process $($listener.OwningProcess) ($($listener.ProcessName)) on port ${Port}."
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
            if (Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue) {
                taskkill.exe /PID $listener.OwningProcess /F /T | Out-Null
            }
        } catch {
            Write-Output "Could not stop process $($listener.OwningProcess): $($_.Exception.Message)"
        }
    }

    # Wait briefly for port release, including stale listeners disappearing.
    for ($i = 0; $i -lt 10; $i++) {
        $remaining = Get-PortListeners -Port $Port | Where-Object { $_.IsActive }
        if (-not $remaining) {
            return
        }
        Start-Sleep -Milliseconds 250
    }
}

function Stop-VisibleJobFillerBackends {
    param([int]$StartPort = $BackendPortStart, [int]$MaxPort = $BackendPortMaxScan)
    for ($p = $StartPort; $p -le $MaxPort; $p++) {
        $listeners = Get-ActivePortListenersByPort -Port $p
        foreach ($listener in $listeners | Where-Object { Is-JobFillerBackendProcess $_ }) {
            try {
                Write-Output "Restart mode: stopping JobFiller backend process $($listener.OwningProcess) on port ${p}."
                Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
            } catch {
                Write-Output "Could not stop JobFiller backend process $($listener.OwningProcess) on port ${p}: $($_.Exception.Message)"
            }
        }
    }
}

function Test-BackendReady {
    param([int]$Port = $BackendPort, [string]$HostName = $BackendHost, [int]$MaxRetries = 30, [int]$DelayMs = 500)
    $url = "http://$HostName`:$Port/api/health"
    $jobsUrl = "http://$HostName`:$Port/api/jobs"
    $settingsUrl = "http://$HostName`:$Port/api/settings"
    $modelHealthUrl = "http://$HostName`:$Port/api/model-health"
    $sessionUrl = "http://$HostName`:$Port/api/session"
    for ($i = 0; $i -lt $MaxRetries; $i++) {
        try {
            $result = Invoke-RestMethod -Uri $url -TimeoutSec 2 -ErrorAction Stop
            if (-not ($result -and $result.status -eq "ok")) {
                Start-Sleep -Milliseconds $DelayMs
                continue
            }
            $capabilities = $result.capabilities
            if (-not ($capabilities -and $capabilities.question_answer_autoflush_fix -eq $true)) {
                Start-Sleep -Milliseconds $DelayMs
                continue
            }
            if (-not ($capabilities.local_mutation_token -eq $true)) {
                Start-Sleep -Milliseconds $DelayMs
                continue
            }
            if (-not ($capabilities.token_required_for_local_writes -eq $true)) {
                Start-Sleep -Milliseconds $DelayMs
                continue
            }
            $sessionResult = Invoke-RestMethod -Uri $sessionUrl -TimeoutSec 2 -ErrorAction Stop
            if (-not ($sessionResult -and $sessionResult.mutation_token)) {
                Start-Sleep -Milliseconds $DelayMs
                continue
            }
            $protectedHeaders = @{ "X-JobFiller-Token" = [string]$sessionResult.mutation_token }
            $jobsResult = Invoke-RestMethod -Uri $jobsUrl -Headers $protectedHeaders -TimeoutSec 2 -ErrorAction Stop
            if ($null -ne $jobsResult -and $jobsResult -is [System.Array]) {
                $settingsResult = Invoke-RestMethod -Uri $settingsUrl -Headers $protectedHeaders -TimeoutSec 2 -ErrorAction Stop
                $modelHealthResult = Invoke-RestMethod -Uri $modelHealthUrl -Headers $protectedHeaders -TimeoutSec 2 -ErrorAction Stop
                if ($settingsResult -and $modelHealthResult -and $modelHealthResult.provider -and $sessionResult.mutation_token) {
                    Write-Output "Backend is ready: $url"
                    return $true
                }
            }
        } catch {
            Start-Sleep -Milliseconds $DelayMs
        }
    }
    return $false
}

function Resolve-BackendPort {
    param([string]$HostName = $BackendHost, [int]$StartPort = $BackendPortStart, [int]$MaxPort = $BackendPortMaxScan)
    Write-Output "Checking for existing healthy backend on ports ${StartPort}-${MaxPort}."
    for ($p = $StartPort; $p -le $MaxPort; $p++) {
        $active = Get-ActivePortListenersByPort -Port $p
        if (-not $active) {
            continue
        }

        if ($ReuseExistingBackend -and (Test-BackendReady -Port $p -HostName $HostName -MaxRetries 2 -DelayMs 200)) {
            Write-Output "Backend already healthy on port ${p}; reusing it."
            return @{
                Port = $p
                ReuseExisting = $true
            }
        }

        $staleJobFillerListeners = @($active | Where-Object { Is-JobFillerBackendProcess $_ })
        if ($staleJobFillerListeners) {
            foreach ($listener in $staleJobFillerListeners) {
                try {
                    Write-Output "Stopping stale JobFiller backend process $($listener.OwningProcess) on port ${p}."
                    Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
                } catch {
                    Write-Output "Could not stop stale JobFiller backend process $($listener.OwningProcess) on port ${p}: $($_.Exception.Message)"
                }
            }
            for ($i = 0; $i -lt 10; $i++) {
                if (-not (Get-ActivePortListenersByPort -Port $p)) {
                    return @{
                        Port = $p
                        ReuseExisting = $false
                    }
                }
                Start-Sleep -Milliseconds 250
            }
        }

        Write-Output "Port ${p} is in use but not a ready JobFiller backend; skipping."
    }

    Write-Output "No existing healthy backend found."
    return @{ Port = $null; ReuseExisting = $false }
}

function Start-BackendWithRetry {
    param(
        [int]$Port,
        [string]$HostName = $BackendHost,
        [string]$Python,
        [string]$BackendLog,
        [string]$BackendErrLog,
        [string]$WorkingDir
    )

    Write-Output "Starting JobFiller backend on http://$HostName`:$Port/api"
    if (Test-Path $BackendLog) { Clear-Content -Path $BackendLog -ErrorAction SilentlyContinue }
    if (Test-Path $BackendErrLog) { Clear-Content -Path $BackendErrLog -ErrorAction SilentlyContinue }

    $backendProcess = Start-Process -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "app.backend.main:app", "--host", $HostName, "--port", $Port) `
        -RedirectStandardOutput $BackendLog `
        -RedirectStandardError $BackendErrLog `
        -WorkingDirectory $WorkingDir `
        -PassThru `
        -WindowStyle Hidden

    Write-Output "Backend PID: $($backendProcess.Id)"
    Start-Sleep -Milliseconds 500

    if ($backendProcess.HasExited) {
        $err = Get-Content -Path $BackendErrLog -Tail 80 -ErrorAction SilentlyContinue
        Write-Output "Backend process $($backendProcess.Id) exited before readiness check."
        if ($err) {
            Write-Output $err
        }
        return $null
    }

    if (Test-BackendReady -Port $Port -HostName $HostName) {
        Write-Output "Backend is healthy on ${HostName}:$Port."
        return $backendProcess
    }

    $isAddressInUse = $false
    $err = Get-Content -Path $BackendErrLog -Tail 80 -ErrorAction SilentlyContinue
    if ($err -and (($err -join "`n") -match "10048|Only one usage of each socket address")) {
        $isAddressInUse = $true
    }

    if ($isAddressInUse) {
        Write-Output "Backend on ${HostName}:$Port could not bind because port is still held."
    } else {
        Write-Output "Backend on ${HostName}:$Port did not become healthy."
        if ($err) {
            Write-Output $err
        }
    }

    if (-not $backendProcess.HasExited) {
        try {
            Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
            $backendProcess.WaitForExit(2000) | Out-Null
        } catch {}
    }

    return $null
}

function Get-PackageManagerName {
    param([string]$Executable)
    $fileName = [IO.Path]::GetFileName($Executable).ToLowerInvariant()
    if ($fileName -like "*pnpm*") { return "pnpm" }
    return "npm"
}

function Invoke-OrExit {
    param([string]$Command, [string[]]$CommandArgs)
    & $Command @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command $($CommandArgs -join ' ')"
    }
}

function Ensure-PythonEnvironment {
    param([string]$BootstrapPython)
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Output "Creating local Python virtual environment in .venv..."
        Invoke-OrExit -Command $BootstrapPython -CommandArgs @("-m", "venv", (Join-Path $Root ".venv"))
        if (-not (Test-Path $venvPython)) {
            throw "Virtual environment creation did not produce $venvPython. Check that Python venv support is installed."
        }
    }
    $python = $venvPython
    $requirements = Join-Path $Root "requirements.txt"
    $depsOk = $false
    try {
        & $python -c "import fastapi, sqlalchemy, uvicorn, pydantic" | Out-Null
        $depsOk = ($LASTEXITCODE -eq 0)
    } catch {
        $depsOk = $false
    }
    if (-not $depsOk) {
        Write-Output "Installing backend dependencies from requirements.txt..."
        Invoke-OrExit -Command $python -CommandArgs @("-m", "pip", "install", "-r", $requirements)
    }
    return $python
}

function Test-FrontendReady {
    param([int]$BackendPort, [string]$HostName = $BackendHost, [int]$MaxRetries = 25, [int]$DelayMs = 500)
    $url = "http://127.0.0.1:$($FrontendPort)"
    $jobsUrl = "http://$HostName`:$BackendPort/api/jobs?sort=newest&remote_first=true"
    $sessionUrl = "http://$HostName`:$BackendPort/api/session"

    for ($i = 0; $i -lt $MaxRetries; $i++) {
        try {
            $status = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($status.StatusCode -ne 200) {
                Start-Sleep -Milliseconds $DelayMs
                continue
            }
            $session = Invoke-RestMethod -Uri $sessionUrl -TimeoutSec 2 -ErrorAction Stop
            $protectedHeaders = @{ "X-JobFiller-Token" = [string]$session.mutation_token }
            $jobs = Invoke-RestMethod -Uri $jobsUrl -Headers $protectedHeaders -TimeoutSec 2 -ErrorAction Stop
            if ($null -ne $jobs -and $jobs -is [System.Array]) {
                Write-Output "Frontend is ready: $url"
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds $DelayMs
        }
    }
    return $false
}

function Ensure-FrontendPortFree {
    param([int]$Port)
    $listeners = Get-ActivePortListenersByPort -Port $Port
    if (-not $listeners) {
        return
    }
    Write-Output "Frontend port ${Port} is already in use; clearing before startup."
    foreach ($listener in $listeners) {
        $cmd = (Get-SafeString $listener.CommandLine).ToLowerInvariant()
        if ($cmd -notlike "*vite*" -or $cmd -notlike "*app\frontend*") {
            throw "Frontend port ${Port} is used by another process. Stop PID $($listener.OwningProcess) or set a different frontend port before starting JobFiller."
        }
        try {
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    Start-Sleep -Milliseconds 500
    if (Get-ActivePortListenersByPort -Port $Port) {
        Write-Output "Could not clear frontend port ${Port}. Please stop the process(es) using it before restarting."
        throw "Frontend port ${Port} is blocked."
    }
}

function Start-JobFillerFrontend {
    param([string]$PackageManager, [string]$BackendApiBase)
    Ensure-FrontendPortFree -Port $FrontendPort

    Write-Output "Starting dashboard on http://127.0.0.1:$FrontendPort with VITE_API_BASE=${BackendApiBase}"
    Push-Location $FrontendDir
    try {
        if (-not (Test-Path "node_modules")) {
            Write-Output "No node_modules found. Running $PackageManager install..."
            $pmNameForInstall = Get-PackageManagerName -Executable $PackageManager
            if ($pmNameForInstall -eq "pnpm" -and (Test-Path "pnpm-lock.yaml")) {
                Invoke-OrExit -Command $PackageManager -CommandArgs @("install", "--frozen-lockfile")
            } elseif ($pmNameForInstall -eq "npm" -and (Test-Path "package-lock.json")) {
                Invoke-OrExit -Command $PackageManager -CommandArgs @("ci")
            } else {
                Invoke-OrExit -Command $PackageManager -CommandArgs @("install")
            }
        }

        $pmName = Get-PackageManagerName -Executable $PackageManager
        if ($pmName -eq "pnpm") {
            $frontendArgs = @("dev", "--host", "127.0.0.1", "--port", "$FrontendPort")
        } else {
            $frontendArgs = @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort")
        }

        $oldApiBase = if (Test-Path Env:VITE_API_BASE) { $env:VITE_API_BASE } else { $null }
        $env:VITE_API_BASE = $BackendApiBase
        Start-Process -FilePath $PackageManager `
            -ArgumentList $frontendArgs `
            -WorkingDirectory $FrontendDir `
            -RedirectStandardOutput $FrontendLog `
            -RedirectStandardError $FrontendErrLog `
            -PassThru `
            -WindowStyle Hidden | Out-Null

        $backendUri = $BackendApiBase -replace "/api$", ""
        $uri = [System.Uri]$backendUri
        $backendHost = $uri.Host
        $backendPort = $uri.Port

        if (Test-FrontendReady -BackendPort $backendPort -HostName $backendHost) {
            Write-Output "Frontend is healthy."
            Write-Output "Dashboard: http://127.0.0.1:$FrontendPort"
            Write-Output "Backend API base: $BackendApiBase"
            Write-Output "Backend logs: $BackendLog"
            Write-Output "Frontend logs: $FrontendLog"
            return
        }

        Write-Output "Frontend did not become ready quickly; check $FrontendErrLog and $FrontendLog."
        throw "Frontend failed readiness probe."
    } finally {
        if ($null -eq $oldApiBase) {
            Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue
        } else {
            $env:VITE_API_BASE = $oldApiBase
        }
        Pop-Location
    }
}

function Write-RuntimeConfig {
    param([string]$BackendApiBase)
    $runtimePath = Join-Path $OutputsDir "jobfiller-runtime.json"
    $mutationToken = ""
    try {
        $session = Invoke-RestMethod -Uri "${BackendApiBase}/session" -TimeoutSec 2 -ErrorAction Stop
        $mutationToken = [string]$session.mutation_token
    } catch {
        Write-Output "Could not read local mutation token for runtime config: $($_.Exception.Message)"
    }
    $payload = [PSCustomObject]@{
        api_base = $BackendApiBase
        frontend_url = "http://127.0.0.1:$FrontendPort"
        mutation_token = $mutationToken
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    $payload | ConvertTo-Json -Depth 4 | Set-Content -Path $runtimePath -Encoding UTF8
    Write-Output "Runtime config for MCP clients: $runtimePath"
}

try {
    Start-Transcript -Path $StartupLog -Append -Force | Out-Null

    $python = Resolve-Executable -Candidates $PythonCandidates -Label "Python"
    $python = Ensure-PythonEnvironment -BootstrapPython $python
    $packageManager = Resolve-Executable -Candidates @(
        $NpmCandidate,
        $PnpmCandidate,
        "npm",
        "pnpm"
    ) -Label "Node package manager (npm or pnpm)"

    if (-not $ReuseExistingBackend) {
        Stop-VisibleJobFillerBackends -StartPort $BackendPortStart -MaxPort $BackendPortMaxScan
    }

    $backendSelection = Resolve-BackendPort -HostName $BackendHost -StartPort $BackendPortStart -MaxPort $BackendPortMaxScan
    $BackendPort = $backendSelection.Port
    $backendWasReused = [bool]$backendSelection.ReuseExisting
    $backendAlreadyReady = $backendWasReused
    $backendProcess = $null

    if (-not $backendAlreadyReady) {
        Write-Output "No healthy backend detected. Scanning ports ${BackendPortStart}-${BackendPortMaxScan}."
        for ($scanAttempt = 1; $scanAttempt -le $BackendScanAttempts; $scanAttempt++) {
            if ($scanAttempt -gt 1) {
                Write-Output "Backend start retry ${scanAttempt} of $BackendScanAttempts."
            }

            for ($candidatePort = $BackendPortStart; $candidatePort -le $BackendPortMaxScan; $candidatePort++) {
                $activeListeners = Get-ActivePortListenersByPort -Port $candidatePort
                if ($activeListeners) {
                    Write-Output "Port ${candidatePort} has active listener(s); skipping."
                    continue
                }

                $backendStartResult = @(Start-BackendWithRetry `
                    -Port $candidatePort `
                    -HostName $BackendHost `
                    -Python $python `
                    -BackendLog $BackendLog `
                    -BackendErrLog $BackendErrLog `
                    -WorkingDir $Root)
                $backendProcess = $backendStartResult |
                    Where-Object { $_ -is [System.Diagnostics.Process] } |
                    Select-Object -Last 1

                if ($backendProcess) {
                    $BackendPort = $candidatePort
                    $backendAlreadyReady = $true
                    $backendWasReused = $false
                    break
                }
            }

            if ($backendAlreadyReady) {
                break
            }

            Write-Output "Backend start attempt failed on all candidate ports; clearing known JobFiller backend processes and retrying."
            Stop-VisibleJobFillerBackends -StartPort $BackendPortStart -MaxPort $BackendPortMaxScan
        }

        if (-not $backendAlreadyReady) {
            throw "Could not start a backend. Ports ${BackendPortStart}-${BackendPortMaxScan} were unavailable or failed."
        }
    } else {
        Write-Output "Backend is already healthy on selected port ${BackendPort}."
    }

    $backendApiBase = "http://$BackendHost`:$BackendPort/api"

    $backendMessage = if ($backendWasReused) { "reused" } else { "started" }
    Write-Output "Backend is available on ${backendApiBase} (${backendMessage})."
    Write-RuntimeConfig -BackendApiBase $backendApiBase

    $frontendStarted = $false
    for ($frontendAttempt = 1; $frontendAttempt -le $FrontendScanAttempts; $frontendAttempt++) {
        try {
            Start-JobFillerFrontend -PackageManager $packageManager -BackendApiBase $backendApiBase
            $frontendStarted = $true
            break
        } catch {
            Write-Output "Frontend start attempt ${frontendAttempt} failed: $($_.Exception.Message)"
            if ($frontendAttempt -lt $FrontendScanAttempts) {
                Write-Output "Retrying frontend startup..."
                Stop-ProcessesByPort -Port $FrontendPort
                Start-Sleep -Milliseconds 500
            }
        }
    }

    if (-not $frontendStarted) {
        throw "Failed to start frontend after $FrontendScanAttempts attempts."
    }

    $elapsedSeconds = [math]::Round(((Get-Date) - $ScriptStartedAt).TotalSeconds, 1)
    Write-Output "Startup completed in ${elapsedSeconds}s."
} finally {
    Stop-Transcript | Out-Null
}
