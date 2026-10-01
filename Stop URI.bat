@echo off
REM Coordinated shutdown of URI Desktop application and backend server.
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%stop_desktop.ps1"
endlocal
exit /b %ERRORLEVEL%
