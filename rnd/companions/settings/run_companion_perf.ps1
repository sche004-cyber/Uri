# Runs one scenario of tool/demo/companion_perf.dart from the profile build and
# samples the exact process it launched (CPU, GPU 3D share, VRAM, and every
# other process holding more than 1 GB of VRAM, e.g. a resident Brain).
#
# Build first (from uri_ui/):
#   flutter build windows --profile -t tool/demo/companion_perf.dart
# Then (from the repository root):
#   powershell -NoProfile -File rnd/companions/settings/run_companion_perf.ps1 `
#     -Identity lunar -Fps fps60 -Quality full -Layout shell -Seconds 30 -OutDir <dir>
#
# Outputs <Tag>.json (frame timings, clock deliveries, adaptive cap, RSS, Dart
# heap) and <Tag>.samples.csv (process counters) under -OutDir, which is
# resolved to an absolute path so the app (working directory uri_ui/) writes
# exactly there.
param(
  [string]$Identity = 'lunar',
  [string]$Fps = 'adaptive',
  [string]$Quality = 'full',
  [string]$Layout = 'shell',
  [int]$Seconds = 30,
  [switch]$Cycle,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [string]$Tag = '',
  # Minimise the window at this second and restore it at -RestoreAt (0 = never),
  # to measure what a hidden companion costs.
  [int]$MinimizeAt = 0,
  [int]$RestoreAt = 0
)
$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$ui = Join-Path $root 'uri_ui'
$exe = Join-Path $ui 'build\windows\x64\runner\Profile\uri_ui.exe'
if (-not (Test-Path $exe)) { throw "profile build missing: $exe" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
if (-not $Tag) { $Tag = "$Layout-$Identity-$Fps-$Quality$(if ($Cycle) { '-cycle' })" }
$json = Join-Path $OutDir "$Tag.json"
$csv = Join-Path $OutDir "$Tag.samples.csv"
$env:URI_CP_OUT = $json
$env:URI_CP_SECONDS = "$Seconds"
$env:URI_CP_IDENTITY = $Identity
$env:URI_CP_FPS = $Fps
$env:URI_CP_QUALITY = $Quality
$env:URI_CP_LAYOUT = $Layout
$env:URI_CP_CYCLE = $(if ($Cycle) { '1' } else { '0' })
$p = Start-Process -FilePath $exe -WorkingDirectory $ui -PassThru
Write-Output "LAUNCHED pid=$($p.Id) tag=$Tag $(Get-Date -Format o)"
if ($MinimizeAt -gt 0) {
  # Separate job: the sampler below blocks this script for the whole run.
  Start-Job -ArgumentList $p.Id, $MinimizeAt, $RestoreAt -ScriptBlock {
    param($procId, $minAt, $restAt)
    Add-Type -Name W -Namespace U -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c);'
    Start-Sleep -Seconds $minAt
    $h = (Get-Process -Id $procId).MainWindowHandle
    [void][U.W]::ShowWindow($h, 6)   # SW_MINIMIZE
    if ($restAt -gt $minAt) {
      Start-Sleep -Seconds ($restAt - $minAt)
      [void][U.W]::ShowWindow($h, 9) # SW_RESTORE
    }
  } | Out-Null
}
& (Join-Path $root 'rnd\voice\sample_process.ps1') -ProcessId $p.Id -Seconds ($Seconds - 2) -SkipSeconds 3 -Out $csv
$p.WaitForExit(($Seconds + 60) * 1000) | Out-Null
if (-not $p.HasExited) { Stop-Process -Id $p.Id; Write-Output 'KILLED_AFTER_TIMEOUT' }
if (Test-Path $json) { Write-Output "REPORT $json" } else { Write-Output "NO_REPORT $json" }
