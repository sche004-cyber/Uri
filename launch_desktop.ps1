<#
.SYNOPSIS
    Authoritative one-click launcher for URI Desktop with Windows Named Mutex single-instance control.

.DESCRIPTION
    1. Uses a local Windows named mutex ("Local\URI_Desktop_App_Mutex") to prevent concurrent launch races.
    2. Checks if the backend is already running and healthy at http://127.0.0.1:8000/health.
    3. If offline, starts run_desktop_server.py directly with user privileges (no Task Scheduler/admin requirement).
    4. Waits for /health to return {"status":"ok"}.
    5. Brings existing uri_ui window to the front or launches uri_ui.exe.
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
        $res = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1 -ErrorAction Stop
        if ($res.status -eq "ok") {
            $backendHealthy = $true
        }
    }
    catch {
        $backendHealthy = $false
    }

    if ($backendHealthy) {
        Write-Step "Backend already active and healthy at $HealthUrl."
    }
    else {
        # Check port collision
        $portConflict = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($portConflict) {
            Write-Warning "Port $Port is occupied by PID $($portConflict.OwningProcess), but /health is not responding."
        }

        Write-Step "Starting URI Backend Server with Canonical Intelligence..."
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
                $h = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1 -ErrorAction Stop
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

    # 3. Desktop Application Window
    if (Activate-ExistingWindow) {
        Write-Step "Existing window activated."
    }
    else {
        if (-not (Test-Path $ExePath)) {
            Write-Error "URI Desktop binary not found at $ExePath."
            exit 1
        }
        Write-Step "Launching URI Desktop Application..."
        Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path -Parent $ExePath)
    }

    Write-Step "Done."
}
finally {
    if ($null -ne $mutex) {
        try {
            $mutex.ReleaseMutex()
            $mutex.Dispose()
        }
        catch {}
    }
}
