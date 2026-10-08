# Samples one process's CPU, GPU 3D-engine utilisation and dedicated GPU
# memory once a second using Windows performance counters, which report per
# process for any GPU vendor (WDDM). Also samples whole-adapter 3D utilisation
# so contention from other processes (the local Brain) is visible.
#
# Usage:
#   powershell -NoProfile -File rnd/voice/sample_process.ps1 -Name uri_ui \
#     -Seconds 90 -Out samples.csv
#
# The process is found by name once it exists; sampling starts then.
param(
  [string]$Name = '',
  [int]$ProcessId = 0,
  [int]$Seconds = 60,
  [int]$WaitSeconds = 240,
  [Parameter(Mandatory = $true)][string]$Out,
  [int]$SkipSeconds = 6
)
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$proc = $null
if ($ProcessId -gt 0) { $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue }
while (-not $proc -and $Name -and (Get-Date) -lt $deadline) {
  $proc = Get-Process -Name $Name -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $proc) { Start-Sleep -Milliseconds 500 }
}
if (-not $proc) { Write-Output "PROCESS_NOT_FOUND $Name $ProcessId"; exit 1 }
$procId = $proc.Id
Write-Output "SAMPLING pid=$procId name=$Name"
Start-Sleep -Seconds $SkipSeconds
$cores = [Environment]::ProcessorCount
$rows = New-Object System.Collections.ArrayList
$lastCpu = $proc.TotalProcessorTime.TotalMilliseconds
$lastT = Get-Date
for ($i = 0; $i -lt $Seconds; $i++) {
  Start-Sleep -Milliseconds 1000
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if (-not $p) { break }
  $now = Get-Date
  $cpuMs = $p.TotalProcessorTime.TotalMilliseconds
  $cpuPct = ($cpuMs - $lastCpu) / (($now - $lastT).TotalMilliseconds * $cores) * 100
  $lastCpu = $cpuMs; $lastT = $now
  $gpu3d = 0.0; $gpuAll3d = 0.0; $ded = 0.0; $sysCpu = 0.0; $foreign = 0.0; $foreignPids = ''
  try {
    $c = Get-Counter -Counter @(
      "\GPU Engine(pid_${procId}_*engtype_3D)\Utilization Percentage",
      '\GPU Engine(*engtype_3D)\Utilization Percentage',
      '\GPU Process Memory(*)\Dedicated Usage',
      '\Processor(_Total)\% Processor Time') -ErrorAction SilentlyContinue
    foreach ($s in $c.CounterSamples) {
      if ($s.Path -like "*processor(_total)*") { $sysCpu = $s.CookedValue }
      elseif ($s.Path -like "*gpu process memory*") {
        # Any other process holding over 1 GB of VRAM is recorded, so a run
        # that overlapped a model server is labelled as such.
        if ($s.Path -like "*pid_${procId}_*") { $ded += $s.CookedValue }
        elseif ($s.CookedValue -gt 1GB) {
          $foreign += $s.CookedValue
          if ($s.InstanceName -match 'pid_(\d+)') { $foreignPids += $Matches[1] + ' ' }
        }
      }
      elseif ($s.Path -like "*pid_${procId}_*") { $gpu3d += $s.CookedValue; $gpuAll3d += $s.CookedValue }
      else { $gpuAll3d += $s.CookedValue }
    }
  } catch {}
  [void]$rows.Add([pscustomobject]@{
    t = $i + 1; cpu_pct = [math]::Round($cpuPct, 2);
    gpu3d_pct = [math]::Round($gpu3d, 2); adapter3d_pct = [math]::Round($gpuAll3d, 2);
    dedicated_mb = [math]::Round($ded / 1MB, 1);
    system_cpu_pct = [math]::Round($sysCpu, 1);
    foreign_vram_gb = [math]::Round($foreign / 1GB, 2); foreign_pids = $foreignPids.Trim();
    working_set_mb = [math]::Round($p.WorkingSet64 / 1MB, 1) })
}
$rows | Export-Csv -NoTypeInformation -Path $Out
$m = $rows | Measure-Object -Property cpu_pct, gpu3d_pct, adapter3d_pct, dedicated_mb, working_set_mb, system_cpu_pct, foreign_vram_gb -Average -Maximum
foreach ($x in $m) { Write-Output ("{0}: avg {1:N2} max {2:N2}" -f $x.Property, $x.Average, $x.Maximum) }
Write-Output "SAMPLES $($rows.Count) -> $Out"
