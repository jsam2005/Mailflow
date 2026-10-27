@echo off
setlocal EnableExtensions
REM Double-click first-time setup for Windows 11 x64.
REM Paths with spaces are supported via %~dp0 quoting.

cd /d "%~dp0"
title MailFlow Windows setup

echo.
echo MailFlow first-time setup (Windows)
echo Repository: %CD%
echo.

REM Bypass is process-local only — does not change machine execution policy.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows.ps1" %*
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo Setup failed with exit code %ERR%.
  echo See launcher\.runtime\setup-windows.log
) else (
  echo Setup finished.
)
echo.
pause
exit /b %ERR%
