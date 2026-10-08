@echo off
powershell.exe -NoProfile -File "%~dp0scripts\launch_uri.ps1" -Voice -VoiceSpeaker "Speakers (High Definition Audio Device)"
if errorlevel 1 pause
