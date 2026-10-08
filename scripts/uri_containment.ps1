<#
.SYNOPSIS
    Reversible PC containment for legacy URI launch paths. DEFAULT IS PLAN ONLY (no change).

.DESCRIPTION
    Owner-approval (RED) actions. Nothing changes unless -Apply is given; -Restore undoes a previous -Apply from its
    backup folder. Every action is recorded in <BackupRoot>\containment_log.json before it is made.

    C-1  Disable scheduled task \URIServer (legacy dirty master server on 127.0.0.1:8000). Task XML exported first.
    C-2  Move the two URI.lnk shortcuts that launch the M37-M39 donor desktop into the backup folder (not deleted).
    C-3  Record (do not edit) the uri_ui shared preference serverBaseUrl, so the UI's legacy binding is visible.

    It never stops a running process, never deletes a file, never touches credentials, worktrees or Git.
    The currently running legacy server keeps running until the owner stops it or logs off.

.EXAMPLE
    powershell -NoProfile -File scripts\uri_containment.ps1                 # show the plan
    powershell -NoProfile -File scripts\uri_containment.ps1 -Apply          # perform C-1 and C-2 (owner approval required)
    powershell -NoProfile -File scripts\uri_containment.ps1 -Restore -BackupRoot <folder printed by -Apply>
#>
param(
    [switch]$Apply,
    [switch]$Restore,
    [string]$BackupRoot = (Join-Path $env:USERPROFILE ("Development\uri-canonical-evidence\containment_" + (Get-Date -Format 'yyyyMMdd_HHmmss')))
)
$ErrorActionPreference = 'Stop'
$TaskName = 'URIServer'
$Shortcuts = @(
    (Join-Path $env:USERPROFILE 'OneDrive\Desktop\URI.lnk'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\URI.lnk')
)
$Prefs = Join-Path $env:APPDATA 'com.example\uri_ui\shared_preferences.json'

function Plan {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    "C-1 scheduled task \$TaskName : " + $(if ($t) { "present, state=$($t.State) -> would DISABLE (XML backup first)" } else { 'absent (nothing to do)' })
    foreach ($s in $Shortcuts) { "C-2 shortcut $s : " + $(if (Test-Path $s) { 'present -> would MOVE into backup folder' } else { 'absent' }) }
    if (Test-Path $Prefs) { $u = (Get-Content $Prefs -Raw | ConvertFrom-Json).'flutter.uri.serverBaseUrl'; "C-3 uri_ui serverBaseUrl = $u (recorded only; tokens never read)" }
}

if ($Restore) {
    $log = Join-Path $BackupRoot 'containment_log.json'
    if (-not (Test-Path $log)) { throw "No containment log at $log" }
    $entries = Get-Content $log -Raw | ConvertFrom-Json
    foreach ($e in $entries) {
        switch ($e.action) {
            'disable_task' { Enable-ScheduledTask -TaskName $e.task | Out-Null; "restored: enabled task $($e.task)" }
            'move_shortcut' { Move-Item -LiteralPath $e.backup -Destination $e.original; "restored: $($e.original)" }
        }
    }
    return
}

if (-not $Apply) { "PLAN ONLY (no changes). Re-run with -Apply after owner approval."; Plan; return }

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$log = @()
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($t) {
    Export-ScheduledTask -TaskName $TaskName | Set-Content -Encoding Unicode (Join-Path $BackupRoot "$TaskName.xml")
    $log += [pscustomobject]@{ action = 'disable_task'; task = $TaskName; previous_state = "$($t.State)" }
    $log | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 (Join-Path $BackupRoot 'containment_log.json')
    Disable-ScheduledTask -TaskName $TaskName | Out-Null
    "C-1 disabled \$TaskName (XML at $BackupRoot)"
}
$i = 0
foreach ($s in $Shortcuts) {
    if (Test-Path $s) {
        $i++; $dest = Join-Path $BackupRoot ("shortcut_{0}_{1}" -f $i, (Split-Path $s -Leaf))
        $log += [pscustomobject]@{ action = 'move_shortcut'; original = $s; backup = $dest }
        $log | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 (Join-Path $BackupRoot 'containment_log.json')
        Move-Item -LiteralPath $s -Destination $dest
        "C-2 moved $s -> $dest"
    }
}
"Backup folder: $BackupRoot  (undo: -Restore -BackupRoot `"$BackupRoot`")"
