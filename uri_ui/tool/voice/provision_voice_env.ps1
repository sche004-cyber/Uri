<#
  Provisions URI's live voice runtime for the current user (no elevation).

    powershell -NoProfile -ExecutionPolicy Bypass -File uri_ui\tool\voice\provision_voice_env.ps1 [-Python <python.exe>] [-Check]

  * Creates %LOCALAPPDATA%\URI\voice\venv with the exact package versions in
    requirements-voice.txt (pip; packages come from the local pip cache or PyPI).
  * Does NOT download a speech model. The recogniser uses the hash-pinned
    faster-whisper base.en files at %LOCALAPPDATA%\URI\models\faster-whisper-base.en
    (URI_MODEL_MANIFEST.json). If they are missing, the script says so and stops:
    fetching a model is an owner decision.
  * -Check only reports what is installed; it changes nothing.
  * Changes no Windows setting, no PATH, no registry, nothing outside
    %LOCALAPPDATA%\URI\voice.
#>
param(
  [string]$Python = '',
  [switch]$Check
)
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA 'URI\voice'
$venv = Join-Path $root 'venv'
$venvPy = Join-Path $venv 'Scripts\python.exe'
$req = Join-Path $PSScriptRoot 'requirements-voice.txt'
$model = Join-Path $env:LOCALAPPDATA 'URI\models\faster-whisper-base.en'

function Report {
  $state = [ordered]@{
    venv = (Test-Path $venvPy)
    model_manifest = (Test-Path (Join-Path $model 'URI_MODEL_MANIFEST.json'))
    model_bin = (Test-Path (Join-Path $model 'model.bin'))
  }
  if ($state.venv) {
    $state.packages = (& $venvPy -I -c "import faster_whisper, ctranslate2, sounddevice, numpy; print(faster_whisper.__version__, ctranslate2.__version__, sounddevice.__version__, numpy.__version__)" 2>&1) -join ' '
  }
  $state | ConvertTo-Json -Compress
}

if ($Check) { Report; exit 0 }

if (-not (Test-Path (Join-Path $model 'URI_MODEL_MANIFEST.json'))) {
  Write-Error "Speech model not found at $model. Provisioning stops here: downloading a model needs the owner's decision."
}

if (-not (Test-Path $venvPy)) {
  if (-not $Python) {
    $cand = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
    if (Test-Path $cand) { $Python = $cand } else { Write-Error 'Python 3.13 not found; pass -Python <path to python.exe>.' }
  }
  New-Item -ItemType Directory -Force $root | Out-Null
  & $Python -m venv $venv
  if ($LASTEXITCODE -ne 0) { Write-Error 'venv creation failed' }
}
& $venvPy -I -m pip install --disable-pip-version-check --no-input -r $req
if ($LASTEXITCODE -ne 0) { Write-Error 'package installation failed' }
Report
