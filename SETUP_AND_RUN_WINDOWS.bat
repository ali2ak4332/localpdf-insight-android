@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title LocalPDF Insight - Setup and Launch

if not exist "%~dp0scripts\windows\setup_windows.ps1" (
  echo ============================================================
  echo  LocalPDF Insight cannot start from inside a ZIP file.
  echo ============================================================
  echo.
  echo Right-click the downloaded ZIP, choose "Extract All", then
  echo run SETUP_AND_RUN_WINDOWS.bat from the extracted folder.
  echo.
  pause
  exit /b 2
)

PowerShell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\setup_windows.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo ============================================================
  echo  SETUP OR LAUNCH FAILED - error code %RC%
  echo ============================================================
  echo Run DIAGNOSE_WINDOWS.bat in this folder and share the log.
  echo.
  pause
  exit /b %RC%
)
exit /b 0
