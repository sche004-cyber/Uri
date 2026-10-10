<#
.SYNOPSIS
  Start the URI working system (development; NOT a production cutover). WS blueprint W7 / AC-11.

.DESCRIPTION
  Order (UI first, P-GOV-1): verify the materialized runtime -> integrated paired server
  (scripts\run_uri_integrated_server.py) -> the Flutter app with URI_CLIENT_MANIFEST set, waiting until its window
  exists -> Brain host (scripts\ws_brain_host.py: GPU lease, contention wait, measured VRAM release wait, Runtime v1
  through the accepted RuntimeManager, calibration). The Brain host's fit check then counts the open window. This is
  the order measured at 133-147 tok/s; a window opened after the Brain loaded left it at about a third of its speed.

  A second launch reuses what is running: a live Brain host is not duplicated, and a second window of the same UI
  build is not opened.

  Refuses, before starting anything:
    * a runtime root that is the legacy checkout (uri-agent) or the M37-M39 donor, or that is not HEAD e8e3b65 with a
      working-system materialization receipt;
    * a server manifest whose port is 8000 (legacy instance) or whose source_root is not the runtime root;
    * a UI executable outside the working-system integration worktree.
  It never stops, reconfigures or contacts the legacy instance, the scheduled task \URIServer, Ollama or any
  shortcut. It never stops a foreign process on the Runtime v1 port.

.PARAMETER SelfTest
  Run only the verification and refusal checks (including negative cases) and print JSON. Starts nothing.

.PARAMETER OverrideGpu
  Owner-authorized: start the Brain even when other GPU processes leave too little memory. Recorded in the GPU lease
  and the Brain host report; the speed check still classifies the result. No process is ever stopped.
#>
param(
  [string]$RuntimeRoot = 'C:\Users\cheta\Development\uri-ws-hard',
  [string]$UiExe = '',
  [int]$BrainMinutes = 480,
  [switch]$NoBrain,
  [switch]$OverrideGpu,
  [switch]$NoUi,
  [switch]$SelfTest,
  # The integration worktree the UI build must come from (a staging source tree is passed here explicitly).
  [string]$UiRoot = 'C:\Users\cheta\Development\uri-ws-hardening'
)
$ErrorActionPreference = 'Stop'
$Base = 'e8e3b65259c45fc823addc3ef8969425a265bd1b'
$LegacyRoots = @('C:\Users\cheta\Development\uri-agent', 'C:\Users\cheta\Development\uri-m37-m39-integration')
$LegacyPorts = @(8000, 8018, 8021)
if (-not $UiExe) { $UiExe = Join-Path $UiRoot 'uri_ui\build\windows\x64\runner\Release\uri_ui.exe' }

function Norm([string]$p) { return [IO.Path]::GetFullPath($p).TrimEnd('\').ToLowerInvariant() }

function Test-Installation([string]$root, [string]$uiExe) {
  $problems = @()
  $r = Norm $root
  foreach ($l in $LegacyRoots) { $n = Norm $l; if ($r -eq $n -or $r.StartsWith($n + '\')) { $problems += "LEGACY_ROOT_REFUSED:$l" } }
  if (-not (Test-Path (Join-Path $root 'OI_MATERIALIZATION_RECEIPT.json'))) { $problems += 'MATERIALIZATION_RECEIPT_MISSING' }
  $head = ''
  try { $head = (& git -C $root rev-parse HEAD 2>$null) } catch {}
  if ($head -ne $Base) { $problems += "RUNTIME_HEAD_NOT_BASE:$head" }
  $curPath = Join-Path $root 'work\c1\ws-current.json'
  $cur = $null
  if (-not (Test-Path $curPath)) { $problems += 'INSTALLATION_MISSING (run scripts\ws_provision.py)' }
  else {
    $cur = Get-Content -Raw -Encoding UTF8 $curPath | ConvertFrom-Json
    $srv = Get-Content -Raw -Encoding UTF8 $cur.server_manifest | ConvertFrom-Json
    if ($LegacyPorts -contains [int]$srv.port) { $problems += "LEGACY_PORT_REFUSED:$($srv.port)" }
    if ((Norm $srv.source_root) -ne $r) { $problems += 'SERVER_SOURCE_ROOT_MISMATCH' }
    $cli = Get-Content -Raw -Encoding UTF8 $cur.client_manifest | ConvertFrom-Json
    if ((Norm $cli.source_root) -ne $r) { $problems += 'CLIENT_SOURCE_ROOT_MISMATCH' }
    if (-not (Test-Path (Join-Path $cli.client_root 'control\ui-integrated-profile.json'))) { $problems += 'INTEGRATED_OPT_IN_MISSING' }
  }
  if ($uiExe) {
    $u = Norm $uiExe
    if (-not $u.StartsWith((Norm $UiRoot) + '\')) { $problems += 'UI_OUTSIDE_INTEGRATION_WORKTREE' }
    foreach ($l in $LegacyRoots) { $n = Norm $l; if ($u.StartsWith($n + '\')) { $problems += "LEGACY_UI_REFUSED:$l" } }
  }
  return [pscustomobject]@{ ok = ($problems.Count -eq 0); problems = $problems; installation = $cur }
}

function Get-LiveBrainHost([string]$reportDir) {
  # The Brain host report names its process; it counts only if that process still exists with the recorded start.
  $f = Join-Path $reportDir 'brain_host.json'
  if (-not (Test-Path $f)) { return $null }
  try { $r = Get-Content -Raw -Encoding UTF8 $f | ConvertFrom-Json } catch { return $null }
  if ($r.schema -ne 'uri.ws.brain_host.v1') { return $null }
  $p = Get-Process -Id ([int]$r.host_pid) -ErrorAction SilentlyContinue
  if (-not $p) { return $null }
  $started = [DateTimeOffset]::FromUnixTimeMilliseconds([int64]([double]$r.host_started * 1000)).LocalDateTime
  if ([Math]::Abs(($p.StartTime - $started).TotalSeconds) -gt 5) { return $null }
  return $r
}

function Test-Http([string]$url) {
  try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $url; return [int]$r.StatusCode } catch {
    if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } ; return 0 }
}

if ($SelfTest) {
  $real = Test-Installation $RuntimeRoot $UiExe
  $negLegacy = Test-Installation 'C:\Users\cheta\Development\uri-agent' $UiExe
  $negUi = Test-Installation $RuntimeRoot 'C:\Users\cheta\Development\uri-m37-m39-integration\uri_ui\build\uri_ui.exe'
  # Synthetic installation whose server manifest names the legacy port: must be refused.
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ('ws-selftest-' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force (Join-Path $tmp 'work\c1') | Out-Null
  Set-Content -Encoding ascii (Join-Path $tmp 'OI_MATERIALIZATION_RECEIPT.json') '{}'
  $sm = Join-Path $tmp 'server.json'; $cm = Join-Path $tmp 'client.json'
  (@{ port = 8000; source_root = $tmp; state_root = $tmp } | ConvertTo-Json) | Set-Content -Encoding ascii $sm
  (@{ source_root = $tmp; client_root = $tmp } | ConvertTo-Json) | Set-Content -Encoding ascii $cm
  (@{ server_manifest = $sm; client_manifest = $cm; port = 8000 } | ConvertTo-Json) | Set-Content -Encoding ascii (Join-Path $tmp 'work\c1\ws-current.json')
  $negPort = Test-Installation $tmp $null
  Remove-Item -Recurse -Force $tmp
  # Listener identity: the real manifest must prove; the same live proof checked against another valid key must fail.
  $idOk = $null; $idForeign = $null
  if ($real.ok) {
    $py0 = Join-Path $RuntimeRoot '.venv\Scripts\python.exe'; $tool = Join-Path $RuntimeRoot 'scripts\ws_server_identity.py'
    $sm0 = $real.installation.server_manifest
    if ((Test-Http ("http://127.0.0.1:{0}/health" -f $real.installation.port)) -ne 0) {
      & $py0 $tool $sm0 | Out-Null; $idOk = ($LASTEXITCODE -eq 0)
      & $py0 $tool $sm0 --selftest-wrong-key | Out-Null; $idForeign = ($LASTEXITCODE -eq 0)
    }
  }
  $out = [ordered]@{
    schema = 'uri.ws.launcher_selftest.v1'
    real_installation = @{ ok = $real.ok; problems = $real.problems; port = $real.installation.port }
    negative_legacy_root = @{ refused = (-not $negLegacy.ok); problems = $negLegacy.problems }
    negative_foreign_ui = @{ refused = (-not $negUi.ok); problems = $negUi.problems }
    negative_legacy_port = @{ refused = (@($negPort.problems | Where-Object { $_ -like 'LEGACY_PORT_REFUSED*' }).Count -gt 0); problems = $negPort.problems }
    listener_identity_proven = $idOk
    wrong_key_proof_refused = $idForeign
    legacy_port_8000_contacted = $false
    gpu_lease = $(try { (& (Join-Path $RuntimeRoot '.venv\Scripts\python.exe') -m uri_operational_intelligence.gpu_lease status 2>$null | Out-String | ConvertFrom-Json).state } catch { 'UNREADABLE' })
  }
  $out | ConvertTo-Json -Depth 5
  if ($real.ok -and -not $negLegacy.ok -and -not $negUi.ok -and $out.negative_legacy_port.refused -and ($idOk -ne $false) -and ($idForeign -ne $false)) { exit 0 } else { exit 1 }
}

$check = Test-Installation $RuntimeRoot ($(if ($NoUi) { $null } else { $UiExe }))
if (-not $check.ok) { Write-Error ("REFUSED: " + ($check.problems -join ', ')); exit 2 }
$cur = $check.installation
$py = Join-Path $RuntimeRoot '.venv\Scripts\python.exe'

# 1. Integrated server. An existing listener is accepted only with this installation's signed identity proof
#    (scripts\ws_server_identity.py, frozen verify_proof); a foreign listener on the port is refused, never used.
$srv = Get-Content -Raw -Encoding UTF8 $cur.server_manifest | ConvertFrom-Json
$health = "http://127.0.0.1:$($srv.port)/health"
$idTool = Join-Path $RuntimeRoot 'scripts\ws_server_identity.py'
function Test-Identity { & $py $idTool $cur.server_manifest | Out-Null; return ($LASTEXITCODE -eq 0) }
if ((Test-Http $health) -ne 0) {
  if (-not (Test-Identity)) { Write-Error "REFUSED: FOREIGN_LISTENER_ON_SERVER_PORT $($srv.port)"; exit 3 }
} else {
  Start-Process -FilePath $py -ArgumentList @('-B', '-I', (Join-Path $RuntimeRoot 'scripts\run_uri_integrated_server.py'), '--manifest', $cur.server_manifest) `
    -WorkingDirectory $srv.state_root -WindowStyle Hidden | Out-Null
  $deadline = (Get-Date).AddSeconds(60)
  while (-not (Test-Identity)) { if ((Get-Date) -gt $deadline) { Write-Error 'SERVER_DID_NOT_PROVE_IDENTITY'; exit 3 }; Start-Sleep -Milliseconds 500 }
}
Write-Host "Integrated server: port $($srv.port), identity proven"

# 2. UI, before the Brain (P-GOV-1): the window's GPU memory must exist when the Brain host measures the fit.
if (-not $NoUi) {
  if (-not (Test-Path $UiExe)) { Write-Error "UI_NOT_BUILT: $UiExe (flutter build windows in $UiRoot\uri_ui)"; exit 4 }
  $open = @(Get-Process uri_ui -ErrorAction SilentlyContinue | Where-Object { $_.Path -and ((Norm $_.Path) -eq (Norm $UiExe)) })
  if ($open.Count -gt 0) {
    # One worker per installation (L-MUTEX): a second window would only fail to start its worker. The Brain step
    # below still runs, so a reused window still gets a Brain.
    Write-Host "URI is already open (pid $($open[0].Id)); not starting a second window."
  } else {
    $env:URI_CLIENT_MANIFEST = $cur.client_manifest
    $ui = Start-Process -FilePath $UiExe -WorkingDirectory (Split-Path $UiExe) -PassThru
    # Wait for the window (its swap chain is allocated with it), then settle briefly so the census sees it.
    $deadline = (Get-Date).AddSeconds(30)
    while ($ui.MainWindowHandle -eq 0 -and -not $ui.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300; $ui.Refresh() }
    if ($ui.MainWindowHandle -ne 0) { Start-Sleep -Seconds 2; Write-Host "URI started (Living Companion, pid $($ui.Id))." }
    else { Write-Host "URI window not seen after 30 s (pid $($ui.Id)); the Brain host starts anyway." }
  }
}

# 3. Brain, after the window. A live Brain host is reused (never duplicated). Something else answering on the
#    Runtime v1 port is attached, not adopted or stopped (the worker verifies its identity). Otherwise the Brain host
#    starts: it takes the machine-wide GPU lease, waits while other GPU processes leave too little memory (explaining
#    who), waits for measured VRAM release, starts Runtime v1 through the accepted RuntimeManager and measures its speed.
$cli0 = Get-Content -Raw -Encoding UTF8 $cur.client_manifest | ConvertFrom-Json
$reportDir = Join-Path $cli0.client_root 'control\oi'
$liveHost = Get-LiveBrainHost $reportDir
$brain = Test-Http 'http://127.0.0.1:18470/health'
if ($liveHost) {
  Write-Host "Brain host: already running (pid $($liveHost.host_pid), $($liveHost.state)); reused"
} elseif ($brain -eq 0 -and -not $NoBrain) {
  $hostArgs = @((Join-Path $RuntimeRoot 'scripts\ws_brain_host.py'), '--report-dir', $reportDir, '--minutes', "$BrainMinutes")
  if ($OverrideGpu) { $hostArgs += '--override-contention'; Write-Host 'GPU override: owner-authorized start next to other GPU processes (recorded)' }
  Start-Process -FilePath $py -ArgumentList $hostArgs -WorkingDirectory $RuntimeRoot -WindowStyle Hidden | Out-Null
  Write-Host "Brain host: starting (GPU check, load and speed check run in the background; URI shows the state)"
} else { Write-Host "Runtime v1: health $brain (attach; identity verified by the worker)" }
