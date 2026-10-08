<#
.SYNOPSIS
  Drives the REAL built working-system app (integrated worker, Core, Runtime v1 when READY) with keyboard and mouse
  input, and captures the client area after each step. Evidence for WS_STATUS_REPORT.md (AC-14).

.DESCRIPTION
  Each step is "<action>|<arg>|<name>": action is `type` (SendKeys text, {ENTER} etc.), `click` (x,y relative to the
  client area), `wait` (ms) or `shot` (capture to <OutDir>\<name>.png). The app is started with URI_CLIENT_MANIFEST
  from the working-system installation and stopped at the end. Nothing else is touched.
#>
param(
  [string]$Exe = 'C:\Users\cheta\Development\uri-working-system\uri_ui\build\windows\x64\runner\Release\uri_ui.exe',
  [string]$Manifest,
  [string]$OutDir,
  [string]$Steps,     # steps separated by ';;'
  [int]$Width = 1400,
  [int]$Height = 900,
  [switch]$KeepOpen,
  [switch]$Attach,     # drive an already running uri_ui.exe instead of starting one
  [int]$AttachPid      # required with -Attach: the PID this tool's earlier -KeepOpen run printed
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class W {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct PT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref PT p);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool rp);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
}
"@
New-Item -ItemType Directory -Force $OutDir | Out-Null
if ($Attach) {
  if (-not $AttachPid) { throw 'ATTACH_PID_REQUIRED' }
  $p = Get-Process -Id $AttachPid
  if ((Resolve-Path $p.Path).Path -ne (Resolve-Path $Exe).Path) { throw "ATTACH_EXE_MISMATCH: $($p.Path)" }
} else {
$env:URI_CLIENT_MANIFEST = $Manifest
$env:URI_LIVING_SKIP_ONBOARDING = '1'
$p = Start-Process -FilePath $Exe -WorkingDirectory (Split-Path $Exe) -PassThru }
$deadline = (Get-Date).AddSeconds(30)
while ($p.MainWindowHandle -eq 0) { if ((Get-Date) -gt $deadline) { throw 'NO_WINDOW' }; Start-Sleep -Milliseconds 300; $p.Refresh() }
$h = $p.MainWindowHandle
# Provenance for every capture of this run: process, executable and the installation it was started against.
[ordered]@{ pid = $p.Id; exe = $p.Path; started = $p.StartTime.ToString('s'); attach = [bool]$Attach;
  manifest = $(if ($Attach) { 'inherited from the -KeepOpen run of this PID' } else { $Manifest }) } |
  ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $OutDir ("capture_run_{0}_{1}.json" -f $p.Id, (Get-Date -Format 'HHmmss')))
Write-Host "pid $($p.Id)"
[W]::MoveWindow($h, 40, 40, $Width, $Height, $true) | Out-Null
if (-not $Attach) { Start-Sleep -Seconds 6 }

function Shot([string]$name) {
  $r = New-Object W+RECT; [W]::GetClientRect($h, [ref]$r) | Out-Null
  $w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
  $bmp = New-Object System.Drawing.Bitmap $w, $hh
  # Screen copy of the foreground client area (PrintWindow returned stale frames for this GPU-rendered window).
  Focus
  $pt = New-Object W+PT; [W]::ClientToScreen($h, [ref]$pt) | Out-Null
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($pt.X, $pt.Y, 0, 0, $bmp.Size); $g.Dispose()
  $bmp.Save((Join-Path $OutDir "$name.png"), [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  Write-Host "shot $name"
}
function Focus { [W]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Milliseconds 300 }

foreach ($s in ($Steps -split ';;')) {
  $parts = $s.Split('|')
  switch ($parts[0]) {
    'type' { Focus; [System.Windows.Forms.SendKeys]::SendWait($parts[1]); Start-Sleep -Milliseconds 300 }
    'click' {
      Focus
      $xy = $parts[1].Split(','); $pt = New-Object W+PT; $pt.X = [int]$xy[0]; $pt.Y = [int]$xy[1]
      [W]::ClientToScreen($h, [ref]$pt) | Out-Null
      [W]::SetCursorPos($pt.X, $pt.Y) | Out-Null; Start-Sleep -Milliseconds 150
      [W]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero); [W]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero)
      Start-Sleep -Milliseconds 400
    }
    'wait' { Start-Sleep -Milliseconds ([int]$parts[1]) }
    'shot' { Shot $parts[2] }
  }
}
if (-not $KeepOpen) { $p.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 3; if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force } }
