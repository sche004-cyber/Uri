<#
.SYNOPSIS
    Start-up gate for the authoritative URI runtime. Refuses to start while any unauthorized URI runtime is active.

.DESCRIPTION
    1. Runs scripts\uri_runtime_authority_check.py in --strict mode (TRANSITIONAL_LEGACY also fails).
    2. Only on exit 0 delegates to the frozen C1 launcher in the materialized runtime checkout named by the
       manifest: <runtime>\scripts\uri_server.ps1 <Action>. The frozen launcher then performs its own signed
       identity, source-pin, interpreter-pin and port checks.
    This wrapper never stops, adopts or edits anything. Use -Action validate|status|start.
#>
param([ValidateSet('validate','status','start')][string]$Action = 'validate', [string]$ServerManifest)
$ErrorActionPreference = 'Stop'
$dev = Split-Path -Parent $PSScriptRoot
$authority = Join-Path $dev 'docs\governance\URI_RUNTIME_AUTHORITY_MANIFEST.json'
$m = Get-Content $authority -Raw | ConvertFrom-Json
$runtime = $m.authoritative_runtime.source_checkout_candidate -replace '/', '\'
$py = Join-Path $runtime '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Authoritative runtime interpreter missing: $py" }
& $py (Join-Path $dev 'scripts\uri_runtime_authority_check.py') --manifest $authority --strict
if ($LASTEXITCODE -ne 0) {
    Write-Host "REFUSED: an unauthorized or transitional URI runtime is active or set to auto-start (see report above). Contain it first (scripts\uri_containment.ps1, owner approval)."
    exit 3
}
if (-not $ServerManifest) { throw 'Provide -ServerManifest <provisioned C1 server manifest.json> (scripts\provision_uri_server.py output).' }
$launcher = Join-Path $runtime 'scripts\uri_server.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File $launcher -Manifest $ServerManifest -Action $Action
exit $LASTEXITCODE
