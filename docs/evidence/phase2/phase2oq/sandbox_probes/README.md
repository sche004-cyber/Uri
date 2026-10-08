# Codex 0.158.0 Windows sandbox probes (2026-10-08, operational qualification, EXE-1)

Scratch client profile (fresh CODEX_HOME, no login), native `codex.exe` from the npm vendor directory, sanitized
worker-like environment (PATH = venv, System32, git), scripted local Responses endpoint (`fakeresp*.py`, 127.0.0.1).

1. No `[windows] sandbox` mode in the client profile: every `exec_command` of a `--sandbox workspace-write` run is
   refused ("rejected: blocked by policy") - observed in the first run (see the main report).
2. `-c windows.sandbox="unelevated"`: write inside the workspace succeeded (`pong.txt` = PONG); write to the parent
   directory was denied ("Access to the path ... is denied") - `req2.log`.
3. `-c windows.sandbox="unelevated"`: network is NOT confined. The sandboxed PowerShell fetched
   `http://127.0.0.1:18999/sandbox-net-probe` (the endpoint logged the GET; output bytes spell "reached") and
   `http://example.com/` returned status 200 - `req3.log`. Codex's own strings state network restriction requires
   the elevated backend; the elevated backend was NOT tested (it needs a one-time administrator setup = owner).
