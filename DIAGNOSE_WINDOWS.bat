@echo off
setlocal EnableExtensions
cd /d "%~dp0"
PowerShell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\diagnose_windows.ps1"
echo.
echo Diagnostic written to LocalPDF_Diagnostic.txt
pause
