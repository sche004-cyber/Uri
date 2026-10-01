<#
.SYNOPSIS
    Authoritative one-click launcher for URI Desktop with Windows Named Mutex single-instance control.

.DESCRIPTION
    1. Uses a local Windows named mutex ("Local\URI_Desktop_App_Mutex") to prevent concurrent launch races.
    2. Checks if the backend is already running and healthy at http://127.0.0.1:$Port/health.
    3. If a non-URI process occupies the port, ABORTS (does not start a competing server).
    4. If offline, starts run_desktop_server.py and waits for /health to confirm readiness.
    5. Mutex is held until the UI process is confirmed running (not released before UI starts).
    6. Brings existing uri_ui window to the front or launches uri_ui.exe.
    7. Records launched UI PID alongside server PID for targeted shutdown.
#>

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonwExe = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "C:\Users\cheta\Development\uri-agent\.venv\Scripts\python.exe"
    $PythonwExe = "C:\Users\cheta\Development\uri-agent\.venv\Scripts\pythonw.exe"
}
if (-not (Test-Path $PythonwExe)) {
    $PythonwExe = $PythonExe
}
$ServerScript = Join-Path $RepoRoot "run_desktop_server.py"
$LogDir = Join-Path $RepoRoot "uri_workspace\logs"
$LogFile = Join-Path $LogDir "uri_server.log"
$ExePath = Join-Path $RepoRoot "uri_ui\build\windows\x64\runner\Release\uri_ui.exe"
$HealthUrl = "http://127.0.0.1:$Port/health"
$ProcessName = "uri_ui"
$MutexName = "Local\URI_Desktop_App_Mutex"
$UiPidFile = Join-Path $RepoRoot "uri_workspace\uri_ui.pid"

function Write-Step($Message) {
    Write-Output "==> $Message"
}

function Activate-ExistingWindow {
    $existing = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Step "URI desktop app is already open. Activating window..."
        try {
            Add-Type -Name Win32NativeWindow -Namespace Native -MemberDefinition @"
                [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
                [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
"@
            foreach ($p in $existing) {
                if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
                    [Native.Win32NativeWindow]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
                    [Native.Win32NativeWindow]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
                }
            }
        }
        catch {}
        return $true
    }
    return $false
}

# 1. Acquire Named Mutex for single-instance launch control
$createdNew = $false
$mutex = $null
try {
    $mutex = New-Object System.Threading.Mutex($true, $MutexName, [ref]$createdNew)
}
catch {
    Write-Step "Could not allocate mutex; continuing with process check."
}

if (-not $createdNew -and $null -ne $mutex) {
    Write-Step "Another launch is already in progress. Activating window..."
    Activate-ExistingWindow | Out-Null
    exit 0
}

try {
    # 2. Check Backend Health
    $backendHealthy = $false
    try {
        $res = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "ok") {
            $backendHealthy = $true
        }
    }
    catch {
        $backendHealthy = $false
    }

    if ($backendHealthy) {
        # A healthy /health only proves *a* URI backend is listening. Make sure it
        # is this checkout's desktop backend, not one started from another
        # worktree, before attaching the UI to it. Never stop it either way.
        $ownerRoot = $null
        try {
            $st = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/desktop/status" -TimeoutSec 5 -ErrorAction Stop
            $ownerRoot = $st.repo_root
        }
        catch {}
        if (-not $ownerRoot -or ([IO.Path]::GetFullPath($ownerRoot).TrimEnd([char]92) -ne [IO.Path]::GetFullPath($RepoRoot).TrimEnd([char]92))) {
            Write-Error "Port $Port is serving a URI backend that is not this desktop install ($RepoRoot; it reports '$ownerRoot'). Close that backend first. Aborting."
            exit 1
        }
        Write-Step "Backend already active and healthy at $HealthUrl."
    }
    else {
        # Check port conflict - ABORT if occupied by non-URI process
        $portConflict = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($portConflict) {
            Write-Error "Port $Port is occupied by PID $($portConflict.OwningProcess) but /health is not responding. This is NOT a URI server. Aborting."
            exit 1
        }

        Write-Step "Starting URI Backend Server..."
        if (-not (Test-Path $LogDir)) {
            New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        }

        # Start detached Python process via pythonw
        Start-Process -FilePath $PythonwExe -ArgumentList "`"$ServerScript`" --port $Port" -WorkingDirectory $RepoRoot -WindowStyle Hidden

        # Wait for health endpoint
        Write-Step "Waiting for backend readiness (up to 30s)..."
        $elapsed = 0
        while ($elapsed -lt 30) {
            Start-Sleep -Seconds 1
            $elapsed += 1
            try {
                $h = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2 -ErrorAction Stop
                if ($h.status -eq "ok") {
                    $backendHealthy = $true
                    break
                }
            }
            catch {}
        }

        if (-not $backendHealthy) {
            Write-Error "Backend failed to become healthy at $HealthUrl within 30 seconds."
            exit 1
        }
        Write-Step "Backend is ready."
    }

    # 3. Desktop Application Window - still under mutex protection
    if (Activate-ExistingWindow) {
        Write-Step "Existing window activated."
    }
    else {
        if (-not (Test-Path $ExePath)) {
            Write-Error "URI Desktop binary not found at $ExePath."
            exit 1
        }
        Write-Step "Launching URI Desktop Application..."
        $uiProcess = Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path -Parent $ExePath) -PassThru

        # Record UI PID for targeted shutdown
        if ($null -ne $uiProcess) {
            $uiProcess.Id | Out-File -FilePath $UiPidFile -Encoding utf8 -Force
            Write-Step "UI process started (PID $($uiProcess.Id))."

            # Wait briefly for the UI window to appear before releasing mutex
            $windowWait = 0
            while ($windowWait -lt 5) {
                Start-Sleep -Milliseconds 500
                $windowWait++
                try {
                    $uiProcess.Refresh()
                    if ($uiProcess.MainWindowHandle -ne [IntPtr]::Zero) {
                        break
                    }
                }
                catch { break }
            }
        }
    }

    Write-Step "Done."
}
finally {
    # Release mutex AFTER UI is confirmed running
    if ($null -ne $mutex) {
        try {
            $mutex.ReleaseMutex()
            $mutex.Dispose()
        }
        catch {}
    }
}
