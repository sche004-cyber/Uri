<#
  Per-process GPU memory residency sampler (live voice phase, AC-13).

    powershell -NoProfile -File rnd\voice\live\sample_gpu_residency.ps1 -Seconds 900 -Out residency.csv

  Every -Interval seconds, for every process that holds GPU memory, writes one row:
  time, pid, process name, dedicated (device-local) MiB, non-local (system memory) MiB, plus the
  adapter's total dedicated usage. "Non Local Usage" of llama-server is the signal that a part of
  Runtime v1 was placed in system memory (Adaptive Runtime R1); the adapter total cannot show it.
  Read-only: performance counters only; it never signals or changes a process.
#>
param(
  [int]$Seconds = 600,
  [double]$Interval = 2,
  [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = 'Stop'
"t,pid,name,dedicated_mib,nonlocal_mib,adapter_dedicated_mib" | Set-Content -Encoding ascii $Out
$end = (Get-Date).AddSeconds($Seconds)
$names = @{}
while ((Get-Date) -lt $end) {
  $t = (Get-Date).ToString('HH:mm:ss.fff')
  try {
    $c = Get-Counter -Counter @('\GPU Process Memory(*)\Dedicated Usage', '\GPU Process Memory(*)\Non Local Usage', '\GPU Adapter Memory(*)\Dedicated Usage') -ErrorAction SilentlyContinue
  } catch { Start-Sleep -Seconds $Interval; continue }
  $per = @{}
  $adapter = 0
  foreach ($s in $c.CounterSamples) {
    if ($s.Path -like '*gpu adapter memory*') { $adapter += $s.CookedValue; continue }
    if ($s.InstanceName -notmatch '^pid_(\d+)_') { continue }
    $procId = [int]$Matches[1]
    if (-not $per.ContainsKey($procId)) { $per[$procId] = @(0, 0) }
    if ($s.Path -like '*dedicated usage') { $per[$procId][0] += $s.CookedValue } else { $per[$procId][1] += $s.CookedValue }
  }
  $rows = @()
  foreach ($procId in $per.Keys) {
    $d = $per[$procId][0]; $n = $per[$procId][1]
    if (($d + $n) -lt 32MB) { continue }
    if (-not $names.ContainsKey($procId)) {
      $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
      $names[$procId] = if ($p) { $p.ProcessName } else { '?' }
    }
    $rows += [string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0},{1},{2},{3:F0},{4:F0},{5:F0}',
      $t, $procId, $names[$procId], ($d / 1MB), ($n / 1MB), ($adapter / 1MB))
  }
  if ($rows.Count) { $rows | Add-Content -Encoding ascii $Out }
  Start-Sleep -Seconds $Interval
}
