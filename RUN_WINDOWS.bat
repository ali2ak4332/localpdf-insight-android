@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo LocalPDF Insight is not set up yet.
  echo Run SETUP_AND_RUN_WINDOWS.bat first.
  pause
  exit /b 2
)
echo Starting LocalPDF Insight. Startup details are saved to LocalPDF_Run.log.
".venv\Scripts\python.exe" -X faulthandler -m localpdf_insight > "LocalPDF_Run.log" 2>&1
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo LocalPDF Insight exited with error code %RC%.
  type "LocalPDF_Run.log"
  echo Run DIAGNOSE_WINDOWS.bat for details.
  pause
)
exit /b %RC%
