# URI Phase 0 — Runtime Inventory

Assessment date: 2026-10-05, Asia/Calcutta. Observations were collected around midnight through 00:24 IST. Status: assessment only; no implementation or release verdict.

## Executive finding

There is no single operational URI installation today. The normal Windows shortcuts target the **integration desktop checkout**, the logon task targets **master's checkout**, and the only observed running URI API is a **separate provisional harness-console checkout on 8021**. These are distinct compositions, even though each serves URI Core.

Reuse `uri_core` as the server foundation. The conservative accepted source anchor is `uri-agent` at `e8e3b65` (ARN.1), not the entire dirty directory. Preserve the integration desktop and V1 work as additional behavior/source donors until their exact code and qualification are reconciled. Do not replace the current desktop with clean master merely to simplify naming.

## Method and evidence limits

Read-only inspection used Git status/log/branches/worktree metadata, source inspection and AST route enumeration, Windows process/listener/service/task inventory, shortcut resolution, filesystem metadata, package metadata, model manifests, and two GETs to the already-running harness server (`/health`, `/openapi.json`). No application modules were imported, tests run, UI launched, accounts authenticated, models loaded, or databases opened. Reports are the only files created.

Discovery covered `C:/Users/cheta/Development`, URI's registered Codex worktrees, user/public desktop and Start Menu launch entries, user URI/Ollama/LM Studio model roots, and installed command locations. It was not a full-disk forensic scan; undiscovered copies elsewhere remain possible. A negative process finding is a point-in-time result. File presence, historical tests, source wiring and live qualification are different evidence levels.

Graphify's existing developer graph was inspected through a read-only one-hop traversal (336 neighbors of the selected Core hubs). Its report records commit `ad9cb368`, 12,787 nodes and 24,494 edges; it is stale relative to HEAD and dirty files. It provided navigation only. Source inspection controls conclusions. No graph rebuilding, learning writes, or installation was performed.

## 1. Git repositories and checkouts

These URI checkouts share the `uri-agent` Git worktree family; separate directories do not imply independent repositories. `Development/Uri` is a container, while `Uri/_V1` is a registered checkout.

| Checkout under `C:/Users/cheta/Development` | HEAD / branch | Observed role | Dirty status at initial snapshot |
|---|---|---|---|
| `uri-agent` | `e8e3b65`, `master` = locally recorded `origin/master` | Accepted Core lineage through ARN.1, plus substantial uncommitted backend/UI/provider/launcher work | 65 porcelain entries |
| `Uri/_V1` | `62d564c`, `codex/antigravity-harness-recon` | V1 parallel turn/memory/execution work, harness console, voice additions, experiments | 247 entries |
| `uri-batch-candidate` | `a87e158`, `candidate-m36-m37-m38` | M36 negation/verifier candidate | 2 entries |
| `uri-m37-m39-integration` | `eb73693`, `experimental/desktop-recovery-repair` | Shortcut-targeted desktop; Core plus V1 packages and desktop seams | 48 entries |
| `uri-dictation` | `f1e13e9`, `feature/uri-dictation` | Standalone dictation helper plus copied integration tree | Clean |
| `Uri_edge_experiments` | `e0950d4`, `claude/project-thread-gb7z7s` | Edge specialist-pair experiments; commit subject records owner's NOT QUALIFIED decision | Clean |

Counts include files/directories reported by Git, not semantic defect counts. No fetch was performed: remote-tracking refs may be stale. Main dirty diff includes `server.py`, route classification, provider code, launchers, capability registry and Flutter screens. Integration dirty diff includes approval/canonical/native execution, drafting, Office document generation/conversion, and Flutter response handling. Neither working directory is a reproducible accepted release by virtue of its HEAD alone.

Additional registered worktrees:

| Path | HEAD / branch |
|---|---|
| `C:/Users/cheta/.codex/worktrees/batch-audit-canonical/_V1` | `62d564c`, `codex/m36-m38-canonical-audit` |
| `C:/Users/cheta/.codex/worktrees/harness-connections-console/_V1` | `62d564c`, `codex/harness-connections-console`; active test-server source |
| `C:/Users/cheta/.codex/worktrees/intent-discovery/_V1` | `62d564c`, detached |
| `C:/Users/cheta/.codex/worktrees/m33-audit-baseline/_V1` | `c2f5839`, detached |
| `C:/Users/cheta/.codex/worktrees/m33-audit-candidate/_V1` | `d1feaf7`, detached |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `5973f6d`, detached |

Important other local refs: `m35-uri-v1-parallel-architecture` at `70e6065`; `m37-m39-integration` at `985dc54`; `claude/harness-first-edge` at `86de4c0`; `claude/project-thread-sqk105` and its backup at `69ef0e4`; `experimental/desktop-core-fixes` at `98abdd0`; `needle-preroute-default-off-2026-10-01` at `71edc17`; `checkpoint/hybrid-ui-paused` at `7bb916f`; `preserve/running-app-2026-10-01` at `a91e0e4`; its local-full snapshot at `869fae5`; and `wip/batch3-codex-partial` at `535135d`. Presence is not deployment or acceptance.

The supplied M22.2/M22.3 resume note is historically stale. Actual HEAD, later governance entries, and code show subsequent work. `URI_M22_ARCHITECTURE.md` still says M22.3 is next, whereas the tracker records its delivery and active governance records later milestones. This assessment does not rerun those audits or change their status.

## 2. What launching URI selects

Observed Desktop shortcut `C:/Users/cheta/OneDrive/Desktop/URI.lnk` and Start Menu `Programs/URI.lnk` both resolve to:

```text
C:/Users/cheta/Development/uri-m37-m39-integration/Launch URI.bat
  -> launch_desktop.ps1 (default port 8000)
  -> .venv/Scripts/pythonw.exe run_desktop_server.py
  -> uri_core.app.server:app + desktop status/timing composition
  -> uri_ui/build/windows/x64/runner/Release/uri_ui.exe
```

The desktop launcher checks socket-owning process and `/desktop/status.repo_root`, uses a Windows mutex, and records UI/server PIDs. It has a fallback to master checkout's Python environment if its own Python is unavailable. The server runner inserts its checkout on `sys.path`; relative stores depend on the launcher working directory.

Integration runner defaults include `URI_HARNESS_FIRST=1`, `OLLAMA_NUM_CTX=16384`, and an Edge chat warm-up (`qwen3:0.6b`, 30-minute residency). These are code defaults, not inspected live process environment. The warm-up calls Ollama; it was not invoked here. The canonical `/ask` contains the experimental social-turn seam. Non-social turns still use Core routing. This is not proof of general external-harness operation.

Other entry points:

| Entry | Selection |
|---|---|
| `uri-agent/Launch URI.bat` | `scripts/launch_uri.ps1`, installed `URIServer` task, release Flutter UI; dirty script can rebuild a stale UI binary |
| Windows `URIServer` logon task | Master `.venv/Scripts/python.exe`, `scripts/run_uri_server.py --port 8000`, master working directory/log |
| `Uri/_V1/Launch URI Harness.bat` / `scripts/launch_uri_harness.ps1` | Provisional composition on 8018, Debug UI, scratch test state |
| `Uri/_V1/Launch URI Voice.bat` | V1 launcher with `-Voice` and speaker selection |
| Integration/dictation `launch_desktop.ps1`, `stop_desktop.ps1`, `Stop URI.bat` | Desktop lifecycle copies; inspected, never invoked |
| `uri-agent/uri_ui.py` | Legacy PyQt6 app directly importing `UriOrchestrator` and Drive services; not the shortcut path |

No launch was performed, so the next launch's success, saved server address, binary's embedded Dart flags, and actual UI behavior remain unverified. Source timestamps/build presence cannot prove which source produced a binary.

## 3. Runtime, services and scheduling

At two snapshots, URI listener: **127.0.0.1:8021, PID 16188**, global Python 3.13 executable. Command identifies `harness-connections-console/_V1/scripts/run_desktop_harness_test.py --enable-subscription-test`, with isolated `scratch/candidate_desktop_state`. Creation time was 2026-10-04 23:20:20 IST. Recorded parent 10188 was absent when checked; this is a detached/unowned-by-current-parent observation, not proof it is unwanted.

`GET /health` returned `{"status":"ok"}`. OpenAPI identified `URI API`, version `0.1.0`, and registered `/desktop/harness-test/providers`, task preparation/start/cancel/recovery and approval routes. This proves API composition/reachability only, not authenticated harness execution. No task/provider-refresh endpoint was invoked.

No listener observed on 8000, 8018, 11434, 1234, 8765 or 5000. No running `uri_ui`, Ollama, LM Studio/llama model server, URI voice/dictation Python worker, or Antigravity executable was observed in the scoped process checks. Claude desktop and Codex app/helper processes existed; multiple Chromium/Electron helpers are not duplicate URI engines. Dart MCP helpers existed and are development tooling.

`URIServer` task was **Ready**, last run 2026-10-04 22:39:39 IST, last result **3221225786 / 0xC000013A**. Installed settings have `StopOnIdleEnd=True`, while current dirty controller source specifies `-DontStopOnIdleEnd`. The exit code indicates interruption; the precise trigger was not established from event logs. No matching URI/Ollama/voice Windows service was identified; broad name matching also found unrelated Windows Security service and OS monitor tasks, which are excluded.

Ollama has a logon Startup shortcut even though no model daemon was running. Integration `uri_server.pid` contains 20488 and `uri_ui.pid` contains 24496; neither PID existed when checked. They are stale bookkeeping files, not live orphaned URI processes.

## 4. Python, Flutter and dependencies

Global Python: `AppData/Local/Programs/Python/Python313/python.exe`, venv metadata version 3.13.15. Global metadata: FastAPI 0.141.1, uvicorn 0.53.0, requests 2.34.2, pytest 9.1.1, graphifyy 0.9.58, NetworkX 3.6.1. Global faster-whisper/ctranslate2/sounddevice/cactus distributions were absent in the checked metadata.

Master `.venv` and integration `.venv`: FastAPI 0.141.1, uvicorn 0.52.4, requests 2.34.2, cryptography 50.0.1, pytest 9.1.1, tzdata 2026.4. Integration `pyvenv.cfg` records the original master venv creation path; portability is not qualified. Master `.venv-needle` exists, but checked package names did not establish a usable Cactus distribution. V1 `.venv_voice`: faster-whisper 1.2.1, ctranslate2 4.8.2, sounddevice 0.5.6; voice requirements also pin av 18.1.0. Package installation is not inference qualification.

Flutter SDK metadata: **3.47.2 stable**, Dart **3.13.2**, under `C:/Users/cheta/flutter`. Flutter, Dart, Python, uv, pip, graphify, Ollama and npm Claude/Codex shims resolve on PATH. `antigravity` and `agy` did not resolve in the checked shell; Antigravity and Antigravity IDE shortcuts/install paths exist. The child's inherited PATH may differ.

Debug and Release `uri_ui.exe` files exist in master, V1 and integration. Flutter source uses HTTP, SharedPreferences, file picker/opener, URL launcher and window manager. Core requirements include FastAPI/uvicorn, cryptography, requests, PDF/Office parsers/writers, psutil, PyMuPDF/Tesseract integration and pinned yt-dlp. No build, analyzer or dependency installation was run.

## 5. Installed models versus resident models

Ollama manifest inventory: `gemma3:270m`, `gemma4:12b`, `granite4:350m-h`, `qwen2.5-coder:14b-instruct-q5_K_M`, `qwen3:0.6b`, `qwen3.5:0.8b`, `qwen3.5:2b`, `qwen3.5:9b`, `smollm2:360m`. Blob completeness was not verified.

LM Studio files: Gemma4 12B (7.38 GB); Qwen3.5 0.8B Q8 (0.83 GB); LFM2.5 350M Q8 (0.38 GB); Gemma4 26B A4B Q4 (14.44 GB) and vision projector (1.19 GB); Qwen3.5 2B Q4 (1.27 GB); Qwen3.5 9B Q4 (5.63 GB). `Qwen3-14B-Q4_K_M.gguf` is **zero bytes**, so it is not a usable model installation. Directory labels are not reliable model identity; these are actual filenames/sizes.

Needle: `.uri/models/needle3/needle3.cact`, 35,335,380 bytes, plus Hugging Face needle3 cache root. Voice: LocalAppData URI faster-whisper-base.en `model.bin`, 145,216,508 bytes. Dictation has two faster-whisper-small cache locations, each with a 483,546,902-byte `model.bin`. Equality of these two model files was not checked. No simultaneous loaded-model conflict was observed because no model-serving process was running.

## 6. State and configuration inventory

Metadata only; private values, account records, bearer tokens, OAuth contents and database contents were not read.

| Checkout | Immediate entries under `uri_workspace/users` | Graph SQLite files including root legacy file | `provider_keys.enc` files |
|---|---:|---:|---:|
| Master | 957 | 339 | 7 |
| V1 | 104 | 56 | 0 |
| Integration | 78 | 34 | 1 |
| Batch candidate | 14 | 7 | 0 |
| Dictation / Edge experiments | 0 / 0 | 0 / 0 | 0 / 0 |

Counts are filesystem artifacts, **not confirmed real users**; test-generated and live data were not separated through private-content inspection. Root stores include user accounts, auth sessions, portable/device identities, approvals, memory, profile, skill memory, logs, Graphify index and legacy graph. Per-user trees include graphs, sessions/history/uploads, provider configuration and encrypted keys. Integration also has token files. Credential-bearing artifacts must be preserved without pooling them into shared server storage.

Integration `uri_workspace/model_roles.json` configures all six roles for Ollama `qwen3.5:9b`, context 16,384. `config/desktop_model_roles.json` is explicitly a copy-in template, not a second automatically consumed configuration. Master/V1 lack that root override in the checked locations; role defaults/environment and per-user `providers.json` remain relevant. File presence does not reveal an active serving model.

Windows preference file exists at `AppData/Roaming/com.example/uri_ui/shared_preferences.json`. Source keys include shared server address and session token/username. Its values were deliberately not read. LocalAppData URI contains a checkout-hashed desktop secret file and several voice control/status/metrics namespaces, including probes; no secret values or transcript contents were inspected. Harness account roots `.claude`, `.codex`, `.antigravity-ide` exist and remain native account stores.

## 7. Implemented capabilities and proof level

| Component | Actual evidence | Qualification limit |
|---|---|---|
| Core HTTP / canonical loop | `uri_core/app/server.py`; `/ask`, streaming, auth, tasks, files, providers, graph and connections; decision/canonical execution modules | Source traced; only harness composition health/schema checked live |
| Graphify runtime | `core/graphify_index.py`; startup loader; per-context copy; `decision_engine.py:1029` builds Turn State and hints | Advisory pointers, never execution authority; preserve per-client overlays |
| URI graph | `core/graph_store.py`, per-user SQLite construction in `server.py:351` | Private evidence graph, distinct from developer Graphify graph |
| ARN.1 | `core/arn/*`, `canonical_execution.py:722` imports NOT_FOUND recovery | Accepted checkpoint source; no new live turn run |
| RAR | V1 `turn/rar_contracts.py`, `rar_deterministic.py`, active-context types; integration clarification evidence/service/journal seams | Deterministic and experimental variants coexist; INT-ARN opt-in flag is not ARN.2 completion |
| Context assembly | Core Turn State/context budgets; V1 `memory/context_package.py:17`; `turn/active_context.py` | V1 `context/__init__.py` says no resolution logic; legacy `context_builder.py` has no production imports found in scoped Core search |
| M36–M39 | V1 memory, Edge local runner, harness runner/capsules, Office bootstrap/writeback; integration contains source | Batch audit at 62d564c records provisional/not frozen and M38 fresh live qualification outstanding |
| Harness adapters | ClaudeCodeAdapter / CodexAdapter source; desktop registry AntigravityAdapter | Antigravity execute explicitly raises containment-unqualified; installed apps do not prove authenticated adapters |
| Voice / Whisper Flow-like helper | V1 voice scripts and standalone `uri_dictation` recording/transcription/polish/clipboard/tray code | Local files/packages exist; no active service or live audio qualification in this assessment |
| Scheduling/monitoring | Separate Flutter scheduler projects, OS server logon task, Core system-performance tool | No canonical URI scheduling/watch service established by inspected paths; scheduler prototype has test code in its repository source file |
| UI / Develop | Flutter HTTP client, persisted server/session settings, ask/history/tasks/providers/connections/settings/modes; legacy PyQt UI | Preserve behavior; no visual verification now; Develop UX is not server authorization |

Supporting source references and conflicts are expanded in the companion reports. Nothing here promotes experimental or dirty implementations to accepted status.

## Appendix — Complete local branch ref snapshot

Read-only local refs; no remote fetch and no acceptance implied. Registered checkout paths are listed above.

```text
backup/project-thread-sqk105-69ef0e4 | 69ef0e4
candidate-m36-m37-m38 | a87e158
checkpoint/hybrid-ui-paused | 7bb916f
claude/harness-first-edge | 86de4c0
claude/project-thread-8llqxx | 3cd3557
claude/project-thread-gb7z7s | e0950d4
claude/project-thread-sqk105 | 69ef0e4
codex/antigravity-harness-recon | 62d564c
codex/harness-connections-console | 62d564c
codex/m36-m38-canonical-audit | 62d564c
codex/m36-m38-independent-audit | 70e6065
experimental/desktop-core-fixes | 98abdd0
experimental/desktop-recovery-repair | eb73693
feature/uri-dictation | f1e13e9
m35-uri-v1-parallel-architecture | 70e6065
m37-m39-integration | 985dc54
master | e8e3b65
needle-preroute-default-off-2026-10-01 | 71edc17
preserve/running-app-2026-10-01 | a91e0e4
preserve/running-app-2026-10-01-local-full | 869fae5
wip/batch3-codex-partial | 535135d
```
