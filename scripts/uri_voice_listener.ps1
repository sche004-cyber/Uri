param(
    [Parameter(Mandatory=$true)][string]$StateDirectory,
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [ValidateRange(5,60)][int]$CommandTimeoutSeconds = 15
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class UriVoiceDesktop {
 [DllImport("user32.dll", SetLastError=true)] static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
 [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern bool GetUserObjectInformation(IntPtr handle, int index, StringBuilder info, int length, out int needed);
 public static bool Unlocked() {
  var desktop = OpenInputDesktop(0, false, 1);
  if (desktop == IntPtr.Zero) return false;
  try { int needed; var name = new StringBuilder(128); return GetUserObjectInformation(desktop, 2, name, 256, out needed) && name.ToString() == "Default"; }
  finally { CloseDesktop(desktop); }
 }
}
'@
$taskSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$taskMutex = New-Object System.Threading.Mutex($false, ('Local\URI_Voice_' + $taskSid.Value))
$taskOwned = $false
$taskRecognizer = $null
$taskSpeaker = $null
$taskSequence = 0
$taskLastTest = ''
$taskStatusPath = Join-Path $StateDirectory 'status.json'
function Publish-Voice([string]$State, [string]$Kind = '', [string]$Text = '') {
 $script:taskSequence++
 $taskPayload = @{state=$State;kind=$Kind;text=$Text;sequence=$script:taskSequence;timestamp=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()}
 $taskTemp = Join-Path $StateDirectory 'status.tmp'
 [IO.File]::WriteAllText($taskTemp, ($taskPayload | ConvertTo-Json -Compress), (New-Object Text.UTF8Encoding($false)))
 # Replace atomically; a short-lived UI read must not terminate recognition.
 for ($taskAttempt=0; $taskAttempt -lt 10; $taskAttempt++) {
  try {
   if ([IO.File]::Exists($taskStatusPath)) { [IO.File]::Replace($taskTemp, $taskStatusPath, [NullString]::Value) }
   else { [IO.File]::Move($taskTemp, $taskStatusPath) }
   return
  } catch {
   if ($_.Exception.GetBaseException() -isnot [IO.IOException] -or $taskAttempt -eq 9) { throw }
   Start-Sleep -Milliseconds 20
  }
 }
}
function Read-Control {
 try { return (Get-Content -LiteralPath (Join-Path $StateDirectory 'control.json') -Raw | ConvertFrom-Json) } catch { return $null }
}
function Control-Ready($Control) {
 return ($null -ne $Control -and $Control.ready -and -not $Control.muted -and ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() - [long]$Control.timestamp) -lt 6000)
}
try {
 # The previous app's bounded recognition call can still be unwinding.
 # Wait once; never create a second microphone owner.
 try { $taskOwned = $taskMutex.WaitOne(10000) }
 catch [System.Threading.AbandonedMutexException] { $taskOwned = $true }
 if (-not $taskOwned) { exit 2 }
 # Private per-launch transport, no transcript history or credentials.
 $taskAllowedRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'URI\voice')) + [IO.Path]::DirectorySeparatorChar
 $taskResolved = [IO.Path]::GetFullPath($StateDirectory)
 if (-not $taskResolved.StartsWith($taskAllowedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid voice state directory' }
 New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
 $taskAcl = New-Object System.Security.AccessControl.DirectorySecurity
 $taskAcl.SetAccessRuleProtection($true,$false)
 $taskAcl.SetOwner($taskSid)
 $taskRule = New-Object System.Security.AccessControl.FileSystemAccessRule($taskSid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
 $taskAcl.AddAccessRule($taskRule)
 [IO.Directory]::SetAccessControl($StateDirectory, $taskAcl)
 $taskRecognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine([Globalization.CultureInfo]::GetCultureInfo('en-US'))
 $taskChoices = New-Object System.Speech.Recognition.Choices
 $taskChoices.Add([string[]]@('Oii URI','Oi URI','Oii you are eye'))
 $taskBuilder = New-Object System.Speech.Recognition.GrammarBuilder
 $taskBuilder.Culture = $taskRecognizer.RecognizerInfo.Culture
 $taskBuilder.Append($taskChoices)
 $taskWake = New-Object System.Speech.Recognition.Grammar($taskBuilder)
 $taskRecognizer.SetInputToDefaultAudioDevice()
 $taskSpeaker = New-Object -ComObject SAPI.SpVoice
 if ($env:URI_VOICE_SPEAKER) {
  $taskOutputs = $taskSpeaker.GetAudioOutputs()
  $taskSelectedOutput = $null
  for ($taskIndex=0; $taskIndex -lt $taskOutputs.Count; $taskIndex++) {
   $taskOutput = $taskOutputs.Item($taskIndex)
   if ($taskOutput.GetDescription() -eq $env:URI_VOICE_SPEAKER) { $taskSelectedOutput = $taskOutput; break }
  }
  if (-not $taskSelectedOutput) { throw 'Configured speech output is unavailable' }
  $taskSpeaker.AudioOutput = $taskSelectedOutput
 }
 $taskSpeakerName = $taskSpeaker.AudioOutput.GetDescription()
 Publish-Voice 'Ready'
 while (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue) {
  $taskControl = Read-Control
  if (-not [UriVoiceDesktop]::Unlocked()) { $taskRecognizer.SetInputToNull(); Publish-Voice 'Locked'; Start-Sleep -Milliseconds 500; continue }
  if (-not (Control-Ready $taskControl)) { $taskRecognizer.SetInputToNull(); Publish-Voice $(if ($taskControl.muted) {'Muted'} else {'Sign in or finish the current turn'}); Start-Sleep -Milliseconds 500; continue }
  $taskRecognizer.SetInputToDefaultAudioDevice()
  $taskRecognizer.UnloadAllGrammars()
  $taskRecognizer.LoadGrammar($taskWake)
  Publish-Voice ('Waiting for Oii URI | Speech: ' + $taskSpeakerName)
  $taskManual = $taskControl.test -and $taskControl.test -ne $taskLastTest
  if ($taskManual) { $taskLastTest = $taskControl.test; $taskHeard = $null }
  else { $taskHeard = $taskRecognizer.Recognize([TimeSpan]::FromSeconds(2)) }
  # Recheck controls/session after a blocking recognition call.
  if (-not (Control-Ready (Read-Control)) -or -not [UriVoiceDesktop]::Unlocked()) { continue }
  if (-not $taskManual -and ($null -eq $taskHeard -or $taskHeard.Confidence -lt 0.65)) { continue }
  $taskRecognizer.SetInputToNull()
  Publish-Voice 'Responding' 'wake'
  $taskSpeaker.Speak('Yes Chetan.', 0) | Out-Null
  Start-Sleep -Milliseconds 300
  # Wake remains lightweight; command STT is a bounded CPU-only child.
  Publish-Voice 'Listening for your instruction'
  $taskPython = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv_voice\Scripts\python.exe'
  $taskTranscribe = Join-Path $PSScriptRoot 'uri_voice_transcribe.py'
  if (-not (Test-Path -LiteralPath $taskPython)) { Publish-Voice 'Command recognition unavailable: voice runtime not installed' 'error'; Start-Sleep -Seconds 2; continue }
  $taskReceipt = Join-Path $StateDirectory 'transcript.json'
  Remove-Item -LiteralPath $taskReceipt -ErrorAction SilentlyContinue
  $taskChild = Start-Process -FilePath $taskPython -ArgumentList @(('"'+$taskTranscribe+'"'),'--directory',('"'+$StateDirectory+'"'),'--timeout',$CommandTimeoutSeconds) -PassThru -WindowStyle Hidden
  $taskPeakMemory = 0
  $taskDeadline = [DateTime]::UtcNow.AddSeconds($CommandTimeoutSeconds + 30)
  while (-not $taskChild.HasExited -and [DateTime]::UtcNow -lt $taskDeadline) {
   if (-not (Control-Ready (Read-Control)) -or -not [UriVoiceDesktop]::Unlocked() -or -not (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) { $taskChild.Kill(); break }
   Start-Sleep -Milliseconds 150
   $taskChild.Refresh()
   if (-not $taskChild.HasExited) { $taskPeakMemory = [Math]::Max($taskPeakMemory, $taskChild.WorkingSet64) }
  }
  if (-not $taskChild.HasExited) { $taskChild.Kill(); Publish-Voice 'Command recognition timed out' 'error' }
  elseif ($taskChild.ExitCode -ne 0) { Publish-Voice 'Command recognition failed; check microphone/runtime' 'error' }
  elseif ((Test-Path -LiteralPath $taskReceipt) -and (Control-Ready (Read-Control)) -and [UriVoiceDesktop]::Unlocked()) {
   $taskTranscript = Get-Content -LiteralPath $taskReceipt -Raw | ConvertFrom-Json
   if ($taskTranscript.text) { Publish-Voice 'Sending instruction' 'command' $taskTranscript.text }
   else { Publish-Voice 'No instruction heard; try again' }
   # Non-sensitive resource evidence; audio never written to disk.
   @{stt_ms=$taskTranscript.stt_ms;model_load_ms=$taskTranscript.model_load_ms;audio_seconds=$taskTranscript.audio_seconds;peak_ram_bytes=$taskTranscript.peak_ram_bytes;timestamp=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()} | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $StateDirectory 'metrics.json')
  }
  Remove-Item -LiteralPath $taskReceipt -ErrorAction SilentlyContinue
  Start-Sleep -Milliseconds 1200
 }
} catch {
 if (Test-Path -LiteralPath $StateDirectory) { Publish-Voice ('Voice unavailable: ' + $_.Exception.Message) 'error' }
 exit 1
} finally {
 if ($taskRecognizer) { $taskRecognizer.Dispose() }
 if ($taskSpeaker) { [Runtime.InteropServices.Marshal]::ReleaseComObject($taskSpeaker) | Out-Null }
 if ($taskChild -and -not $taskChild.HasExited) { $taskChild.Kill() }
 if ($taskOwned) { $taskMutex.ReleaseMutex() }
 $taskMutex.Dispose()
}
