@echo off
REM URI working system (development; not a production cutover). See docs\working_system\WS_BLUEPRINT.md.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_uri_working_system.ps1" %*
