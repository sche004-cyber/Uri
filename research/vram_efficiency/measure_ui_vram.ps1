<#
Measures the GPU memory of one URI window (research only). Starts the given uri_ui.exe (no worker manifest: the
app runs its own demo sources; nothing else is started), sizes the window to 1400x900, samples the process's
"GPU Process Memory" Dedicated and Non Local usage in Companion mode, clicks into the Workspace and samples again,
then closes the window it started. Writes one JSON line per sample to -Out.
#>
param(
  [Parameter(Mandatory = $true)][string]$Exe,
  [Parameter(Mandatory = $true)][string]$Tag,
  [Parameter(Mandatory = $true)][string]$Out,
  [int]$Samples = 6
)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WM {
  [StructLayout(LayoutKind.Sequential)] public struct PT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool rp);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref PT p);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
}
"@
function Sample([System.Diagnostics.Process]$p, [string]$view) {
  for ($i = 0; $i -lt $Samples; $i++) {
    $s = (Get-Counter "\GPU Process Memory(pid_$($p.Id)_*)\Dedicated Usage", "\GPU Process Memory(pid_$($p.Id)_*)\Non Local Usage").CounterSamples
    $ded = ($s | Where-Object { $_.Path -like '*dedicated usage' } | Measure-Object CookedValue -Sum).Sum / 1MB
    $nl = ($s | Where-Object { $_.Path -like '*non local usage' } | Measure-Object CookedValue -Sum).Sum / 1MB
    [ordered]@{ tag = $Tag; view = $view; i = $i; dedicated_mib = [math]::Round($ded, 1); non_local_mib = [math]::Round($nl, 1);
      t = (Get-Date -Format 's') } | ConvertTo-Json -Compress | Add-Content -Encoding utf8 $Out
    Start-Sleep -Seconds 1
  }
}
if (-not $env:URI_MEASURE_MANIFEST) { $env:URI_CLIENT_MANIFEST = '' } else { $env:URI_CLIENT_MANIFEST = $env:URI_MEASURE_MANIFEST }
$env:URI_LIVING_SKIP_ONBOARDING = '1'
$p = Start-Process -FilePath $Exe -WorkingDirectory (Split-Path $Exe) -PassThru
try {
  $deadline = (Get-Date).AddSeconds(30)
  while ($p.MainWindowHandle -eq 0 -and -not $p.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300; $p.Refresh() }
  if ($p.MainWindowHandle -eq 0) { throw 'NO_WINDOW' }
  $h = $p.MainWindowHandle
  [WM]::MoveWindow($h, 40, 40, 1400, 900, $true) | Out-Null
  Start-Sleep -Seconds 8
  Sample $p 'companion'
  # Workspace chip under the composer (client coordinates at 1400x900, as in the staging captures).
  [WM]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Milliseconds 300
  $pt = New-Object WM+PT; $pt.X = 630; $pt.Y = 795; [WM]::ClientToScreen($h, [ref]$pt) | Out-Null
  [WM]::SetCursorPos($pt.X, $pt.Y) | Out-Null; Start-Sleep -Milliseconds 150
  [WM]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero); [WM]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Seconds 4
  Sample $p 'workspace'
} finally {
  if (-not $p.HasExited) { $p.CloseMainWindow() | Out-Null; Start-Sleep 3; if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
}
