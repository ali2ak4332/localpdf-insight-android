param([switch]$SkipAI, [switch]$NoLaunch, [switch]$Web)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Repo
$Model = if ($env:LOCALPDF_MODEL) { $env:LOCALPDF_MODEL } else { "gemma3:4b" }
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"

function Step([string]$Text) { Write-Host "`n== $Text ==" -ForegroundColor Cyan }
function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user;$env:Path"
}
function Test-Python([string]$Executable, [string[]]$Arguments = @()) {
    try {
        & $Executable @Arguments -c "import sys, struct; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) and struct.calcsize('P') == 8 else 1)" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{Executable = $Executable; Arguments = @($Arguments)}
        }
    } catch {}
    return $null
}
function Find-Python {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($version in @("-3.12", "-3.13", "-3.11")) {
            $candidate = Test-Python $launcher.Source @($version)
            if ($candidate) { return $candidate }
        }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike "*\Microsoft\WindowsApps\*") {
        $candidate = Test-Python $command.Source
        if ($candidate) { return $candidate }
    }
    foreach ($version in @("312", "313", "311")) {
        foreach ($root in @((Join-Path $env:LOCALAPPDATA "Programs\Python"), $env:ProgramFiles)) {
            $path = Join-Path $root "Python$version\python.exe"
            if (Test-Path $path) {
                $candidate = Test-Python $path
                if ($candidate) { return $candidate }
            }
        }
    }
    return $null
}
function Find-Ollama {
    $command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $path = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $path) { return (Get-Item $path).FullName }
    return $null
}

if (-not (Test-Path (Join-Path $Repo "pyproject.toml"))) {
    throw "Project files are incomplete. Extract the entire ZIP before running setup."
}
Write-Host "LocalPDF Insight 0.2.0 - setup" -ForegroundColor White
Write-Host "Project: $Repo"
Step "Checking Python"
$existing = if (Test-Path $VenvPython) { Test-Python $VenvPython } else { $null }
if (-not $existing) {
    $pythonCmd = Find-Python
    if (-not $pythonCmd) {
        Step "Installing 64-bit Python 3.12"
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $winget) { throw "Install 64-bit Python 3.12 from python.org, then rerun setup. Python 3.11-3.13 is supported." }
        & $winget.Source install --id Python.Python.3.12 --exact --architecture x64 --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -ne 0) { throw "Python installation failed with code $LASTEXITCODE." }
        Refresh-Path
        $pythonCmd = Find-Python
        if (-not $pythonCmd) { throw "Python is not visible yet. Close this window and rerun setup." }
    }
    if (Test-Path (Join-Path $Repo ".venv")) {
        $backup = ".venv.backup-" + (Get-Date -Format "yyyyMMdd-HHmmss-fff")
        Rename-Item -LiteralPath (Join-Path $Repo ".venv") -NewName $backup
        Write-Host "Preserved the old Python environment as $backup."
    }
    Step "Creating Python environment"
    $executable = $pythonCmd.Executable
    $arguments = @($pythonCmd.Arguments)
    & $executable @arguments -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv." }
}
Step "Installing LocalPDF Insight"
$extra = if ($Web) { ".[web]" } else { ".[desktop]" }
& $VenvPython -m pip install --disable-pip-version-check -c requirements-validation.lock -e $extra
if ($LASTEXITCODE -ne 0) { throw "Application dependency installation failed. Check the internet connection, then rerun setup." }
$importCheck = if ($Web) { "import fitz, PIL, flask, waitress, localpdf_insight.web" } else { "import fitz, PIL, PySide6, localpdf_insight.ui" }
& $VenvPython -c $importCheck
if ($LASTEXITCODE -ne 0) { throw "Application import failed. Run DIAGNOSE_WINDOWS.bat for details." }

if (-not $SkipAI) {
    try {
        $ollamaPath = Find-Ollama
        if (-not $ollamaPath) {
            Step "Installing Ollama for local AI"
            Invoke-Expression (Invoke-RestMethod -Uri "https://ollama.com/install.ps1")
            Refresh-Path
            $ollamaPath = Find-Ollama
            if (-not $ollamaPath) { throw "Ollama was not found after installation. Install it from ollama.com/download/windows." }
        }
        Step "Starting Ollama"
        $ready = $false
        try { $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2; $ready = $true } catch {}
        if (-not $ready) {
            Start-Process -FilePath $ollamaPath -ArgumentList "serve" -WindowStyle Hidden
            for ($i = 0; $i -lt 20; $i++) {
                Start-Sleep -Milliseconds 500
                try { $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2; $ready = $true; break } catch {}
            }
        }
        if (-not $ready) { throw "Ollama did not become ready on 127.0.0.1:11434." }
        $modelTag = if ($Model.Contains(":")) { $Model } else { "${Model}:latest" }
        if (@($tags.models | Where-Object { $_.name -eq $modelTag }).Count -eq 0) {
            Step "Downloading $Model (several GB on first setup)"
            & $ollamaPath pull $Model
            if ($LASTEXITCODE -ne 0) { throw "Ollama model download failed." }
        } else { Write-Host "Local model $modelTag is already installed." }
    } catch {
        Write-Warning "Local AI setup is incomplete: $($_.Exception.Message)"
        Write-Host "The PDF reader will still open. Reading, indexing and text/data export work without AI."
        Write-Host "Rerun this setup later to finish AI installation."
    }
} else { Write-Host "Skipping AI setup. PDF reading, indexing and text/data export are available." }
if (-not $NoLaunch) {
    Step "Launching LocalPDF Insight"
    if ($Web) {
        if (-not $env:LOCALPDF_MODEL -and -not $SkipAI) { $env:LOCALPDF_MODEL = $Model }
        Write-Host "Open http://127.0.0.1:8765 in your browser. Keep this window open."
        & $VenvPython -m localpdf_insight.web
    } else {
        & $VenvPython -m localpdf_insight
    }
    if ($LASTEXITCODE -ne 0) { throw "LocalPDF Insight exited with code $LASTEXITCODE. Run DIAGNOSE_WINDOWS.bat." }
}
