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
if (-not (Test-Path $exe)) { throw "profile build missing: $exe" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
# Absolute, because the app runs with uri_ui/ as its working directory.
$OutDir = (Resolve-Path $OutDir).Path
if (-not $Tag) { $Tag = "$Scenario-$Identity-$Size" }
$json = Join-Path $OutDir "$Tag.json"
$csv = Join-Path $OutDir "$Tag.samples.csv"
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
