# URI PC Contamination Audit — 2026-10-08

Machine: ChetanPC, Windows 11 Pro. Inspected live between 09:35 and 10:10 IST. Method: read-only queries
(`Get-ScheduledTask`, `Get-CimInstance Win32_Process`, `Get-NetTCPConnection`, shortcut COM targets, Run keys,
services, environment, `pyvenv.cfg`, folder listings, `icacls`). Secret files were located by name only; no secret
value, token or credential file content was read or printed. The machine-readable form of this audit is
`scripts/uri_runtime_authority_check.py` run against `docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json`
(live reports in the evidence folder `C:\Users\cheta\Development\uri-canonical-evidence`).

## 1. Headline findings

| # | Finding | Severity | Can it launch, modify or impersonate URI? |
|---|---|---|---|
| F-1 | Scheduled task `\URIServer` (logon trigger, state Running) starts `C:\Users\cheta\Development\uri-agent\scripts\run_uri_server.py --port 8000` from the **legacy dirty master** checkout with its `.venv`. It is the only URI server running (PIDs 8476 → 13544 → 13660, since 2026-10-07 17:34) | **High** | Yes. It is the de-facto live runtime, writes `uri-agent\uri_workspace` (957 user dirs, 724 MB), and owns 127.0.0.1:8000 at every logon |
| F-2 | Every `uri_ui.exe` build (three on disk: legacy 09-29, integration 10-01, `_V1` 10-04) reads the **same** preferences file `%APPDATA%\com.example\uri_ui\shared_preferences.json`; its `serverBaseUrl` is `http://127.0.0.1:8000`; it also stores session tokens for 8000 and 8021 | **High** | Yes. Opening any UI build directly connects it, with a stored session, to whichever process owns 8000 — today the legacy server — regardless of which checkout the UI came from |
| F-3 | Desktop and Start Menu `URI.lnk` start `uri-m37-m39-integration\Launch URI.bat` (donor desktop line). Its launcher refuses a foreign backend on 8000, so with F-1 active it aborts; if 8000 is free it starts the donor server. If its own `.venv` were missing it would fall back to `uri-agent\.venv` | Medium | Yes (donor server on 8000 when F-1 is not running); cross-installation interpreter fallback |
| F-4 | 33 secret/session files (provider-key master secret `desktop_secrets_*.json`, UI preferences with tokens, `auth_sessions.json`, `user_accounts.json`, `provider_keys.enc`, device identity files in 6 data roots) inherited **read access for `ChetanPC\CodexSandboxUsers`** from the profile ACL | **High (exposure)** | Not a launch path, but any Codex-sandboxed process could read them. **Contained** (§4) |
| F-5 | Runtime state and secrets in `_V1\scratch\desktop_harness_test_state\` and harness-console `scratch\candidate_desktop_state\` were not git-ignored | Medium | Accidental commit path. **Contained** (§4) and never committed (history search: none) |
| F-6 | Legacy launchers still exist inside the Core tree itself (`Launch URI.bat`, `scripts/launch_uri.ps1`, `uri_server_ctl.ps1`, `run_uri_server.py`, base `e8e3b65` files) | Medium | Yes, if double-clicked in any checkout (including the canonical one) they start a legacy-composition server on 8000 with that checkout's `uri_workspace`. Classified forbidden entrypoints; the checker flags them |
| F-7 | `C:\uri-model-lab-nvme` holds byte-identical copies of the Runtime v1 model and projector (research cold-load copy, hashes recorded at copy time) | Low | Only if a launcher pointed there; `local_brain.json` pins `D:\uri-model-lab`. Classified quarantined; the checker flags any process using it |
| F-8 | The Phase 2 development worktree runs real servers/workers during its test chains (other session) | Info | Development activity on non-legacy ports; classified donor/dev, never runtime |

No URI Windows service, no URI Run-key entry, no URI environment variable and no URI entry in the Startup folder
was found.

## 2. Inventory by category

| Category | Observed | Classification |
|---|---|---|
| Git repository | One repository, common dir `uri-agent\.git`, 14 registered worktrees (+4 empty stubs) | see salvage ledger |
| Live URI processes | Legacy server only (F-1) | TRANSITIONAL LEGACY |
| Listening ports | 8000 legacy URI; 11434 Ollama (shared); 1234 LM Studio and 18470 Runtime v1: not listening | — |
| Scheduled tasks | `\URIServer` (F-1). Others are Windows (`appuriverifier*`) false positives | QUARANTINE pending approval |
| Shortcuts | `URI.lnk` ×2 (F-3); `Ollama.lnk` in Startup (shared tool); `LM Studio.lnk` (shared) | F-3 transitional |
| Loose launchers | `_V1\Launch URI Harness.bat`, `_V1\Launch URI Voice.bat`, `Launch URI.bat` in each checkout | DONOR / forbidden |
| Services | `CodexSandboxService.OpenAI.Codex` (shared developer tool) | SHARED |
| Python | System Python 3.13.15 (`AppData\Local\Programs\Python\Python313`); venvs in `uri-agent`, `uri-m37-m39-integration`, `uri-phase1-integration`, `uri-phase2a` (+ two consolidation copies) — all on the same base interpreter | venvs belong to their checkouts; F-3 fallback noted |
| Flutter / Dart / Node | `C:\Users\cheta\flutter`, Node v24.19.0 (`Program Files\nodejs`), npm global (`AppData\Roaming\npm`, Codex shim) | SHARED |
| Ollama | App + Startup shortcut; models gemma3/4, granite4, qwen2.5-coder, qwen3, qwen3.5, smollm2 | SHARED (Core is model-optional) |
| LM Studio | `D:\New folder (2)\LM Studio`, `~\.lmstudio` (CLI on PATH) | SHARED |
| Claude / Codex configs | `~\.claude`, `~\.codex` (native account homes; contents not read) | SHARED; must never be imported into URI (Phase 1 C4 / Phase 2 ISO-1) |
| Environment | PATH entries for Python, npm, Ollama, Flutter, LM Studio, Node only; no URI_* variables | clean |
| Data roots | `uri_workspace\` in uri-agent (957 users, live), integration (78), `_V1` (104), batch-candidate (14) | Owned by their checkouts; none is the authoritative state root (C1 provisions fresh roots) |
| Model registries | `D:\uri-model-lab` (pinned Runtime v1), `C:\uri-model-lab-nvme` (F-7), `~\.uri\models\needle3`, `%LOCALAPPDATA%\URI\models\faster-whisper-base.en`, Ollama/LM Studio stores | pinned / quarantined / donor assets / shared |
| Voice side project | `%LOCALAPPDATA%\URI\voice\*` session folders (2026-10-04) | QUARANTINED data |
| Camera | `D:\Security Cameras\Camera 1` recordings (external recorder, last write 10-05), no recorder running, no camera task | Not URI; private; never in Git |
| Encrypted vault | `D:\URI-preservation\phase1-20261005-0037` (79 GB) | PRESERVED |

## 3. Can an old installation silently become the active URI runtime?

| Attempt | Result today | After proposed containment |
|---|---|---|
| Log on to Windows | Legacy server starts automatically (F-1) | Task disabled: nothing starts |
| Open any `uri_ui.exe` directly | Connects to whatever owns 8000 with a stored token (F-2) | Nothing owns 8000; UI shows disconnected. Full fix is per-installation client storage (C3/C6) |
| Double-click `URI.lnk` | Aborts while F-1 runs; otherwise starts the donor desktop server | Shortcuts moved to backup; donor not reachable by click |
| Double-click a `Launch URI.bat` in any checkout | Starts a legacy-composition server on 8000 | Still possible (file stays); checker reports it as DONOR/UNACCOUNTED, and the authoritative start gate refuses to run while it is active |
| Start the frozen C1 launcher on 8000 or 8021 | Refused by frozen Core (`NONPRODUCTION_PORT_REQUIRED`) | same |
| Start the frozen C1 launcher with a foreign server already on its port | Refused; identity requires a signed nonce, generic `/health` is never trusted | same |
| Start `scripts\uri_authorized_start.ps1` | **Refused** (live test: `REFUSED`, strict checker found 6 transitional findings) | Allowed only when the strict checker is clean |

## 4. Containment already applied (reversible, non-destructive)

| Action | Scope | Reversal |
|---|---|---|
| Removed `ChetanPC\CodexSandboxUsers` read access from 33 secret/session files (inheritance converted to explicit, then that one grant removed). Current user, SYSTEM, Administrators and one packaged-app SID unchanged | listed in `uri-canonical-evidence\acl\hardened_files.txt` | `icacls <dir> /restore acl_NNN.txt` per saved file; live server health re-checked: `{"status":"ok"}` |
| Added runtime-state and secret patterns to the shared `.git\info\exclude` (and the candidate clone): `scratch/*_state/`, `uri_workspace` session/account/key/identity files, `*.pid`, `desktop_secrets*.json` | git only; no file moved | restore `uri-canonical-evidence\info_exclude.before-20261008` |

## 5. Containment prepared, awaiting owner approval (RED)

`scripts/uri_containment.ps1` (plan by default; `-Apply`; `-Restore -BackupRoot <folder printed by -Apply>`):
- C-1 disable scheduled task `\URIServer` after exporting its XML.
- C-2 move both `URI.lnk` shortcuts into the backup folder.
- C-3 record (not edit) the UI `serverBaseUrl`.
It does not stop the running legacy server, delete files, touch credentials or Git. Stopping the running server and
choosing the authoritative state root/port are separate owner decisions (TODO CONS-1..CONS-4).
