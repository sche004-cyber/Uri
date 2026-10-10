# Staging qualification: final integration, 2026-10-10

Status: **STAGED and qualified for the automatable criteria.** This is not a production cutover. The legacy
`\URIServer` on port 8000, its scheduled task and the shortcuts were not touched.

## Installation under test

| Item | Value |
|---|---|
| Source (UI tree) | `C:\Users\cheta\Development\uri-final-stage-src`, detached at `0215887` (a clean worktree of the integration branch) |
| Runtime | `C:\Users\cheta\Development\uri-final-stage-rt2`, materialized by `scripts/oi_materialize_test_runtime.py` from that tree: HEAD `e8e3b65`, overlay `759d0d4`, receipt `candidate_head` = `0215887` |
| Provisioning | `ws_provision.py --name staging-final`, port 18300, **run from PowerShell** (see ENV-P1) |
| UI | `flutter build windows --release` in the same tree |
| Start | `scripts\launch_uri_working_system.ps1 -RuntimeRoot …\uri-final-stage-rt2 -UiRoot …\uri-final-stage-src` |
| Host | Ryzen 9 5900X, RX 7900 GRE 16 GB, Windows 11 26200; heartbeat log `evidence/staging2/heartbeat.jsonl` |

A first staging pass ran at `85fb24f`, before the rail-orb and INT-F1 changes. Its evidence is in `evidence/staging/`.
The second pass, at `0215887`, is the one this record qualifies (`evidence/staging2/`).

## Results

| Criterion | Result | Evidence |
|---|---|---|
| Launcher self-test, refusals (legacy root, foreign UI, arbitrary UI root, port 8000) | PASS (rc 0) | `staging2/selftest.json` |
| Companion and Workspace launch; UI-first order | PASS. Server 20:13:30, then window 20:13:32, then Brain host 20:13:38 | `staging2/launch_console.txt`, `launch_processes.txt` |
| Brain connection and response | PASS. Brain READY, calibration **145.9 tok/s** with the window open (handoff target ≥ 120). Live answers 121-125 tok/s, first token 0.8-0.9 s | `brain_host.json` in the runtime; `staging2/05_brain_and_draft.png` |
| GPU residency | Brain 14,946 MiB local and 1,730 MiB non-local (about 860 MiB beyond the 872 MiB host-visible share), with no slowdown. Fit verdict AT_RISK (−57 MB shortfall): the known Runtime v1 oversubscription (Adaptive Runtime R1/R2) | brain host report |
| P-GOV-1 advisory with a resident Brain | GO for a 480 MiB window (63 MiB margin); WILL_DEGRADE_BRAIN, exit 76, for 700 MiB | `staging/advise_resident_brain*.json` |
| Dictation → corrected draft | Typed-text path PASS (letter and notice drafted, "Not sent · not saved", 110-123 tok/s). **Voice dictation not run live**: DEFERRED, owner unavailable | screenshots; voice service tests 29/29 (`staging2/voice_service_tests.txt`); Flutter voice tests inside 511 passed |
| Voice recognition and spoken replies | Automated tests only (29 service + Flutter). **Human microphone qualification NOT VERIFIED (deferred).** The speaker→microphone e2e was deliberately not run: it plays synthetic speech into the owner's home and records room audio | — |
| A2UI proposal, revision, approval; stale and unauthorised actions | PASS at process level (real scheduler service + real renderer, synthetic fixture executor). Forged pre-revision confirm → `STALE_SURFACE`; confirm before propose → `DRAFT_CHANGED`; service kill/restart; hash chain 27 ok. State was temporary and deleted | `staging/a2ui_live/a2ui_live_result.json` |
| Scheduler handoff in the real app | The scheduler service is not started by the launcher (not activated). The reply is now truthful (INT-F1) and the companion returns to Idle | `staging2/04_intf1_after_wait.png` |
| Worker journeys (question, reasoning, cancel, approve, deny, refusal, forged digest, restart refused during a turn) | PASS 13, 1 skipped (opt-in), then the opt-in Brain restart journey PASS 2 | `staging2/worker_live_console.txt`, `worker_live_restart_console.txt`, `worker_live_*.json`, `ti_worker_live_*.json` |
| Restart and recovery | PASS. UI closed and relaunched: identity re-proven, Brain host and llama-server reused (no duplicate). Brain restart through the host → READY 156 tok/s. Staging stopped with a stop file → HOST_EXIT, lease released. Drafts and conversation do not survive a UI restart (TI L-7, DESIGN, accepted) | `staging/launch2_*`, brain host report |
| Orb FPS setting | Not re-measured. The frame clock and FPS settings code is unchanged (only the rail geometry moved). Companion-settings evidence is reused: UI-first 144.7 FPS, Codex r4 ACCEPT | reused |
| Orb appearance | Same Solar orb, palette and animation. Rail orb centred and enlarged at the owner's request | `staging2/02_workspace_orb.png` |

## Environment findings

- **ENV-P1 (new):** provision and launch from the same shell. The frozen `runtime_identity` hashes the `git` found on
  PATH. Git Bash (`mingw64\bin\git.exe`) and PowerShell (`Git\cmd\git.exe`) differ, so an installation provisioned in
  Git Bash fails under the PowerShell launcher with `DEPENDENCY_MANIFEST_MISMATCH`, and the server exits silently.
- **INC-1:** unexpected host resets (no bugcheck) on 2026-10-09 and 2026-10-10. A heartbeat log now runs during GPU
  work. No reset occurred during either staging pass.
