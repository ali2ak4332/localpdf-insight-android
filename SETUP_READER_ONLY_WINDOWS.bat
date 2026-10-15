@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "%~dp0scripts\windows\setup_windows.ps1" (
  echo Extract the entire ZIP before running this file.
  pause
  exit /b 2
)
PowerShell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\setup_windows.ps1" -SkipAI
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo Setup or launch failed. Run DIAGNOSE_WINDOWS.bat for details.
  pause
)
exit /b %RC%
