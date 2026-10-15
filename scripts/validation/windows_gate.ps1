param([string]$Output = "external-windows-results", [switch]$RunLive)
$ErrorActionPreference = "Stop"
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw "This gate requires a real Windows installation or VM." }
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Repo
New-Item -ItemType Directory -Force $Output | Out-Null
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE) { throw "Python 3.12 environment creation failed" }
}
& $Python -m pip install -c requirements-validation.lock -e ".[web,test,desktop]"
if ($LASTEXITCODE) { throw "Clean dependency installation failed" }
$env:PYTHONUTF8 = "0"
$env:PYTHONCOERCECLOCALE = "0"
& $Python -c "import json,locale,platform,sys; print(json.dumps(dict(platform=platform.platform(), encoding=locale.getencoding(), filesystem_encoding=sys.getfilesystemencoding(), utf8_mode=sys.flags.utf8_mode)))" | Set-Content -Encoding UTF8 (Join-Path $Output "platform.json")
$env:LOCALPDF_UNICODE_LOG = Join-Path (Resolve-Path $Output).Path "unicode.jsonl"
& $Python -m pytest -ra tests/test_unicode_remediation.py --junitxml=(Join-Path $Output "unicode.xml")
if ($LASTEXITCODE) { throw "Unicode/recovery gate failed" }
& $Python -m pytest -ra --junitxml=(Join-Path $Output "all-tests.xml")
if ($LASTEXITCODE) { throw "Full suite failed" }
if ($RunLive) {
    & $Python scripts/validation/live_grounding.py --output (Join-Path $Output "live-model.json")
    if ($LASTEXITCODE) { Write-Warning "Live gate remains incomplete or failed. Review its recorded result." }
}
Write-Host "Automation finished. Complete the actual browser, live-page, Android and trusted HTTPS checks in docs/REMEDIATION_OPERATIONS.md. This script does not grant release approval."
