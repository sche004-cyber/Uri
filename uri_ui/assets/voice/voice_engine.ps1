<#
  URI voice engine bridge for the client (Windows only).

  The client runs this file (a bundled asset) with -EncodedCommand, so every
  input arrives through environment variables and nothing a voice is called can
  be interpreted as script:

    URI_VOICE_VERB    list | speak | render
    URI_VOICE_ENGINE  sapi | onecore
    URI_VOICE_NAME    the voice's display name
    URI_VOICE_RATE    -10..10   URI_VOICE_PITCH -10..10   URI_VOICE_VOLUME 0..100
    URI_VOICE_TEXT    text to say (speak/render)
    URI_VOICE_OUT     WAV path (render only)

  list   prints every installed voice as one JSON array.
  speak  plays the text through the default output device.
  render writes a 16-bit WAV instead (used by rnd/companions/settings/
         measure_voice_params.py to verify, per engine, which parameters
         really change the audio).

  Engines: 'sapi' = System.Speech (the engine URI's voice architecture
  designates), 'onecore' = Windows.Media.SpeechSynthesis (WinRT). Both are local
  and offline; nothing is downloaded.
#>
$ErrorActionPreference = 'Stop'
$Verb = [Environment]::GetEnvironmentVariable('URI_VOICE_VERB')
$Text = [Environment]::GetEnvironmentVariable('URI_VOICE_TEXT')
if (-not $Text) { $Text = "Hello. I'm URI, and this is how I sound." }
$OutFile = [Environment]::GetEnvironmentVariable('URI_VOICE_OUT')
if ($Verb -notin @('list', 'speak', 'render')) { throw "unknown verb: $Verb" }

function Get-IntEnv([string]$name, [int]$fallback, [int]$lo, [int]$hi) {
  $raw = [Environment]::GetEnvironmentVariable($name)
  $v = 0
  if (-not [int]::TryParse("$raw", [ref]$v)) { return $fallback }
  return [Math]::Max($lo, [Math]::Min($hi, $v))
}

function Load-OneCore {
  [void][Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
}

function Await-WinRT($op, [Type]$resultType) {
  $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
      $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
    Select-Object -First 1
  $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($op))
  [void]$task.Wait(-1)
  return $task.Result
}

if ($Verb -eq 'list') {
  $out = New-Object System.Collections.ArrayList
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  foreach ($v in $s.GetInstalledVoices()) {
    $i = $v.VoiceInfo
    [void]$out.Add([ordered]@{ engine = 'sapi'; name = $i.Name; culture = $i.Culture.Name; gender = "$($i.Gender)"; enabled = [bool]$v.Enabled })
  }
  $s.Dispose()
  try {
    Load-OneCore
    foreach ($v in [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices) {
      [void]$out.Add([ordered]@{ engine = 'onecore'; name = $v.DisplayName; culture = $v.Language; gender = "$($v.Gender)"; enabled = $true })
    }
  } catch {
    [void]$out.Add([ordered]@{ engine = 'onecore'; name = ''; culture = ''; gender = ''; enabled = $false; error = $_.Exception.Message })
  }
  ConvertTo-Json -InputObject @($out) -Compress -Depth 3
  exit 0
}

$engine = [Environment]::GetEnvironmentVariable('URI_VOICE_ENGINE')
$name = [Environment]::GetEnvironmentVariable('URI_VOICE_NAME')
$rate = Get-IntEnv 'URI_VOICE_RATE' 0 -10 10
$pitch = Get-IntEnv 'URI_VOICE_PITCH' 0 -10 10
$volume = Get-IntEnv 'URI_VOICE_VOLUME' 100 0 100
if ($Verb -eq 'render' -and -not $OutFile) { throw 'render needs -OutFile' }

if ($engine -eq 'sapi') {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  try {
    if ($name) { $s.SelectVoice($name) }
    $s.Rate = $rate
    $s.Volume = $volume
    if ($Verb -eq 'render') { $s.SetOutputToWaveFile($OutFile) } else { $s.SetOutputToDefaultAudioDevice() }
    if ($pitch -ne 0) {
      # SAPI has no pitch property; SSML prosody is the only route. Whether a
      # voice honours it is measured by measure_voice_params.py, not assumed.
      $pb = New-Object System.Speech.Synthesis.PromptBuilder
      $style = New-Object System.Speech.Synthesis.PromptStyle
      $ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"><prosody pitch="{0}%">{1}</prosody></speak>' -f `
        ($(if ($pitch -gt 0) { '+' } else { '' }) + ($pitch * 5)), [System.Security.SecurityElement]::Escape($Text)
      $s.SpeakSsml($ssml)
    } else {
      $s.Speak($Text)
    }
  } finally { $s.Dispose() }
  exit 0
}

if ($engine -eq 'onecore') {
  Load-OneCore
  $syn = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
  if ($name) {
    $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -eq $name } | Select-Object -First 1
    if (-not $voice) { throw "voice not installed: $name" }
    $syn.Voice = $voice
  }
  # Rate: 2^(r/10) gives 0.5x..2x; pitch: 1 + p*0.05 gives 0.5..1.5.
  $syn.Options.SpeakingRate = [Math]::Pow(2, $rate / 10.0)
  $syn.Options.AudioPitch = 1 + $pitch * 0.05
  $syn.Options.AudioVolume = $volume / 100.0
  $stream = Await-WinRT ($syn.SynthesizeTextToStreamAsync($Text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
  $target = $OutFile
  if (-not $target) { $target = Join-Path $env:TEMP ("uri_voice_preview_{0}.wav" -f [guid]::NewGuid().ToString('N')) }
  $in = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
  $fs = [System.IO.File]::Create($target)
  try { $in.CopyTo($fs) } finally { $fs.Dispose(); $in.Dispose(); $stream.Dispose(); $syn.Dispose() }
  if ($Verb -eq 'speak') {
    try { (New-Object System.Media.SoundPlayer $target).PlaySync() } finally { Remove-Item -LiteralPath $target -ErrorAction SilentlyContinue }
  }
  exit 0
}

throw "unknown engine: $engine"
