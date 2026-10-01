@echo off
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0scriptsestore_normal_uri.ps1"
exit /b 0
