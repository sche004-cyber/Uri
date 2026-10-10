# Runs one performance scenario of tool/demo/voice_demo.dart from the profile
# build and samples the exact process it launched.
#
# Build first (from uri_ui/):
#   flutter build windows --profile -t tool/demo/voice_demo.dart
# Then (from the repository root):
#   powershell -NoProfile -File rnd/voice/run_perf.ps1 -Scenario cycle `
#     -Identity lunar -Size panel -Seconds 90 -OutDir <dir> [-Tag name]
param(
  [string]$Scenario = 'cycle',
  [string]$Identity = 'lunar',
  [string]$Size = 'panel',
  [int]$Seconds = 90,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [string]$Tag = ''
)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ui = Join-Path $root 'uri_ui'
$exe = Join-Path $ui 'build\windows\x64\runner\Profile\uri_ui.exe'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
# Absolute, because the app runs with uri_ui/ as its working directory.
$OutDir = (Resolve-Path $OutDir).Path
if (-not $Tag) { $Tag = "$Scenario-$Identity-$Size" }
$json = Join-Path $OutDir "$Tag.json"
$csv = Join-Path $OutDir "$Tag.samples.csv"
# A tag reused in the same directory must not leave an earlier run's numbers next to this attempt's advisory
# (Codex P-GOV-1 r4): the earlier outputs of this tag are removed before the attempt.
foreach ($f in @($json, $csv, (Join-Path $OutDir "$Tag.gpu_advise.json"))) { if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -ErrorAction Stop } }
if (-not (Test-Path $exe)) { throw "profile build missing: $exe" }
# P-GOV-1: a performance run asks the GPU lease first (read-only; waits while a benchmark or live test holds the
# GPU) and marks itself invalid when opening the window would slow a resident Brain.
Push-Location $root
try { $advise = (& python -m uri_operational_intelligence.gpu_lease advise --window --wait 1800 | Out-String) } finally { Pop-Location }
$advise | Set-Content -Encoding utf8 (Join-Path $OutDir "$Tag.gpu_advise.json")
$verdict = $null; try { $verdict = ($advise | ConvertFrom-Json).verdict } catch {}
Write-Output "GPU_ADVISE $verdict"
if ($verdict -ne 'GO' -and $verdict -ne 'WILL_DEGRADE_BRAIN') {
  # A heavy holder is still present after the wait (or the advisory is unreadable): no window, no measurement.
  Write-Output "RUN_SKIPPED gpu advisory $verdict (see $Tag.gpu_advise.json)"; exit 3
}
if ($verdict -eq 'WILL_DEGRADE_BRAIN') { Write-Output "RUN_INVALID gpu advisory $verdict (see $Tag.gpu_advise.json)" }
$env:URI_VOICE_PERF = "$Seconds"
$env:URI_VOICE_SCENARIO = $Scenario
$env:URI_VOICE_IDENTITY = $Identity
$env:URI_VOICE_SIZE = $Size
$env:URI_VOICE_OUT = $json
$p = Start-Process -FilePath $exe -WorkingDirectory $ui -PassThru
Write-Output "LAUNCHED pid=$($p.Id) tag=$Tag"
& (Join-Path $PSScriptRoot 'sample_process.ps1') -ProcessId $p.Id -Seconds ($Seconds - 2) -SkipSeconds 5 -Out $csv
$p.WaitForExit(($Seconds + 60) * 1000) | Out-Null
if (-not $p.HasExited) { Stop-Process -Id $p.Id; Write-Output 'KILLED_AFTER_TIMEOUT' }
if (Test-Path $json) { Write-Output "REPORT $json" } else { Write-Output "NO_REPORT $json" }
