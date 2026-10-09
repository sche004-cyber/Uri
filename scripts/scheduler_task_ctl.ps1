<#
.SYNOPSIS
    Owner-gated Windows lifecycle for the URI Scheduler service (logon task "URIScheduler").

.DESCRIPTION
    Persistent operation while the URI app is closed needs an OS-level launcher. This script follows the
    existing URIServer pattern (scripts/uri_server_ctl.ps1): a per-user task triggered at logon, no elevation,
    restart on failure, IgnoreNew for multiple instances (the service also refuses a second instance itself).
    Unlike URIServer, the trigger is bound to the current user only.

    Registering, changing or removing a Windows scheduled task is an OWNER decision (RED). Without -Apply
    every action only PRINTS what it would do; nothing is changed. The existing URIServer task is never touched.

    install -Apply refuses unless:
      * every precondition in the plan passes (Python exists and imports uri_scheduler from the repository,
        the state directory's parent exists, the client home exists), and
      * -LiveValidation names the result.json of a passed live-Claude test (scripts/scheduler_live_test.py
        --mode live) whose "simulated" is false and whose "verdict" is "PASS", and
      * no task with that name exists yet (an existing one is never overwritten silently).

    uninstall (rollback) stops the task, stops the scheduler service process recorded in <State>\service.json
    (only if its command line is uri_scheduler.service for that state directory), unregisters the task, and
    verifies it is gone. Scheduler state, artifacts and history are never deleted.

    verify builds the task definition in memory (New-ScheduledTask) without registering anything.

.EXAMPLE
    scripts\scheduler_task_ctl.ps1 -Action plan -State C:\...\scheduler -ClientHome C:\...\client_home -PythonExe C:\...\python.exe
    scripts\scheduler_task_ctl.ps1 -Action install -State ... -ClientHome ... -PythonExe ... -LiveValidation C:\...\result.json -Apply   # owner only
    scripts\scheduler_task_ctl.ps1 -Action uninstall -State ... -Apply                                                             # rollback, owner only
#>
param(
    [ValidateSet("plan", "verify", "install", "uninstall", "status")]
    [string]$Action = "plan",
    [string]$State,
    [string]$ClientHome,
    [string]$ClientRoot,
    [ValidateSet("phase2d", "probe")]
    [string]$Qualification = "phase2d",
    [int]$Port = 18520,
    [string]$PythonExe,
    [string]$LiveValidation,
    [string]$TaskName = "URIScheduler",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
if ($TaskName -eq "URIServer") { throw "URIServer is never touched by this script" }
if ($TaskName -ne "URIScheduler" -and $Apply) { throw "-TaskName may only be changed for dry runs" }
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonExe) { $PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe" }
$UserId = "$env:USERDOMAIN\$env:USERNAME"

function Get-Plan {
    if (-not $State) { throw "-State is required" }
    $log = Join-Path $State "service.log"
    $svcArgs = "-m uri_scheduler.service run --state `"$State`" --mode live --qualification $Qualification --port $Port"
    if ($ClientHome) { $svcArgs += " --client-home `"$ClientHome`"" }
    if ($ClientRoot) { $svcArgs += " --client-root `"$ClientRoot`"" }
    [pscustomobject]@{
        TaskName         = $TaskName
        Trigger          = "AtLogOn of $UserId only"
        Execute          = "cmd.exe"
        Argument         = "/c `"`"$PythonExe`" $svcArgs >> `"$log`" 2>&1`""
        WorkingDirectory = $RepoRoot
        Settings         = "Hidden; RestartCount 999 every 1 min; no time limit; batteries allowed; MultipleInstances IgnoreNew"
        Touches          = "only $TaskName (URIServer and every other task untouched)"
    }
}

function Get-Preconditions {
    $checks = [ordered]@{}
    $checks["python_exists"] = [bool](Test-Path -LiteralPath $PythonExe -PathType Leaf)
    $checks["imports_uri_scheduler"] = $false
    if ($checks["python_exists"]) {
        Push-Location $RepoRoot
        try {
            & $PythonExe -c "import uri_scheduler.service" 2>$null
            $checks["imports_uri_scheduler"] = ($LASTEXITCODE -eq 0)
        } catch { } finally { Pop-Location }
    }
    $checks["state_parent_exists"] = [bool]($State -and (Test-Path -LiteralPath (Split-Path -Parent $State) -PathType Container))
    $checks["client_home_exists"] = [bool]($ClientHome -and (Test-Path -LiteralPath $ClientHome -PathType Container))
    $live = $false
    if ($LiveValidation -and (Test-Path -LiteralPath $LiveValidation -PathType Leaf)) {
        try {
            $j = Get-Content -LiteralPath $LiveValidation -Raw -Encoding UTF8 | ConvertFrom-Json
            $live = ($j.simulated -eq $false) -and ($j.verdict -eq "PASS")
        } catch { $live = $false }
    }
    $checks["live_claude_validation_passed"] = $live
    $checks["task_absent"] = -not [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
    [pscustomobject]$checks
}

function New-TaskDefinition($p) {
    $a = New-ScheduledTaskAction -Execute $p.Execute -Argument $p.Argument -WorkingDirectory $p.WorkingDirectory
    $t = New-ScheduledTaskTrigger -AtLogOn -User $UserId
    $s = New-ScheduledTaskSettingsSet -Hidden -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
    @{ Action = $a; Trigger = $t; Settings = $s }
}

function Stop-SchedulerService {
    if (-not $State) { return "no -State given: no service process looked up" }
    $info = Join-Path $State "service.json"
    if (-not (Test-Path -LiteralPath $info)) { return "no service.json: no recorded service process" }
    $svc = Get-Content -LiteralPath $info -Raw -Encoding UTF8 | ConvertFrom-Json
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$svc.pid)" -ErrorAction SilentlyContinue
    if (-not $proc) { return "recorded pid $($svc.pid) is not running" }
    $cl = [string]$proc.CommandLine
    if ($cl -notmatch "uri_scheduler\.service" -or $cl.IndexOf($State, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return "pid $($svc.pid) is not this scheduler service; left alone"
    }
    if (-not $Apply) { return "DRY RUN: would stop scheduler service pid $($svc.pid)" }
    Stop-Process -Id ([int]$svc.pid) -Force
    return "stopped scheduler service pid $($svc.pid)"
}

switch ($Action) {
    "plan" {
        Get-Plan | Format-List
        "Preconditions:"
        Get-Preconditions | Format-List
        "Nothing changed (plan only)."
    }
    "verify" {
        $d = New-TaskDefinition (Get-Plan)
        $task = New-ScheduledTask -Action $d.Action -Trigger $d.Trigger -Settings $d.Settings `
            -Description "URI Scheduler service (definition check only; not registered)"
        [pscustomobject]@{
            Execute           = $task.Actions[0].Execute
            TriggerUser       = $task.Triggers[0].UserId
            MultipleInstances = $task.Settings.MultipleInstances
            RestartCount      = $task.Settings.RestartCount
            Hidden            = $task.Settings.Hidden
            Registered        = [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
        } | Format-List
        "Definition built in memory only; nothing registered."
    }
    "status" { Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Select-Object TaskName, State | Format-List }
    "install" {
        $p = Get-Plan
        $p | Format-List
        $pre = Get-Preconditions
        $pre | Format-List
        $failed = @($pre.PSObject.Properties | Where-Object { -not $_.Value } | ForEach-Object { $_.Name })
        if (-not $Apply) { "DRY RUN: owner approval required; re-run with -Apply to register. Failing preconditions: $($failed -join ', ')"; break }
        if ($failed.Count -gt 0) { throw "REFUSED: preconditions not met: $($failed -join ', ')" }
        New-Item -ItemType Directory -Force -Path $State | Out-Null
        $d = New-TaskDefinition $p
        Register-ScheduledTask -TaskName $TaskName -Action $d.Action -Trigger $d.Trigger -Settings $d.Settings `
            -Description "URI Scheduler service (uri_scheduler.service): runs scheduled URI work at this user's logon." | Out-Null
        "Registered $TaskName for $UserId. Rollback: -Action uninstall -State `"$State`" -Apply"
    }
    "uninstall" {
        $exists = [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
        if (-not $Apply) {
            "DRY RUN: would stop and unregister $TaskName only (exists: $exists); state and artifacts are kept."
            Stop-SchedulerService
            break
        }
        if ($exists) { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }
        Stop-SchedulerService
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw "ROLLBACK FAILED: $TaskName still registered" }
        "Removed $TaskName (existed: $exists). Scheduler state kept in $State."
    }
}
