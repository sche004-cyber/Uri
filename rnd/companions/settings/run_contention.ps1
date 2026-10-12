# Focused contention check (synthetic, controlled): the measured app runs
# Lunar in the shell for 100 s; from second 30 to second 70 a second process
# (layout "stress": 24 companions, uncapped) loads the GPU. Run once with the
# adaptive rate and once fixed at 144 for comparison.
#
#   powershell -NoProfile -File rnd/companions/settings/run_contention.ps1 -OutDir <dir>
#
# The load is graphics work, not a language model: it shows how the governor
# responds to real GPU contention, not what a Brain generating would do.
param([Parameter(Mandatory = $true)][string]$OutDir)
$run = Join-Path $PSScriptRoot 'run_companion_perf.ps1'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
foreach ($fps in 'adaptive', 'fps144') {
  $load = Start-Job -ArgumentList $run, $OutDir, $fps -ScriptBlock {
    param($run, $out, $fps)
    Start-Sleep -Seconds 30
    & $run -Identity lunar -Fps fps144 -Quality full -Layout stress -Seconds 40 -OutDir (Join-Path $out 'load') -Tag "load-for-$fps"
  }
  & $run -Identity lunar -Fps $fps -Quality full -Layout shell -Seconds 100 -OutDir $OutDir -Tag "contention-lunar-$fps"
  Wait-Job $load | Receive-Job | Select-String 'REPORT'
}
Write-Output "CONTENTION_DONE $(Get-Date -Format o)"
