# Explicit provisional mode of the existing URI application. No production promotion.
$ErrorActionPreference = 'Stop'
$HarnessRepo = Split-Path -Parent $PSScriptRoot
$HarnessExe = Join-Path $HarnessRepo 'uri_ui\build\windows\x64\runner\Debug\uri_ui.exe'
$HarnessState = Join-Path $HarnessRepo 'scratch\candidate_desktop_state'
$HarnessHealth = 'http://127.0.0.1:8021/health'
try {
    if (-not (Test-Path -LiteralPath $HarnessExe)) { throw 'Provisional desktop build is missing.' }
    $healthy = $false
    try { Invoke-RestMethod -Uri $HarnessHealth -TimeoutSec 2 | Out-Null; $healthy = $true } catch {}
    if (-not $healthy) {
        $HarnessPython = (Get-Command python -ErrorAction Stop).Source
        New-Item -ItemType Directory -Force -Path $HarnessState | Out-Null
        $HarnessServer = Join-Path $PSScriptRoot 'run_desktop_harness_test.py'
        Start-Process -FilePath $HarnessPython -ArgumentList @('"' + $HarnessServer + '"',
            '--enable-subscription-test', '--port', '8021', '--state-dir', '"' + $HarnessState + '"') `
            -WorkingDirectory $HarnessRepo -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $HarnessState 'launcher.stdout.log') `
            -RedirectStandardError (Join-Path $HarnessState 'launcher.stderr.log') | Out-Null
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Seconds 1
            try { Invoke-RestMethod -Uri $HarnessHealth -TimeoutSec 2 | Out-Null; $healthy = $true; break } catch {}
        }
        if (-not $healthy) { throw 'Provisional Core did not become reachable. See scratch/desktop_harness_test_state/launcher.stderr.log.' }
    }
    # Identify this composition; do not accidentally connect to an unrelated loopback server.
    $schema = Invoke-RestMethod -Uri 'http://127.0.0.1:8021/openapi.json' -TimeoutSec 3
    if ($null -eq $schema.paths.'/desktop/harness-test/providers') { throw 'Port 8021 belongs to another server.' }
    $running = Get-Process uri_ui -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $HarnessExe }
    if (-not $running) {
        # This is the interactive application the User asked to see.
        Start-Process -FilePath $HarnessExe -WorkingDirectory (Split-Path -Parent $HarnessExe)
    }
    exit 0
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'URI Harness Management') | Out-Null
    exit 1
}
