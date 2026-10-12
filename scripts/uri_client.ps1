[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Manifest,
    [ValidateSet('validate', 'launch', 'status')][string]$Action = 'launch',
    [switch]$Headless
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    $sourceRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
    $interpreter = Join-Path $sourceRoot '.venv\Scripts\python.exe'
    $manifestPath = (Resolve-Path -LiteralPath $Manifest).Path
    $config = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ([System.IO.Path]::GetFullPath($config.interpreter) -ne $interpreter) { throw 'INTERPRETER_MISMATCH' }
    $stream = [System.IO.File]::Open($interpreter, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try { $hash = [System.BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $hasher.Dispose() }
    if ($hash -ne $config.interpreter_sha256) { throw 'INTERPRETER_HASH' }
    $arguments = @('-B', '-I', (Join-Path $PSScriptRoot 'uri_client_launcher.py'), $Action, '--manifest', $manifestPath)
    if ($Headless) { $arguments += '--headless' }
    if ($Headless -and $Action -eq 'launch') {
        # Windows PowerShell 5.1's native pipeline decodes/re-encodes stdout,
        # corrupting binary frame headers. Bridge raw streams instead.
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = $interpreter
        $start.Arguments = (($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' ')
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.RedirectStandardInput = $true
        $start.RedirectStandardOutput = $true
        $start.RedirectStandardError = $true
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $start
        [void]$process.Start()
        $outputTask = $process.StandardOutput.BaseStream.CopyToAsync([Console]::OpenStandardOutput())
        $errorTask = $process.StandardError.BaseStream.CopyToAsync([Console]::OpenStandardError())
        $inputTask = [Console]::OpenStandardInput().CopyToAsync($process.StandardInput.BaseStream)
        [void]$inputTask.GetAwaiter().GetResult()
        $process.StandardInput.Close()
        [void]$outputTask.GetAwaiter().GetResult()
        [void]$errorTask.GetAwaiter().GetResult()
        $process.WaitForExit()
        exit $process.ExitCode
    }
    & $interpreter @arguments
    exit $LASTEXITCODE
} catch {
    Write-Output '{"result":"REFUSED","code":"CLIENT_LAUNCH_PREFLIGHT_REFUSED"}'
    exit 1
}
