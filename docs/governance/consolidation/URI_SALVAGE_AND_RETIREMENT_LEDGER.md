# URI Salvage and Retirement Ledger — 2026-10-08

Every relevant URI capability, its purpose, where its code actually is, its status, and its disposition.
**No component is retired by this ledger.** "Propose deletion" means a later, owner-approved action after the
recovery path listed here has been tested. Nothing was deleted.

## Status scale and evidence rules

PLANNED < PROTOTYPED < IMPLEMENTED < TESTED < ACCEPTED < QUALIFIED < FROZEN; DEPLOYED is orthogonal (running or
installed on this PC). A status is only given when primary evidence supports it:
- **Code present** was checked with `git ls-tree` on the named commit (not inferred from documents).
- **TESTED** for canonical components = the 2026-10-08 gate run in `URI_CLEANUP_VERIFICATION_REPORT.md`; for donor
  lines = the commit/report record (marked "record, not re-run").
- **ACCEPTED/FROZEN** = a named verdict document or freeze record.
- **DEPLOYED** = observed process, scheduled task, shortcut or installed build on 2026-10-08.

Dispositions: **RETAIN** (in canonical line) · **INTEGRATE** (needed in canonical; reconcile via C5–C7 with
provenance) · **DONOR** (preserved, read-only, reusable) · **QUARANTINE** (must not run; investigate before reuse)
· **PROPOSE DELETION** (owner approval + tested recovery first).

## 1. Canonical Core lineage

| Capability | Purpose | Code (verified) | Status | Disposition |
|---|---|---|---|---|
| ARN.1 deterministic narrowing | Bounded retrieval narrowing with NOT_FOUND recovery | `uri_core/core/arn/*` at e8e3b65 | IMPLEMENTED, TESTED, ACCEPTED (ARN_1_STATE) | RETAIN |
| Graphify index + graph engine | Advisory capability/graph hints; never grants authority | `uri_core/core/graphify_index.py`, `graph_*` at e8e3b65 | IMPLEMENTED, TESTED (Phase 1 suites) | RETAIN; graph authority tests in Phase 1 |
| Memory (user/skill/drafting) | Per-user memory stores in Core | `uri_core/core/user_memory.py`, `skill_memory.py`, `drafting_memory.py` | IMPLEMENTED, TESTED (Phase 1 full suite) | RETAIN |
| Model router / provider registry | Model selection, degraded mode | `uri_core/core/model_router.py` | IMPLEMENTED, TESTED | RETAIN |
| C1 runtime identity + launcher authority | One verifiable server identity; foreign-listener refusal; legacy port refusal | `uri_core/core/runtime_identity.py`, `scripts/uri_server_launcher.py`, `uri_server.ps1` | IMPLEMENTED, TESTED, ACCEPTED, **FROZEN** (Phase 1) | RETAIN; the authoritative launch path |
| C2/C3 client identity, pairing, client-owned state | Client/server separation, private client DBs | `uri_core/client_runtime/*`, `client_pairing.py`, `client_state_ports.py` | FROZEN (Phase 1) | RETAIN |
| C4 client-local harness execution | Server never holds harness credentials | `uri_harness_adapters`, Phase 1 C4 modules | FROZEN; native auth/containment = documented limitation | RETAIN |
| C5 Intent Discovery + reference binding (RAR) | Clarify/confirm intent; deterministic reference binding with provenance from eb73693 | `uri_core/core/intent_discovery.py`, `uri_core/reference_binding/*` (+ `PROVENANCE.json`) | FROZEN (Phase 1) | RETAIN |
| C6 UI contract, paired runtime screen | UI against paired runtime | `uri_ui/lib/screens/settings/paired_runtime_screen.dart`, `services/paired_runtime.dart` | FROZEN | RETAIN |
| C7 offline rollback | Recovery of Phase 1 file set | `scripts/phase1_offline_rollback.py` | FROZEN; cutover NOT performed | RETAIN |
| Phase 2A durable supervisor | Durable admission, fencing, containment, recovery | `uri_supervisor/*` | ACCEPTED (2D/ops/closure); not frozen; power loss not physically qualified | RETAIN |
| Phase 2B bridge, 2D composition, ops lifecycle | Signed ticket → supervised task; opt-in profiles; UI lifecycle | `uri_supervisor_bridge/*`, `scripts/run_uri_phase2_server.py`, `run_uri_supervised_worker.py`, supervised screen | ACCEPTED (closure round 6; operational qualification `-g` accepted by Codex OQ round 7, in Git at `6dea266`) | RETAIN |
| Codex CLI native executor | Real harness execution | Phase 2C/2D qualification | QUALIFIED (run-scoped); worker execution BLOCKED (EXE-1) | RETAIN; owner decision EXE-1 |
| Claude CLI executor | Real harness execution | — | BLOCKED (not logged in) | RETAIN design; owner login |
| Runtime v1 (resident Brain) | Local Qwen3.6 llama.cpp runtime | `model_lab/*`, `local_brain.json`; binaries on `D:\uri-model-lab` | FROZEN (2026-10-07); artifacts re-hashed and generation speed reproduced 2026-10-08 (`URI_INFERENCE_OPTIMIZATION_RECOVERY.md`); **not integrated** into Phase 2 composition; not DEPLOYED | RETAIN as frozen component; INTEGRATE later |
| Legacy one-click launchers in Core tree | Old single-checkout start (`Launch URI.bat`, `scripts/launch_uri.ps1`, `uri_server_ctl.ps1`, `run_uri_server.py`) | e8e3b65 base files | IMPLEMENTED (pre-Phase 1) | **QUARANTINE in place**: present for compatibility, classified forbidden entrypoints in the authority manifest; replacement = C1 launcher |

## 2. Desktop mainline (donor line `eb73693`, installed at `uri-m37-m39-integration`)

| Capability | Purpose | Code (verified at eb73693) | Status | Unique vs canonical? | Disposition |
|---|---|---|---|---|---|
| M36 URI-Memory minimum | Grounded memory with qualification | `uri_v1/memory` (12 files) | FROZEN (bd7c450) | Yes | INTEGRATE via C5 (port with provenance) |
| M37 Edge (local small-model specialists) | Edge-first social routing | `uri_v1/edge` (10) | FROZEN (bd7c450), M37-L4 accepted | Yes | INTEGRATE via C5 |
| M38 harness execution capsules | Bounded harness runs, approvals, receipts | `uri_v1/execution/*` incl. `harness/` | FROZEN (bd7c450) | Partly (Phase 1 C4 + Phase 2 supersede the execution path; capsule semantics are a donor) | DONOR; compare with Phase 2 before porting |
| M39 Office demonstrator | Office file operations | `uri_v1/office` (9) | ACCEPTED R0 (record, not re-run) | Yes | INTEGRATE via C5/C6 |
| INT-ARN-1 clarification in desktop /ask | RAR clarification cards in desktop | `uri_desktop_seams/reference_clarification`, UI card | IMPLEMENTED, audit rounds 1–4 (record) | Superseded for Core by Phase 1 C5 (marker `SUPERSEDED_FOR_PHASE1.md`) | DONOR (UI card design reusable) |
| Desktop features: Google onboarding, Gmail/Drive/Docs creation, PPT research decks, uploads summarization, Ollama residency | Daily-use desktop capabilities | `uri_core/*` changes in 3c8087b..0699cb6 | IMPLEMENTED, Codex-audited (record) | Yes — **canonical Core lacks them** | INTEGRATE via C6 parity before any cutover |
| Desktop UI build `uri_ui.exe` (2026-10-01) | The UI the owner launches | `uri-m37-m39-integration\uri_ui\build\...\uri_ui.exe` | DEPLOYED (Start Menu + Desktop shortcut) | Yes (richer than canonical UI) | DONOR until C6 parity; then retire with approval |
| Presentation variants / document layout / approval-result repairs (2026-10-03) | PPT/document quality | `preserve/desktop-int-uncommitted-20261003` | IMPLEMENTED, review pending | Yes | DONOR |
| Dynamic planning slice 1 | Planning compiler/contracts | `uri_v1/planning` at e4dea8c (565eae8) | FROZEN (slice 1) | Yes | INTEGRATE later (owner priority) |
| Dictation | Standalone dictation + polish | `uri_dictation/` at f1e13e9 | IMPLEMENTED + qualification evidence (record) | Yes | DONOR; integrate per C6 voice decision |

## 3. Superseded-base work (`62d564c`) and experiments

| Capability | Location | Status | Unique? | Disposition |
|---|---|---|---|---|
| Desktop harness qualification + harness completion | `preserve/v1-harness-voice-research-20261004` (`uri_v1/desktop_harness`, UI widgets) | Provisional; acceptance blocked | Partly (Phase 2 supervised screen covers execution; harness discovery/selection UX is unique) | DONOR |
| Harness / Connections / Console | `preserve/harness-connections-console-20261003` | PARTIAL / ACCEPTANCE BLOCKED | Yes (three Connections tabs, inspector) | DONOR for C6 |
| Experimental intent workflow | `preserve/intent-discovery-20261004` | Superseded by Phase 1 C5 | No | DONOR (historical); PROPOSE DELETION of worktree later |
| Camera / voice / Gemma | `_V1` (`preserve/v1-...`), voice state `%LOCALAPPDATA%\URI\voice`, whisper model `%LOCALAPPDATA%\URI\models` | Partial; camera 2 and recording management BLOCKED; voice status strip implemented in `_V1` only | Yes | DONOR; voice data QUARANTINED (not part of runtime) |
| Camera recordings | `D:\Security Cameras` (external recorder, not URI code) | Not URI; private recordings | n/a | Never in Git; leave untouched |
| M35 URIv1 A2.x research (Needle/LFM/Qwen decoders, RAR stages) | `_V1` research files in `preserve/v1-...`; qualified RAR code already in eb73693 and ported to Core | Research (VERIFICATION_READY) | Research evidence only | DONOR (evidence) |
| Harness-first edge experiment | `claude/harness-first-edge` 86de4c0; local `69ef0e4` | Experimental | Partly | DONOR; `69ef0e4` disputed, local only |
| Edge pair | `claude/project-thread-gb7z7s` | NOT QUALIFIED (owner) | — | DONOR (negative evidence) |
| WIP batch 3 | `wip/batch3-codex-partial` | Unreviewed | — | QUARANTINE |
| Home automation | Searched all branches (`home assistant|mqtt|tuya|smart home|onvif|rtsp`): only camera RTSP notes and planning-action vocabulary | No home-automation implementation exists | — | Nothing to salvage |

## 4. PC installations

| Installation | Purpose | Status | Disposition |
|---|---|---|---|
| `C:\Users\cheta\Development\uri-agent` (legacy dirty master) + scheduled task `\URIServer` | Live legacy server on 127.0.0.1:8000 since logon | DEPLOYED; content preserved in `a91e0e4`/`869fae5` | QUARANTINE (transitional): disable task after owner approval (`scripts/uri_containment.ps1`) |
| `uri-m37-m39-integration` + `URI.lnk` (Desktop, Start Menu) | Installed desktop UI + desktop server launcher | DEPLOYED | DONOR (transitional) until C6/C7 |
| `_V1` UI build (2026-10-04), `Launch URI Harness.bat`, `Launch URI Voice.bat` | Harness/voice experiments | Built, not auto-started | DONOR; never launch as URI |
| `uri-dictation`, `Uri_edge_experiments`, `uri-batch-candidate`, m33 worktrees | Feature/experiment checkouts | Idle | DONOR / HISTORICAL; worktree removal = owner decision |
| `.tmp_m33_1_batch4_baseline_5973f6d` worktree | Pytest temp residue | Idle | QUARANTINE; PROPOSE DELETION (recoverable at 5973f6d) |
| `C:\uri-model-lab-nvme` | Runtime v1 cold-load research copy (model + mmproj); its `sha256.txt` matches the pinned hashes | Not referenced by `local_brain.json` | QUARANTINE; PROPOSE DELETION (pinned copy on `D:\uri-model-lab` remains) |
| `%USERPROFILE%\.uri\models\needle3` | Needle 3 edge model (M33.2) | Idle asset | DONOR asset |
| `%LOCALAPPDATA%\URI` (voice state, whisper model, desktop secrets file) | Voice side project; provider-key master secret | Contains secrets; ACL hardened | QUARANTINE (data); keep |
| `%APPDATA%\com.example\uri_ui\shared_preferences.json` | Shared by every `uri_ui` build; serverBaseUrl = 8000; session tokens | Contamination vector (any UI build talks to whatever owns 8000) | QUARANTINE; per-installation client storage is a C3/C6 item |
| Ollama, LM Studio, Codex sandbox service, Flutter, Node, Python 3.13 | Shared developer tools | Legitimate shared dependencies | KEEP (not contamination) |
| `D:\URI-preservation\phase1-20261005-0037` | Encrypted vault | Preservation; restore not re-tested | KEEP; restore drill = TODO |

## 5. Recovery paths (verified 2026-10-08)

- Canonical Core lineage: fresh clone of `uri-repo integration/git-sync-20261008`, byte-verified against all three
  acceptance checkpoints (see `docs/governance/git_sync_20261008/GIT_SYNC_AUDIT.md` §13).
- Donor lines: GitHub branches listed in `URI_CANONICAL_BRANCH_DECISION.md` §5; local `donor/*` / `accepted/*` tags.
- Uncommitted donor work: `preserve/*` branches (pushed, SHA-verified).
- Runtime-state and secrets: deliberately **not** in Git; they remain only in their original locations (ACL-hardened).
