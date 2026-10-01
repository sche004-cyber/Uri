<#
.SYNOPSIS
    One-click launch of the EXPERIMENTAL harness-first URI build from this checkout.

.DESCRIPTION
    1. Makes sure local Ollama is running and warms the Edge chat model.
    2. If the normal URI backend (Scheduled Task "URIServer") is serving port 8000, stops it so this
       build can use the port. "Restore normal URI.bat" starts it again.
    3. Starts this checkout's backend on 127.0.0.1:8000 with URI_HARNESS_FIRST=1, using this
       checkout's own uri_workspace (your normal URI data is not touched; sign up a test account).
    4. Opens the URI desktop app (this checkout's build if present, otherwise the normal build:
       the UI source is unchanged on this branch).
    Nothing here changes system settings; every change is undone by "Restore normal URI.bat".
#>
param(
    [int]$Port = 8000,
    [string]$EdgeChatModel = "qwen3:0.6b"
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LiveRepo = "C:\Users\cheta\Development\uri-agent"
$Python = @("$RepoRoot\.venv\Scripts\python.exe", "$LiveRepo\.venv\Scripts\python.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$Exe = @("$RepoRoot\uri_ui\build\windows\x64\runner\Release\uri_ui.exe", "$LiveRepo\uri_ui\build\windows\x64\runner\Release\uri_ui.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$LogDir = Join-Path $RepoRoot "uri_workspace\logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null

function Fail($m) {
    try { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show($m, "URI (harness-first) failed to start") | Out-Null } catch {}
    exit 1
}
function Healthy($url) { try { Invoke-RestMethod $url -TimeoutSec 2 | Out-Null; $true } catch { $false } }

if (-not $Python) { Fail "No Python virtual environment found (.venv) in this checkout or in $LiveRepo." }
if (-not $Exe) { Fail "No built uri_ui.exe found. Build the desktop app once with 'flutter build windows' in uri_ui." }

# 1. Ollama + Edge chat model
if (-not (Healthy "http://127.0.0.1:11434/api/tags")) {
    Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve"
    for ($i = 0; $i -lt 30 -and -not (Healthy "http://127.0.0.1:11434/api/tags"); $i++) { Start-Sleep 1 }
    if (-not (Healthy "http://127.0.0.1:11434/api/tags")) { Fail "Ollama did not start." }
}
try {
    $body = @{ model = $EdgeChatModel; prompt = "hi"; stream = $false; keep_alive = "30m"; options = @{ num_predict = 1 } } | ConvertTo-Json
    Invoke-RestMethod "http://127.0.0.1:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
} catch { Fail "Edge chat model '$EdgeChatModel' is not available in Ollama." }

# 2. Free port 8000 from the normal backend
$task = Get-ScheduledTask -TaskName "URIServer" -ErrorAction SilentlyContinue
if ($task -and $task.State -eq "Running") { Stop-ScheduledTask -TaskName "URIServer"; Start-Sleep 2 }
if (Healthy "http://127.0.0.1:$Port/health") { Fail "Something is still serving port $Port. Close the normal URI backend first." }

# 3. This checkout's backend, harness-first on
$env:URI_HARNESS_FIRST = "1"
$env:URI_HARNESS_EDGE_CHAT_MODEL = $EdgeChatModel
$proc = Start-Process -PassThru -WindowStyle Hidden -FilePath $Python -WorkingDirectory $RepoRoot `
    -ArgumentList "scripts\run_uri_server.py", "--port", "$Port" `
    -RedirectStandardOutput "$LogDir\harness_first_server.out.log" -RedirectStandardError "$LogDir\harness_first_server.err.log"
Set-Content -Path "$LogDir\harness_first_server.pid" -Value $proc.Id -Encoding ascii
for ($i = 0; $i -lt 45 -and -not (Healthy "http://127.0.0.1:$Port/health"); $i++) { Start-Sleep 1 }
if (-not (Healthy "http://127.0.0.1:$Port/health")) { Fail "Harness-first backend did not start. See $LogDir\harness_first_server.err.log" }

# 4. Desktop app
if (-not (Get-Process -Name "uri_ui" -ErrorAction SilentlyContinue)) { Start-Process -FilePath $Exe }
