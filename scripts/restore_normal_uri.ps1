<#
.SYNOPSIS
    Undo "Launch URI Harness-First": close the desktop app, stop the harness-first backend this
    checkout started (by its recorded process id), and start the normal URI backend again.
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $RepoRoot "uri_workspace\logs\harness_first_server.pid"
Get-Process -Name "uri_ui" -ErrorAction SilentlyContinue | Stop-Process -Force -Confirm:$false
if (Test-Path $PidFile) {
    $id = [int](Get-Content $PidFile | Select-Object -First 1)
    Get-CimInstance Win32_Process -Filter "ParentProcessId = $id" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
    Stop-Process -Id $id -Force -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item $PidFile -Force -Confirm:$false
}
if (Get-ScheduledTask -TaskName "URIServer" -ErrorAction SilentlyContinue) { Start-ScheduledTask -TaskName "URIServer" }
