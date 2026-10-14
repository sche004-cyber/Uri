<#
Runs ember_perf_app.exe (profile build) for one companion identity and samples
Windows GPU counters for that process at 1 Hz: dedicated VRAM, shared memory and
3D engine utilisation. Writes <Out>\<Id>_gpu.json next to the app's own
<Out>\<Id>_perf.json (frame timings, RSS).

  powershell -File tool\capture\run_ember_perf.ps1 -Exe <path to ember_perf_app.exe> -Id ember -Out <dir>

The executable must be a build of tool/capture/ember_perf_app.dart. Nothing
else is started or stopped. Brain residency is recorded, not changed.
#>
param(
  [Parameter(Mandatory)] [string] $Exe,
  [Parameter(Mandatory)] [string] $Id,
  [Parameter(Mandatory)] [string] $Out
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Out | Out-Null

# Record whether a local Brain (llama-server) is resident during the run.
$brain = @(Get-Process -Name 'llama-server' -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })

# OUT and ID are compile-time (--dart-define at build); the build must match.
$p = Start-Process -FilePath $Exe -WorkingDirectory (Split-Path $Exe) -PassThru
$samples = @()
while (-not $p.HasExited) {
  Start-Sleep -Milliseconds 1000
  try {
    $pidTag = "pid_$($p.Id)_"
    $mem = Get-Counter -Counter '\GPU Process Memory(*)\Dedicated Usage', '\GPU Process Memory(*)\Shared Usage' -ErrorAction SilentlyContinue
    $eng = Get-Counter -Counter '\GPU Engine(*engtype_3D)\Utilization Percentage' -ErrorAction SilentlyContinue
    $ded = ($mem.CounterSamples | Where-Object { $_.InstanceName -like "$pidTag*" -and $_.Path -like '*dedicated usage' } | Measure-Object CookedValue -Sum).Sum
    $sha = ($mem.CounterSamples | Where-Object { $_.InstanceName -like "$pidTag*" -and $_.Path -like '*shared usage' } | Measure-Object CookedValue -Sum).Sum
    $gpu = ($eng.CounterSamples | Where-Object { $_.InstanceName -like "$pidTag*" } | Measure-Object CookedValue -Sum).Sum
    $cpu = (Get-Process -Id $p.Id -ErrorAction SilentlyContinue).CPU
    $samples += [pscustomobject]@{
      t = [math]::Round(((Get-Date) - $p.StartTime).TotalSeconds, 1)
      dedicated_mb = [math]::Round($ded / 1MB, 1)
      shared_mb = [math]::Round($sha / 1MB, 1)
      gpu3d_pct = [math]::Round($gpu, 2)
      cpu_s = $cpu
    }
  } catch { }
}
[pscustomobject]@{
  identity = $Id
  exe = $Exe
  exit_code = $p.ExitCode
  brain_pids_at_start = $brain
  logical_processors = [Environment]::ProcessorCount
  samples = $samples
} | ConvertTo-Json -Depth 4 | Out-File -Encoding utf8 (Join-Path $Out "$($Id)_gpu.json")
"RUN_EMBER_PERF_DONE $Id exit=$($p.ExitCode) samples=$($samples.Count)"
