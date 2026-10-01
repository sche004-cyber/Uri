<#
.SYNOPSIS
    Gracefully stops the URI Desktop application and backend server.

.DESCRIPTION
    Uses PID files for targeted shutdown - only terminates processes
    that THIS launcher started, not any process named "uri_ui".

    1. Stop the UI process tracked in uri_workspace/uri_ui.pid.
    2. Stop the backend server tracked in uri_workspace/uri_server.pid.
    3. Verify port release.

    Does NOT indiscriminately kill processes by name.
    Does NOT attempt to terminate an externally-owned backend.
#>

param(
    [int]$Port = 8000
)

$RepoRoot = $PSScriptRoot
$ServerPidFile = Join-Path $RepoRoot "uri_workspace\uri_server.pid"
$UiPidFile = Join-Path $RepoRoot "uri_workspace\uri_ui.pid"
$UiExePath = Join-Path $RepoRoot "uri_ui\build\windows\x64\runner\Release\uri_ui.exe"
$ServerScript = Join-Path $RepoRoot "run_desktop_server.py"

# A PID file can be stale and its number reused by an unrelated process.
# A process counts as this checkout's backend only when its executable is a
# python/pythonw and its first argument is exactly this checkout's
# run_desktop_server.py (not merely mentioned somewhere in the command line).
function Test-OwnedServer([int]$ProcessId) {
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $cim -or -not $cim.CommandLine -or -not $cim.ExecutablePath) { return $false }
    if ([IO.Path]::GetFileName($cim.ExecutablePath) -notmatch '^pythonw?\.exe$') { return $false }
    $pattern = '^\s*(?:"[^"]*"|\S+)\s+"?' + [Regex]::Escape($ServerScript) + '"?(?:\s|$)'
    return [Regex]::IsMatch($cim.CommandLine, $pattern, [Text.RegularExpressions.RegexOptions]::IgnoreCase)
}

Write-Output "==> Shutting down URI Desktop..."

# 1. Stop Desktop UI - targeted by PID file
if (Test-Path $UiPidFile) {
    $uiPid = (Get-Content $UiPidFile -ErrorAction SilentlyContinue).Trim()
    if ($uiPid -match "^\d+$") {
        $proc = Get-Process -Id ([int]$uiPid) -ErrorAction SilentlyContinue
        $procPath = $null
        if ($proc) { try { $procPath = $proc.Path } catch {} }
        if ($proc -and $procPath -and ($procPath -ieq $UiExePath)) {
            Write-Output "Closing URI desktop app (PID $uiPid)..."
            $proc.CloseMainWindow() | Out-Null
            $proc.WaitForExit(3000) | Out-Null
            if (-not $proc.HasExited) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Remove-Item $UiPidFile -Force -ErrorAction SilentlyContinue
}
else {
    Write-Output "No UI PID file found - UI may not have been launched by this system."
}

# 2. Stop Managed Backend - targeted by PID file
if (Test-Path $ServerPidFile) {
    $serverPid = (Get-Content $ServerPidFile -ErrorAction SilentlyContinue).Trim()
    if ($serverPid -match "^\d+$") {
        $proc = Get-Process -Id ([int]$serverPid) -ErrorAction SilentlyContinue
        if ($proc -and -not (Test-OwnedServer ([int]$serverPid))) {
            Write-Output "PID $serverPid in the PID file is not this URI backend (stale PID file) - leaving it alone."
            $proc = $null
        }
        if ($proc) {
            Write-Output "Terminating URI backend server (PID $serverPid)..."
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    }
    Remove-Item $ServerPidFile -Force -ErrorAction SilentlyContinue
}
else {
    Write-Output "No server PID file found - backend may not have been started by this launcher."
}

# 3. Check for lingering listener on port - but do NOT kill it if it's
#    not ours (the PID file was our authority; without it, we don't own it)
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $owningPid = $conn.OwningProcess
    Write-Output "Port $Port still has a listener (PID $owningPid)."
    # Only kill if we can verify it's a run_desktop_server.py process
    try {
        if (Test-OwnedServer ([int]$owningPid)) {
            Write-Output "Confirmed lingering desktop server - stopping PID $owningPid..."
            Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
        else {
            Write-Output "Listener is NOT a URI desktop server - leaving it alone."
        }
    }
    catch {
        Write-Output "Could not inspect lingering process - leaving it alone."
    }
}

# 4. Verify Port Release
$released = $false
for ($i = 0; $i -lt 5; $i++) {
    $stillListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $stillListening) {
        $released = $true
        break
    }
    Start-Sleep -Milliseconds 500
}

if ($released) {
    Write-Output "==> URI shutdown complete. Port $Port is released."
    exit 0
} else {
    Write-Warning "Port $Port is still in use by PID $($stillListening.OwningProcess). This process is not owned by URI."
    exit 1
}
