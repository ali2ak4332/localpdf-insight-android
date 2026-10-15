@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\setup_windows.ps1" -Web
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
