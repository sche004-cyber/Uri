Set-Location C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'queue_runs' }) { Start-Sleep 30 }
$env:URI_QUEUE_SET = "3"
& .venv\Scripts\python.exe model_lab\queue_runs.py
