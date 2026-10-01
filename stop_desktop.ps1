<#
.SYNOPSIS
    Gracefully stops the URI Desktop application and backend server, verifying port release.
#>

param(
    [int]$Port = 8000
)

$RepoRoot = $PSScriptRoot
$PidFile = Join-Path $RepoRoot "uri_workspace\uri_server.pid"

Write-Output "==> Shutting down URI Desktop..."

# 1. Stop Desktop UI
$uiProcs = Get-Process -Name "uri_ui" -ErrorAction SilentlyContinue
if ($uiProcs) {
    Write-Output "Closing URI desktop app window..."
    $uiProcs | ForEach-Object {
        $_.CloseMainWindow() | Out-Null
        Start-Sleep -Milliseconds 500
        if (-not $_.HasExited) {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

# 2. Stop Managed Backend
if (Test-Path $PidFile) {
    $serverPid = (Get-Content $PidFile -ErrorAction SilentlyContinue).Trim()
    if ($serverPid -match "^\d+$") {
        $proc = Get-Process -Id ([int]$serverPid) -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Output "Terminating URI backend process (PID $serverPid)..."
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# Check if any lingering run_desktop_server is still listening on port
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $owningPid = $conn.OwningProcess
    $p = Get-Process -Id $owningPid -ErrorAction SilentlyContinue
    if ($p -and $p.CommandLine -like "*run_desktop_server.py*") {
        Write-Output "Stopping lingering server PID $owningPid..."
        Stop-Process -Id $owningPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

# 3. Verify Port Release
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
    Write-Warning "Port $Port is still in use by PID $($stillListening.OwningProcess)."
    exit 1
}
