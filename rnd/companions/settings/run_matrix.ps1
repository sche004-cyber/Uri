# The focused validation matrix for Companion Settings (one profile build of
# tool/demo/companion_perf.dart; see run_companion_perf.ps1).
#
#   powershell -NoProfile -File rnd/companions/settings/run_matrix.ps1 -OutDir <dir>
#
# 1. Frame-rate control: the app's Companion mode with Lunar (the costliest
#    companion) at each setting.
# 2. Render quality: one large companion, uncapped, at each quality, for the
#    two costliest identities, so the shader's share of the frame is visible.
# 3. Hidden window: minimised for ten seconds mid-run.
# Each run's samples record any other process holding more than 1 GB of VRAM.
param([Parameter(Mandatory = $true)][string]$OutDir, [int]$Seconds = 20)
$run = Join-Path $PSScriptRoot 'run_companion_perf.ps1'
foreach ($fps in 'fps30', 'fps60', 'fps90', 'fps144', 'adaptive') {
  & $run -Identity lunar -Fps $fps -Quality full -Layout shell -Seconds $Seconds -OutDir $OutDir
}
foreach ($id in 'lunar', 'solar') {
  foreach ($q in 'full', 'balanced', 'performance') {
    & $run -Identity $id -Fps fps144 -Quality $q -Layout large -Seconds $Seconds -OutDir $OutDir
  }
}
& $run -Identity lunar -Fps fps144 -Quality full -Layout shell -Seconds 32 -MinimizeAt 12 -RestoreAt 22 -OutDir $OutDir -Tag 'hidden-lunar-fps144'
Write-Output "MATRIX_DONE $(Get-Date -Format o)"
