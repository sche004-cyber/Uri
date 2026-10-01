@echo off
REM EXPERIMENTAL harness-first URI build. Undo with "Restore normal URI.bat".
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0scripts\launch_uri_harness_first.ps1"
exit /b 0
