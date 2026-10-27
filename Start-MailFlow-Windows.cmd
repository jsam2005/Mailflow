@echo off
setlocal EnableExtensions
REM Everyday launcher entry point for Windows.
REM Leave this window open while using MailFlow.

cd /d "%~dp0"
title MailFlow launcher

if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo Backend virtualenv missing.
  echo Run Setup-MailFlow-Windows.cmd first.
  echo.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-windows.ps1"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  pause
)
exit /b %ERR%
