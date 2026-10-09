# Synthesises the deterministic speech fixtures used by the voice waveform
# tests, captures and performance runs.
#
# The audio is real synthesised speech from Windows System.Speech, which is the
# engine URI's opt-in desktop voice adapter already uses for output. The words
# are scripted, so every fixture is SIMULATED as a session: it proves the
# waveform responds to genuine speech audio, not that a live microphone or a
# live URI reply was wired. The "user" clip is a different installed voice
# standing in for a person; no human voice is recorded.
#
# Output per clip: <name>.wav (16 kHz mono PCM16) and <name>.timing.json
# (one entry per word: character offset, length, audio offset in ms), taken
# from the synthesiser's own SpeakProgress events.
#
# Run: powershell -NoProfile -File rnd/voice/make_fixtures.ps1
param([string]$Out = (Join-Path $PSScriptRoot '..\..\uri_ui\test\fixtures\voice'))
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$clips = @(
  @{ name = 'user_request'; voice = 'female';
     text = 'URI, draft a short reply to Mr Rai and tell him the report is ready on Friday.' },
  @{ name = 'uri_reply'; voice = 'male';
     text = 'I have drafted the reply to Mr Rai. It is in your documents, and nothing has been sent yet. Would you like me to read it?' }
)

$voices = (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() |
  ForEach-Object { $_.VoiceInfo }
Write-Output ('installed voices: ' + (($voices | ForEach-Object { $_.Name + '/' + $_.Gender }) -join ', '))

foreach ($c in $clips) {
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $v = $voices | Where-Object { $_.Gender -eq $c.voice } | Select-Object -First 1
  if ($v) { $s.SelectVoice($v.Name) }
  $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono)
  $wav = Join-Path $Out ($c.name + '.wav')
  $s.SetOutputToWaveFile($wav, $fmt)
  $words = New-Object System.Collections.ArrayList
  $handler = Register-ObjectEvent -InputObject $s -EventName SpeakProgress -Action {
    [void]$Event.MessageData.Add(@{
      char = $EventArgs.CharacterPosition; len = $EventArgs.CharacterCount;
      ms = [int]$EventArgs.AudioPosition.TotalMilliseconds; word = $EventArgs.Text })
  } -MessageData $words
  $s.Speak($c.text)
  Start-Sleep -Milliseconds 300
  Unregister-Event -SourceIdentifier $handler.Name
  $voiceName = $s.Voice.Name
  $s.SetOutputToNull(); $s.Dispose()
  # SpeakProgress handlers run on PowerShell's event queue, which does not
  # preserve arrival order. Every entry carries its own character and audio
  # offset, so sorting by character position restores the spoken order.
  $sorted = @($words | Sort-Object { $_.char })
  $json = @{ text = $c.text; voice = $voiceName; source = 'System.Speech SpeakProgress';
             simulated = $true; words = $sorted } | ConvertTo-Json -Depth 4
  [IO.File]::WriteAllText((Join-Path $Out ($c.name + '.timing.json')), $json,
    (New-Object Text.UTF8Encoding($false)))
  Write-Output ("{0}: {1} bytes, {2} words, voice {3}" -f $c.name, (Get-Item $wav).Length, $words.Count, $v.Name)
}
