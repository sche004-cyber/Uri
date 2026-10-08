[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Manifest,
    [ValidateSet('start', 'status', 'validate')][string]$Action = 'start',
    [ValidateRange(1, 60)][int]$TimeoutSeconds = 30
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$stage = 'manifest'
try {
    $sourceRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
    $manifestPath = (Resolve-Path -LiteralPath $Manifest).Path
    $config = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $stage = 'interpreter'
    $interpreter = Join-Path $sourceRoot '.venv\Scripts\python.exe'
    if ([System.IO.Path]::GetFullPath($config.interpreter) -ne $interpreter) { throw 'ISOLATED_INTERPRETER_REQUIRED' }
    $stage = 'interpreter_hash'
    # Venv's Windows redirector keeps its image open while its child runs.
    # Read with sharing; an exclusive FileStream rejects repeated launches.
    $stream = [System.IO.File]::Open($interpreter, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try { $observedHash = [System.BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $hasher.Dispose() }
    if ($observedHash -ne $config.interpreter_sha256) { throw 'INTERPRETER_HASH_MISMATCH' }
    $stage = 'invoke'
    & $interpreter '-B' '-I' (Join-Path $PSScriptRoot 'uri_server_launcher.py') $Action '--manifest' $manifestPath '--timeout' $TimeoutSeconds
    exit $LASTEXITCODE
} catch {
    Write-Output ('{"result":"REFUSED","code":"LAUNCHER_PREFLIGHT_FAILED","stage":"' + $stage + '"}')
    exit 1
}
