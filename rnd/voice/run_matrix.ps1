# The performance matrix for the voice/state phase. Each run records, before
# and after, whether a GPU model server (llama-server) is resident, because
# other sessions on this machine start and stop the local Brain on their own
# schedule and that changes the GPU conditions under which a run was taken.
param([Parameter(Mandatory = $true)][string]$OutDir, [string]$Only = '')
$runs = @(
  @('idle', 'solar', 'panel', 45), @('idle', 'sakura', 'panel', 45),
  @('idle', 'lunar', 'panel', 45), @('idle', 'moonlit', 'panel', 45),
  @('cycle', 'solar', 'panel', 75), @('cycle', 'sakura', 'panel', 75),
  @('cycle', 'lunar', 'panel', 75), @('cycle', 'moonlit', 'panel', 75),
  @('voice', 'lunar', 'panel', 45),
  @('cycle', 'lunar', 'floating', 45), @('cycle', 'lunar', 'workspace', 45)
)
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$log = Join-Path $OutDir 'matrix_log.txt'
function Brain() {
  $s = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
    Where-Object { $_.CommandLine -notmatch '--embeddings' -and $_.CommandLine -match '-ngl (99|999)' }
  if ($s) { return 'resident:' + (($s | ForEach-Object { $_.ProcessId }) -join ',') } else { return 'none' }
}
foreach ($r in $runs) {
  $tag = "$($r[0])-$($r[1])-$($r[2])"
  if ($Only -and $tag -notmatch $Only) { continue }
  $before = Brain
  $out = & (Join-Path $PSScriptRoot 'run_perf.ps1') -Scenario $r[0] -Identity $r[1] -Size $r[2] -Seconds $r[3] -OutDir $OutDir
  $after = Brain
  $line = "{0} {1} brain_before={2} brain_after={3}" -f (Get-Date -Format 'HH:mm:ss'), $tag, $before, $after
  Add-Content -Path $log -Value $line
  Add-Content -Path $log -Value ($out -join "`n")
  Write-Output $line
}
Write-Output 'MATRIX_DONE'
