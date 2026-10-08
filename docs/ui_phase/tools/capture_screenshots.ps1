<#
.SYNOPSIS
  Captures the Living Companion preview in each form, from the real
  Windows build, into docs/ui_phase/screenshots/.

.DESCRIPTION
  Repeatable evidence for UI_TEST_EVIDENCE.md. Launches the release exe
  built by `flutter build windows -t lib/main_living.dart` once per
  scenario with the local demo environment variables documented in
  lib/main_living.dart, resizes the window with user32, waits for the
  first frames, captures the client area with System.Drawing, and kills
  the process. No server, no network, no shared preference keys other
  than uri.living.*.

.PARAMETER Exe
  Path to uri_ui.exe (default: the release build output).
#>
param(
  [string]$Exe = (Join-Path $PSScriptRoot "..\..\..\uri_ui\build\windows\x64\runner\Release\uri_ui.exe"),
  [string]$OutDir = (Join-Path $PSScriptRoot "..\screenshots"),
  [int]$SettleMs = 6500
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win32 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct PT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref PT p);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int x, int y, int w, int h, bool repaint);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr SetFocus(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
}
"@

$scenarios = @(
  @{ name = "01_companion_idle";        w = 460;  h = 720;  env = @{ URI_LIVING_START_MODE = "companion" } },
  @{ name = "02_companion_working";     w = 460;  h = 720;  env = @{ URI_LIVING_START_MODE = "companion"; URI_LIVING_DEMO_STATE = "working" } },
  @{ name = "03_companion_approval";    w = 460;  h = 720;  env = @{ URI_LIVING_START_MODE = "companion"; URI_LIVING_DEMO_STATE = "awaitingApproval" } },
  @{ name = "04_workspace_conversation";w = 1400; h = 900;  env = @{ URI_LIVING_START_MODE = "workspace"; URI_LIVING_START_FOCUS = "conversation" } },
  @{ name = "05_workspace_tasks";       w = 1400; h = 900;  env = @{ URI_LIVING_START_MODE = "workspace"; URI_LIVING_START_FOCUS = "tasks"; URI_LIVING_DEMO_STATE = "thinking" } },
  @{ name = "06_workspace_documents";   w = 1400; h = 900;  env = @{ URI_LIVING_START_MODE = "workspace"; URI_LIVING_START_FOCUS = "documents" } },
  @{ name = "07_workspace_intelligence";w = 1400; h = 900;  env = @{ URI_LIVING_START_MODE = "workspace"; URI_LIVING_START_FOCUS = "intelligence" } },
  @{ name = "08_workspace_settings";    w = 1400; h = 900;  env = @{ URI_LIVING_START_MODE = "workspace"; URI_LIVING_START_FOCUS = "settings" } },
  @{ name = "09_dashboard";             w = 1400; h = 900;  env = @{ URI_LIVING_START_MODE = "dashboard" } },
  @{ name = "10_dashboard_error";       w = 1400; h = 900;  env = @{ URI_LIVING_START_MODE = "dashboard"; URI_LIVING_DEMO_STATE = "error" } },
  @{ name = "11_onboarding";            w = 1100; h = 820;  env = @{ URI_LIVING_SKIP_ONBOARDING = "0" } },
  @{ name = "12_companion_reduced_fx";  w = 460;  h = 720;  env = @{ URI_LIVING_START_MODE = "companion"; URI_LIVING_REDUCED_EFFECTS = "1"; URI_LIVING_DEMO_STATE = "success" } },
  @{ name = "13_workspace_narrow";      w = 900;  h = 700;  env = @{ URI_LIVING_START_MODE = "workspace"; URI_LIVING_START_FOCUS = "tasks" } }
)

if (-not (Test-Path $Exe)) { throw "exe not found: $Exe (run flutter build windows -t lib/main_living.dart)" }
New-Item -ItemType Directory -Force $OutDir | Out-Null

foreach ($s in $scenarios) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = (Resolve-Path $Exe).Path
  $psi.WorkingDirectory = Split-Path $psi.FileName
  $psi.UseShellExecute = $false
  $psi.EnvironmentVariables["URI_LIVING_SKIP_ONBOARDING"] = "1"
  foreach ($k in $s.env.Keys) { $psi.EnvironmentVariables[$k] = $s.env[$k] }
  $p = [System.Diagnostics.Process]::Start($psi)
  try {
    $deadline = (Get-Date).AddSeconds(20)
    while ($p.MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 200; $p.Refresh() }
    if ($p.MainWindowHandle -eq 0) { throw "no window for $($s.name)" }
    [Win32]::MoveWindow($p.MainWindowHandle, 40, 40, $s.w, $s.h, $true) | Out-Null
    [Win32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds $SettleMs
    $r = New-Object Win32+RECT
    [Win32]::GetClientRect($p.MainWindowHandle, [ref]$r) | Out-Null
    $pt = New-Object Win32+PT
    [Win32]::ClientToScreen($p.MainWindowHandle, [ref]$pt) | Out-Null
    $bmp = New-Object System.Drawing.Bitmap($r.Right, $r.Bottom)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    # PrintWindow with PW_CLIENTONLY|PW_RENDERFULLCONTENT (3) reads the
    # window's own composed surface, so other always-on-top windows on
    # the desktop never appear in the evidence.
    $hdc = $g.GetHdc()
    [Win32]::PrintWindow($p.MainWindowHandle, $hdc, 3) | Out-Null
    $g.ReleaseHdc($hdc)
    $out = Join-Path $OutDir ($s.name + ".png")
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Output ("captured {0} ({1}x{2})" -f $s.name, $r.Right, $r.Bottom)
  } finally {
    if (-not $p.HasExited) { $p.Kill(); $p.WaitForExit(5000) }
  }
}
