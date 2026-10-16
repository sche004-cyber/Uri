# Positive control for the GPU process memory counter (review R4). Read-only. Prints dwm.exe dedicated GPU memory.
$d = (Get-Process dwm).Id
$m = (Get-Counter "\GPU Process Memory(pid_$d*)\Dedicated Usage").CounterSamples | Measure-Object CookedValue -Sum
@{ dwm_pid = $d; dwm_dedicated_bytes = [int64]$m.Sum; instances = $m.Count } | ConvertTo-Json
