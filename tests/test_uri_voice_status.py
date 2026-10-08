"""Exercise Windows status replacement while a reader holds the file."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows voice transport')
class VoiceStatusTest(unittest.TestCase):
    def test_reader_collision_does_not_stop_publication(self):
        with tempfile.TemporaryDirectory(prefix='uri_voice_status_') as directory:
            environment = dict(os.environ, URI_STATUS_TEST_DIRECTORY=directory,
                URI_STATUS_TEST_SCRIPT=str(Path(__file__).resolve().parents[1] /
                    'scripts/uri_voice_listener.ps1'))
            script = r'''
$ErrorActionPreference = 'Stop'
$StateDirectory = $env:URI_STATUS_TEST_DIRECTORY
$taskStatusPath = Join-Path $StateDirectory 'status.json'
$taskSequence = 0
$ast = [Management.Automation.Language.Parser]::ParseFile($env:URI_STATUS_TEST_SCRIPT, [ref]$null, [ref]$null)
$function = $ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Publish-Voice'}, $true)
Invoke-Expression $function.Extent.Text
Publish-Voice 'Ready'
$marker = Join-Path $StateDirectory 'reader.locked'
$job = Start-Job -ArgumentList $taskStatusPath,$marker -ScriptBlock {
 param($path,$marker)
 # Load the sleep cmdlet before taking the lock: Windows PowerShell's
 # first-use module loading must not extend the simulated reader hold.
 Start-Sleep -Milliseconds 1
 $handle = [IO.File]::Open($path, 'Open', 'Read', 'None')
 try { [IO.File]::WriteAllText($marker,'ready'); Start-Sleep -Milliseconds 120 }
 finally { $handle.Dispose() }
}
try {
 $deadline = [DateTime]::UtcNow.AddSeconds(10)
 while (-not (Test-Path $marker)) {
  if ([DateTime]::UtcNow -gt $deadline) { throw 'Reader did not acquire lock' }
  Start-Sleep -Milliseconds 10
 }
 Publish-Voice 'Responding' 'wake'
 $result = Get-Content $taskStatusPath -Raw | ConvertFrom-Json
 if ($result.sequence -ne 2 -or $result.kind -ne 'wake') { throw 'Lost publication after collision' }
 for ($i=0;$i -lt 100;$i++) { Publish-Voice 'Ready'; $null = Get-Content $taskStatusPath -Raw | ConvertFrom-Json }
 Wait-Job $job | Out-Null
 Receive-Job $job -ErrorAction Stop | Out-Null
} finally { Remove-Job $job -Force }
'''
            result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script],
                env=environment, capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
