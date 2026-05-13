$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$DataDir = Join-Path $RootDir "data"
$DownloadsDir = Join-Path $RootDir "downloads"
$LogsDir = Join-Path $RootDir "logs"
$EnvPath = Join-Path $RootDir ".env"
$EnvExamplePath = Join-Path $RootDir ".env.example"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Resolve-Tool {
    param(
        [Parameter(Mandatory = $true)][string[]]$Names,
        [Parameter(Mandatory = $true)][string]$InstallHint
    )

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    throw "$($Names -join ' or ') was not found. $InstallHint"
}

function Test-PortInUse {
    param([Parameter(Mandatory = $true)][int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return
    }

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Install-BackendDependencies {
    $python = Resolve-Tool -Names @("python", "py") -InstallHint "Install Python 3.12+ and add it to PATH."
    $requirements = Join-Path $BackendDir "requirements.txt"
    $stamp = Join-Path $VenvDir ".requirements.stamp"

    if (-not (Test-Path $VenvPython)) {
        Write-Host "Creating backend virtual environment..."
        if ((Split-Path -Leaf $python) -eq "py.exe") {
            & $python -3 -m venv $VenvDir
        }
        else {
            & $python -m venv $VenvDir
        }
    }

    $shouldInstall = -not (Test-Path $stamp)
    if (-not $shouldInstall) {
        $shouldInstall = (Get-Item $requirements).LastWriteTimeUtc -gt (Get-Item $stamp).LastWriteTimeUtc
    }

    if ($shouldInstall) {
        Write-Host "Installing backend dependencies..."
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r $requirements
        New-Item -ItemType File -Force -Path $stamp | Out-Null
    }
}

function Install-FrontendDependencies {
    $npm = Resolve-Tool -Names @("npm.cmd", "npm") -InstallHint "Install Node.js 20+ from https://nodejs.org/."
    $nodeModules = Join-Path $FrontendDir "node_modules"
    $packageLock = Join-Path $FrontendDir "package-lock.json"
    $shouldInstall = -not (Test-Path $nodeModules)

    if ((Test-Path $nodeModules) -and (Test-Path $packageLock)) {
        $shouldInstall = (Get-Item $packageLock).LastWriteTimeUtc -gt (Get-Item $nodeModules).LastWriteTimeUtc
    }

    if ($shouldInstall) {
        Write-Host "Installing frontend dependencies..."
        & $npm install --prefix $FrontendDir
    }

    return $npm
}

Set-Location $RootDir
New-Item -ItemType Directory -Force -Path $DataDir, $DownloadsDir, $LogsDir | Out-Null

if (-not (Test-Path $EnvPath)) {
    Copy-Item $EnvExamplePath $EnvPath
    Write-Host "Created .env from .env.example. Fill Google OAuth values before uploading to YouTube."
}

if (Test-PortInUse -Port 8000) {
    throw "Port 8000 is already in use. Stop the existing backend or change the port before starting."
}
if (Test-PortInUse -Port 5173) {
    throw "Port 5173 is already in use. Stop the existing frontend or change the port before starting."
}

Install-BackendDependencies
$npm = Install-FrontendDependencies

$env:APP_BASE_URL = "http://localhost:8000"
$env:FRONTEND_BASE_URL = "http://localhost:5173"
$env:DATABASE_URL = "sqlite:///../data/app.db"
$env:DOWNLOAD_DIR = "../downloads"

$backendLog = Join-Path $LogsDir "backend.log"
$backendErr = Join-Path $LogsDir "backend.err.log"
$frontendLog = Join-Path $LogsDir "frontend.log"
$frontendErr = Join-Path $LogsDir "frontend.err.log"

Remove-Item -LiteralPath $backendLog, $backendErr, $frontendLog, $frontendErr -Force -ErrorAction SilentlyContinue

Write-Host "Starting backend on http://localhost:8000"
$backend = Start-Process `
    -FilePath $VenvPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErr `
    -WindowStyle Hidden `
    -PassThru

Write-Host "Starting frontend on http://localhost:5173"
$frontend = Start-Process `
    -FilePath $npm `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErr `
    -WindowStyle Hidden `
    -PassThru

Write-Host ""
Write-Host "App is starting:"
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend health: http://localhost:8000/health"
Write-Host "  Logs: $LogsDir"
Write-Host ""
Write-Host "Keep this window open. Press Ctrl+C to stop both servers."

try {
    while ($true) {
        if ($backend.HasExited) {
            $tail = if (Test-Path $backendErr) { Get-Content $backendErr -Tail 40 | Out-String } else { "" }
            throw "Backend stopped unexpectedly. Check logs\backend.err.log.`n$tail"
        }

        if ($frontend.HasExited) {
            $tail = if (Test-Path $frontendErr) { Get-Content $frontendErr -Tail 40 | Out-String } else { "" }
            throw "Frontend stopped unexpectedly. Check logs\frontend.err.log.`n$tail"
        }

        Start-Sleep -Seconds 2
        $backend.Refresh()
        $frontend.Refresh()
    }
}
finally {
    Write-Host "Stopping servers..."
    Stop-ProcessTree -ProcessId $frontend.Id
    Stop-ProcessTree -ProcessId $backend.Id
}
