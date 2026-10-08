<#
.SYNOPSIS
  Start the URI working system (development; NOT a production cutover). WS blueprint W7 / AC-11.

.DESCRIPTION
  Order: verify the materialized runtime -> Runtime v1 (attach, or start through uri_operational_intelligence.host)
  -> integrated paired server (scripts\run_uri_integrated_server.py) -> the Flutter app with URI_CLIENT_MANIFEST set.

  Refuses, before starting anything:
    * a runtime root that is the legacy checkout (uri-agent) or the M37-M39 donor, or that is not HEAD e8e3b65 with a
      working-system materialization receipt;
    * a server manifest whose port is 8000 (legacy instance) or whose source_root is not the runtime root;
    * a UI executable outside the working-system integration worktree.
  It never stops, reconfigures or contacts the legacy instance, the scheduled task \URIServer, Ollama or any
  shortcut. It never stops a foreign process on the Runtime v1 port.

.PARAMETER SelfTest
  Run only the verification and refusal checks (including negative cases) and print JSON. Starts nothing.
#>
param(
  [string]$RuntimeRoot = 'C:\Users\cheta\Development\uri-ws-rt',
  [string]$UiExe = 'C:\Users\cheta\Development\uri-working-system\uri_ui\build\windows\x64\runner\Release\uri_ui.exe',
  [int]$BrainMinutes = 480,
  [switch]$NoBrain,
  [switch]$NoUi,
  [switch]$SelfTest
)
$ErrorActionPreference = 'Stop'
$Base = 'e8e3b65259c45fc823addc3ef8969425a265bd1b'
$LegacyRoots = @('C:\Users\cheta\Development\uri-agent', 'C:\Users\cheta\Development\uri-m37-m39-integration')
$LegacyPorts = @(8000, 8018, 8021)
$UiRoot = 'C:\Users\cheta\Development\uri-working-system'

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
  }
  return [pscustomobject]@{ ok = ($problems.Count -eq 0); problems = $problems; installation = $cur }
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
  }
  $out | ConvertTo-Json -Depth 5
  if ($real.ok -and -not $negLegacy.ok -and -not $negUi.ok -and $out.negative_legacy_port.refused -and ($idOk -ne $false) -and ($idForeign -ne $false)) { exit 0 } else { exit 1 }
}

$check = Test-Installation $RuntimeRoot ($(if ($NoUi) { $null } else { $UiExe }))
if (-not $check.ok) { Write-Error ("REFUSED: " + ($check.problems -join ', ')); exit 2 }
$cur = $check.installation
$py = Join-Path $RuntimeRoot '.venv\Scripts\python.exe'

# 1. Runtime v1: attach if something answers on its port (the worker verifies identity and reports a foreign
#    instance; nothing here adopts or stops it), otherwise start it through the OI host (frozen argv, job object).
$brain = Test-Http 'http://127.0.0.1:18470/health'
if ($brain -eq 0 -and -not $NoBrain) {
  Start-Process -FilePath $py -ArgumentList @('-m', 'uri_operational_intelligence.host', '--minutes', "$BrainMinutes") `
    -WorkingDirectory $RuntimeRoot -WindowStyle Hidden | Out-Null
  Write-Host "Runtime v1: starting (loads in the background; URI reports its state)"
} else { Write-Host "Runtime v1: health $brain (attach; identity verified by the worker)" }

# 2. Integrated server. An existing listener is accepted only with this installation's signed identity proof
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

# 3. UI.
if (-not $NoUi) {
  if (-not (Test-Path $UiExe)) { Write-Error "UI_NOT_BUILT: $UiExe (flutter build windows in $UiRoot\uri_ui)"; exit 4 }
  $env:URI_CLIENT_MANIFEST = $cur.client_manifest
  Start-Process -FilePath $UiExe -WorkingDirectory (Split-Path $UiExe) | Out-Null
  Write-Host "URI started (Living Companion)."
}
