Set-Location C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent
& .venv\Scripts\python.exe model_lab\queue_runs.py qwen35-2b qwen36-35b-a3b qwen38-27b nemotron35-30b-a3b
$env:URI_QUEUE_SET = "2"
& .venv\Scripts\python.exe model_lab\queue_runs.py
