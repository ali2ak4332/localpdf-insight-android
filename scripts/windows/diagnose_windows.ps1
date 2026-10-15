$ErrorActionPreference = "Continue"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Repo
$Log = Join-Path $Repo "LocalPDF_Diagnostic.txt"
"LocalPDF Insight diagnostic - $(Get-Date -Format o)" | Set-Content -Encoding UTF8 $Log
"Project: $Repo" | Add-Content -Encoding UTF8 $Log
"PowerShell: $($PSVersionTable.PSVersion)" | Add-Content -Encoding UTF8 $Log
"Windows: $([Environment]::OSVersion.VersionString)" | Add-Content -Encoding UTF8 $Log
"pyproject exists: $(Test-Path 'pyproject.toml')" | Add-Content -Encoding UTF8 $Log
"venv python exists: $(Test-Path '.venv\Scripts\python.exe')" | Add-Content -Encoding UTF8 $Log

if (Test-Path ".venv\Scripts\python.exe") {
  "`n--- Python ---" | Add-Content -Encoding UTF8 $Log
  & ".venv\Scripts\python.exe" --version 2>&1 | Out-String | Add-Content -Encoding UTF8 $Log
  & ".venv\Scripts\python.exe" -c "import sys, fitz, PIL, PySide6, localpdf_insight; print(sys.executable); print('imports OK')" 2>&1 | Out-String | Add-Content -Encoding UTF8 $Log
  "`n--- App import ---" | Add-Content -Encoding UTF8 $Log
  & ".venv\Scripts\python.exe" -c "import localpdf_insight.ui; print('UI import OK')" 2>&1 | Out-String | Add-Content -Encoding UTF8 $Log
  "`n--- GUI startup check ---" | Add-Content -Encoding UTF8 $Log
  $oldPlatform = $env:QT_QPA_PLATFORM
  $oldAppData = $env:LOCALAPPDATA
  $diagnosticState = Join-Path ([IO.Path]::GetTempPath()) ("LocalPDF-Diagnostic-" + [Guid]::NewGuid())
  try {
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:LOCALAPPDATA = $diagnosticState
    & ".venv\Scripts\python.exe" -c "from localpdf_insight.ui import QApplication, MainWindow; app=QApplication([]); win=MainWindow(); print('GUI creation OK'); win.close()" 2>&1 | Out-String | Add-Content -Encoding UTF8 $Log
  } finally {
    $env:QT_QPA_PLATFORM = $oldPlatform
    $env:LOCALAPPDATA = $oldAppData
    if (Test-Path $diagnosticState) { Remove-Item -LiteralPath $diagnosticState -Recurse -Force }
  }
}
if (Test-Path "LocalPDF_Run.log") {
  "`n--- Last launch ---" | Add-Content -Encoding UTF8 $Log
  Get-Content -Encoding UTF8 "LocalPDF_Run.log" -Tail 80 | Add-Content -Encoding UTF8 $Log
}
"`n--- Ollama ---" | Add-Content -Encoding UTF8 $Log
Get-Command ollama.exe -ErrorAction SilentlyContinue | Format-List * | Out-String | Add-Content -Encoding UTF8 $Log
try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | ConvertTo-Json -Depth 4 | Add-Content -Encoding UTF8 $Log } catch { $_ | Out-String | Add-Content -Encoding UTF8 $Log }
Get-Content -Encoding UTF8 $Log
