@echo off
REM Explicit provisional harness mode of the existing URI desktop app.
start "" /min powershell -NoProfile -WindowStyle Hidden -File "%~dp0scripts\launch_uri.ps1" -HarnessManagement
exit /b 0
