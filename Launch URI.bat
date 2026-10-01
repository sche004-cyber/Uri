@echo off
REM One-click authoritative URI Desktop startup with Named Mutex single-instance control.
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SCRIPT_DIR%launch_desktop.ps1"
endlocal
exit /b %ERRORLEVEL%
