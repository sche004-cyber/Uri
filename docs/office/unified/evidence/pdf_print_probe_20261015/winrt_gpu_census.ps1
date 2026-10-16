# GPU census for the WinRT PDF raster path (amendment A1 review finding A1-M4). Read-only.
# Renders every page of a PDF 3 times at 1800 px in a child PowerShell (winrt_pdf_render.ps1) while sampling the
# Windows "GPU Process Memory" and "GPU Engine" performance counters for that child process id.
param([string]$Pdf, [string]$OutDir)
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'winrt_pdf_render.ps1'
$samples = @()
$before = (Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples | Measure-Object -Property CookedValue -Sum
for ($round = 1; $round -le 3; $round++) {
    $p = Start-Process powershell -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script, $Pdf, $OutDir, '1800') -PassThru -WindowStyle Hidden
    while (-not $p.HasExited) {
        $mem = (Get-Counter "\GPU Process Memory(pid_$($p.Id)*)\Dedicated Usage" -ErrorAction SilentlyContinue).CounterSamples |
            Measure-Object -Property CookedValue -Sum
        $eng = (Get-Counter "\GPU Engine(pid_$($p.Id)*)\Utilization Percentage" -ErrorAction SilentlyContinue).CounterSamples |
            Measure-Object -Property CookedValue -Maximum
        $samples += [ordered]@{ round = $round; pid = $p.Id; dedicated_bytes = [int64]$mem.Sum; engine_util_max = [double]$eng.Maximum }
        Start-Sleep -Milliseconds 100
    }
}
$after = (Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples | Measure-Object -Property CookedValue -Sum
[ordered]@{
    samples = $samples.Count
    max_dedicated_bytes_worker = ($samples | ForEach-Object { $_.dedicated_bytes } | Measure-Object -Maximum).Maximum
    max_engine_util_worker = ($samples | ForEach-Object { $_.engine_util_max } | Measure-Object -Maximum).Maximum
    system_dedicated_before = [int64]$before.Sum
    system_dedicated_after = [int64]$after.Sum
    gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
} | ConvertTo-Json -Depth 3
