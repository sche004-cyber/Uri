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
        --mode live) whose evidence directory describes ONE live run (result, journal steps, both GIF hashes,
        every attempt LIVE by claude_code; see Test-LiveValidation), and
      * no task with that name exists yet (an existing one is never overwritten silently).

    uninstall (rollback, -State required with -Apply) stops the task, stops the scheduler service process recorded
    in <State>\service.json (only if its parsed argv is `python -m uri_scheduler.service run ... --state <State>` and
    its start time matches the record), unregisters the task, and verifies it is gone. Scheduler state, artifacts
    and history are never deleted.

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
    $checks["live_claude_validation_passed"] = Test-LiveValidation
    $checks["task_absent"] = -not [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
    [pscustomobject]$checks
}

function Test-LiveValidation {
    # The live leg of scripts/scheduler_live_test.py writes result.json, journal.json, attempts.json and the two GIF
    # versions into one evidence directory. Everything must describe ONE live run (review rounds 9-10, C3-01/R10-02):
    # result: live, not simulated, PASS, LIVE available harness, verified chain; journal: the service started in live
    # mode, v1 and v2 verified with the result's hashes, v2 approved; v1.gif/v2.gif hash to those values; attempts: at
    # least two (generate + refine), every one LIVE by claude_code. An owner-run safeguard against a wrong, partial or
    # mixed evidence set, not proof against evidence the owner forges.
    if (-not $LiveValidation -or -not (Test-Path -LiteralPath $LiveValidation -PathType Leaf)) { return $false }
    if ((Split-Path -Leaf $LiveValidation) -ne "result.json") { return $false }
    $dir = Split-Path -Parent $LiveValidation
    try {
        $r = Get-Content -LiteralPath $LiveValidation -Raw -Encoding UTF8 | ConvertFrom-Json
        # Windows PowerShell 5.1 emits a JSON array as ONE object: assign it first, then enumerate it with @().
        $attRaw = Get-Content -LiteralPath (Join-Path $dir "attempts.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        $jrRaw = Get-Content -LiteralPath (Join-Path $dir "journal.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        $att = @($attRaw)
        $jr = @($jrRaw)
        $h1 = (Get-FileHash -LiteralPath (Join-Path $dir "v1.gif") -Algorithm SHA256).Hash.ToLowerInvariant()
        $h2 = (Get-FileHash -LiteralPath (Join-Path $dir "v2.gif") -Algorithm SHA256).Hash.ToLowerInvariant()
    } catch { return $false }
    $resultOk = ($r.mode -eq "live") -and ($r.simulated -eq $false) -and ($r.verdict -eq "PASS") -and
        ($r.harness.mode -eq "LIVE") -and ($r.harness.available -eq $true) -and ($r.chain.ok -eq $true) -and
        $r.v1.sha256 -and $r.v2.sha256 -and ($r.v1.sha256 -ne $r.v2.sha256)
    if (-not $resultOk) { return $false }
    $started = @($jr | Where-Object { $_.step -eq "1.service_started" -and $_.mode -eq "live" })
    $j1 = @($jr | Where-Object { $_.step -eq "6.gif_v1_verified" -and $_.sha256 -eq $r.v1.sha256 })
    $j2 = @($jr | Where-Object { $_.step -eq "9.gif_v2_verified" -and $_.sha256 -eq $r.v2.sha256 })
    $ap = @($jr | Where-Object { $_.step -eq "10.approved_v2" })
    $journalOk = ($started.Count -eq 1) -and ($j1.Count -eq 1) -and ($j2.Count -eq 1) -and ($ap.Count -eq 1)
    $filesOk = ($h1 -eq $r.v1.sha256) -and ($h2 -eq $r.v2.sha256)
    # Attempts belong to the run's own occurrence (journal step 3), not to another live run (round 11, R10-02).
    $persisted = @($jr | Where-Object { $_.step -eq "3.persisted_before_due" })
    $occ = if ($persisted.Count -eq 1) { $persisted[0].occ_id } else { $null }
    $nonLive = @($att | Where-Object { $_.mode -ne "LIVE" -or $_.harness -ne "claude_code" -or $_.occ_id -ne $occ })
    $attemptsOk = ($null -ne $occ) -and ($att.Count -ge 2) -and ($nonLive.Count -eq 0)
    return $journalOk -and $filesOk -and $attemptsOk
}

if (-not ("UriSchedulerArgv" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class UriSchedulerArgv {
    [DllImport("shell32.dll", SetLastError = true)]
    static extern IntPtr CommandLineToArgvW([MarshalAs(UnmanagedType.LPWStr)] string cmd, out int n);
    [DllImport("kernel32.dll")]
    static extern IntPtr LocalFree(IntPtr p);
    public static string[] Split(string cmd) {
        int n;
        IntPtr p = CommandLineToArgvW(cmd, out n);
        if (p == IntPtr.Zero) return new string[0];
        try {
            string[] a = new string[n];
            for (int i = 0; i < n; i++) a[i] = Marshal.PtrToStringUni(Marshal.ReadIntPtr(p, i * IntPtr.Size));
            return a;
        } finally { LocalFree(p); }
    }
}
"@
}

function Test-IsThisService($proc, $svc) {
    # Windows' own argument splitting, then fixed positions: <python>.exe -m uri_scheduler.service run ... --state <State>.
    # A quoted argument that merely contains this text is one argument and cannot match (round 10, R10-03).
    $argv = [UriSchedulerArgv]::Split([string]$proc.CommandLine)
    if ($argv.Count -lt 6) { return $false }
    if ((Split-Path -Leaf $argv[0]) -notmatch '^pythonw?(\d+(\.\d+)?)?(\.exe)?$') { return $false }
    if ($argv[1] -ne "-m" -or $argv[2] -ne "uri_scheduler.service" -or $argv[3] -ne "run") { return $false }
    $want = [System.IO.Path]::GetFullPath($State).TrimEnd([char]92)
    $ok = $false
    for ($i = 4; $i -lt $argv.Count - 1; $i++) {
        if ($argv[$i] -eq "--state") {
            try { $got = [System.IO.Path]::GetFullPath($argv[$i + 1]).TrimEnd([char]92) } catch { $got = "" }
            $ok = [string]::Equals($got, $want, [StringComparison]::OrdinalIgnoreCase)
        }
    }
    if (-not $ok) { return $false }
    # A reused PID belongs to a process that started at another time than the service recorded in service.json.
    $created = ([DateTimeOffset]$proc.CreationDate).ToUnixTimeMilliseconds() / 1000.0
    return [Math]::Abs($created - [double]$svc.started) -le 120
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
    if (-not (Test-IsThisService $proc $svc)) {
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
        if ($Apply -and -not $State) { throw "REFUSED: rollback needs -State (the installed service's state directory) so its running service is stopped too" }
        $exists = [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
        if (-not $Apply) {
            "DRY RUN: would stop and unregister $TaskName only (exists: $exists); state and artifacts are kept."
            Stop-SchedulerService
            break
        }
        if ($exists) {
            # The registered task must be the one for this -State (round 11, R11-01): otherwise nothing is touched.
            $t = Get-ScheduledTask -TaskName $TaskName
            $targs = [UriSchedulerArgv]::Split("x " + [string]$t.Actions[0].Arguments)
            $want = [System.IO.Path]::GetFullPath($State).TrimEnd([char]92)
            $match = $false
            for ($i = 0; $i -lt $targs.Count - 1; $i++) {
                if ($targs[$i] -eq "--state") {
                    try { $got = [System.IO.Path]::GetFullPath($targs[$i + 1].Trim('"')).TrimEnd([char]92) } catch { $got = "" }
                    $match = [string]::Equals($got, $want, [StringComparison]::OrdinalIgnoreCase)
                }
            }
            if (-not $match) { throw "REFUSED: $TaskName is registered for another state directory; nothing was changed" }
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        }
        Stop-SchedulerService
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw "ROLLBACK FAILED: $TaskName still registered" }
        "Removed $TaskName (existed: $exists). Scheduler state kept in $State."
    }
}
