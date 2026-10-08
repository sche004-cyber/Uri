<#
.SYNOPSIS
    Owner-gated Windows lifecycle for the URI Scheduler service (logon task "URIScheduler").

.DESCRIPTION
    Persistent operation while the URI app is closed needs an OS-level launcher. This script follows the
    existing URIServer pattern (scripts/uri_server_ctl.ps1): a per-user task triggered at logon, no elevation,
    restart on failure, IgnoreNew for multiple instances (the service also refuses a second instance itself).

    Registering, changing or removing a Windows scheduled task is an OWNER decision (RED). Without -Apply
    every action only PRINTS what it would do; nothing is changed. The existing URIServer task is never touched.

.EXAMPLE
    scripts\scheduler_task_ctl.ps1 -Action plan -State C:\...\client\control\scheduler -ClientHome C:\...\client\home
    scripts\scheduler_task_ctl.ps1 -Action install -State ... -ClientHome ... -Apply      # owner only
#>
param(
    [ValidateSet("plan", "install", "uninstall", "status")]
    [string]$Action = "plan",
    [string]$State,
    [string]$ClientHome,
    [string]$ClientRoot,
    [ValidateSet("phase2d", "probe")]
    [string]$Qualification = "phase2d",
    [int]$Port = 18520,
    [string]$PythonExe,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$TaskName = "URIScheduler"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonExe) { $PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe" }

function Get-Plan {
    if (-not $State) { throw "-State is required" }
    $log = Join-Path $State "service.log"
    $svcArgs = "-m uri_scheduler.service run --state `"$State`" --mode live --qualification $Qualification --port $Port"
    if ($ClientHome) { $svcArgs += " --client-home `"$ClientHome`"" }
    if ($ClientRoot) { $svcArgs += " --client-root `"$ClientRoot`"" }
    [pscustomobject]@{
        TaskName         = $TaskName
        Trigger          = "AtLogOn ($env:USERNAME)"
        Execute          = "cmd.exe"
        Argument         = "/c `"`"$PythonExe`" $svcArgs >> `"$log`" 2>&1`""
        WorkingDirectory = $RepoRoot
        Settings         = "Hidden; RestartCount 999 every 1 min; no time limit; batteries allowed; MultipleInstances IgnoreNew"
        Touches          = "only \$TaskName (URIServer and every other task untouched)"
    }
}

switch ($Action) {
    "plan" { Get-Plan | Format-List; "Nothing changed (plan only)." }
    "status" { Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Select-Object TaskName, State | Format-List }
    "install" {
        $p = Get-Plan
        $p | Format-List
        if (-not $Apply) { "DRY RUN: owner approval required; re-run with -Apply to register."; break }
        New-Item -ItemType Directory -Force -Path $State | Out-Null
        $a = New-ScheduledTaskAction -Execute $p.Execute -Argument $p.Argument -WorkingDirectory $p.WorkingDirectory
        $t = New-ScheduledTaskTrigger -AtLogOn
        $s = New-ScheduledTaskSettingsSet -Hidden -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $TaskName -Action $a -Trigger $t -Settings $s `
            -Description "URI Scheduler service (uri_scheduler.service): runs scheduled URI work at this user's logon." | Out-Null
        "Registered $TaskName."
    }
    "uninstall" {
        if (-not $Apply) { "DRY RUN: would unregister $TaskName only. Re-run with -Apply."; break }
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        "Removed $TaskName (if it existed)."
    }
}
