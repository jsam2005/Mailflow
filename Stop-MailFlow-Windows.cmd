@echo off
setlocal EnableExtensions
REM Safe fallback stop — only launcher-owned processes via loopback API.

cd /d "%~dp0"
title MailFlow stop

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-windows.ps1"
exit /b %ERRORLEVEL%
