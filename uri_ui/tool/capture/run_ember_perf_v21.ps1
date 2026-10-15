<#
Ember V2.1 performance series: V2.1 Ember, V2 Ember and Solar, alternated, two
runs each, through run_ember_perf.ps1. Meant to run INSIDE the GPU lease:

  python -m uri_operational_intelligence.gpu_lease run --purpose benchmark `
    --label "Ember V2.1 perf series" -- powershell -File tool\capture\run_ember_perf_v21.ps1 -Builds <dir> -Out <dir>

Before every run it re-checks that this process tree still holds the lease and
that no llama-server (Brain) is resident; if either fails it stops and writes
BLOCKED.txt instead of measuring. Nothing else is started or stopped.
#>
param(
  [Parameter(Mandatory)] [string] $Builds,
  [Parameter(Mandatory)] [string] $Out,
  # Folder the builds were compiled to write their own <id>_perf.json and PNGs to
  # (--dart-define=OUT). Its files are moved into each run's folder after the run.
  [Parameter(Mandatory)] [string] $Baked
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$lease = Join-Path $env:LOCALAPPDATA 'URI\gpu\lease.json'
$incoming = Join-Path $Out '_incoming'
New-Item -ItemType Directory -Force $Out | Out-Null

function Get-Ancestors {
  $ids = @(); $p = $PID
  while ($p) {
    $ids += $p
    $p = (Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction SilentlyContinue).ParentProcessId
    if ($ids -contains $p) { break }
  }
  return $ids
}

function Assert-Exclusive([string] $tag) {
  $l = Get-Content $lease -Raw | ConvertFrom-Json
  $mine = (Get-Ancestors) -contains [int]$l.pid
  $brain = @(Get-Process -Name 'llama-server' -ErrorAction SilentlyContinue)
  $line = "$tag lease_state=$($l.state) lease_pid=$($l.pid) purpose=$($l.purpose) ours=$mine brain_resident=$($brain.Count)"
  Add-Content -Path (Join-Path $Out 'lease_checks.txt') -Value $line
  if ($l.state -ne 'held' -or -not $mine -or $brain.Count -gt 0) {
    Set-Content -Path (Join-Path $Out 'BLOCKED.txt') -Value $line
    throw "BLOCKED: $line"
  }
}

$order = @('v21_ember', 'v2_ember', 'v21_solar', 'v21_ember', 'v2_ember', 'v21_solar')
$count = @{}
foreach ($name in $order) {
  $count[$name] = 1 + [int]$count[$name]
  $run = "$($name)_r$($count[$name])"
  Assert-Exclusive "before $run"
  $id = if ($name -like '*solar') { 'solar' } else { 'ember' }
  $src = Join-Path $incoming $name
  Get-ChildItem -Path $Baked -Filter "$($id)_*" -ErrorAction SilentlyContinue | Remove-Item -Force
  if (Test-Path $src) { Remove-Item -Recurse -Force $src }
  New-Item -ItemType Directory -Force $src | Out-Null
  & (Join-Path $here 'run_ember_perf.ps1') -Exe (Join-Path $Builds "$name\uri_ui.exe") -Id $id -Out $src
  Assert-Exclusive "after $run"
  Get-ChildItem -Path $Baked -Filter "$($id)_*" -ErrorAction SilentlyContinue | Move-Item -Destination $src
  Move-Item $src (Join-Path $Out $run)
}
"RUN_EMBER_PERF_V21_DONE"
