# URI capability ledger: final integration, 2026-10-10

Ladder: RESEARCHED → IMPLEMENTED → TESTED → INDEPENDENTLY ACCEPTED → INTEGRATED (canonical) → STAGED (fresh isolated
install, qualified) → ACTIVATED (live for the owner). A level is claimed only with COMPLETED_WITH_RESULT evidence; the
evidence column names it. "Reused" means accepted evidence from an earlier session on code this session did not change.

Canonical before this session: `uri-repo/integration/git-sync-20261008` @ `54ad7be` (tree `786f8de`), verified
2026-10-10 by fetch and ancestry.

| Capability | Highest level | Evidence | Not yet |
|---|---|---|---|
| Brain (Runtime v1, frozen) | STAGED (this session, 145.9-156 tok/s) | `STAGING_QUALIFICATION.md` | ACTIVATED |
| Brain host + GPU lease | INTEGRATED | WS hardening receipt (reused) | ACTIVATED |
| P-GOV-1 window advisory + UI-first launcher | INDEPENDENTLY ACCEPTED (Codex r11 AwF), STAGED (UI-first 145.9 tok/s live) | `P_GOV_1_AUDIT.md`, `STAGING_QUALIFICATION.md` | INTEGRATED on canonical (pending fast-forward) |
| Companion (orbs, themes, FPS caps) | INTEGRATED; STAGED | companion-settings receipt; Flutter 511/5 at 08a9192 | FPS not re-measured (code unchanged) |
| Workspace rail orb centred (owner request) | INDEPENDENTLY ACCEPTED (Codex r5), STAGED | commits 9fdefe3, 2cf3231 | — |
| INT-F1 truthful A2UI handoff reply / companion state | INDEPENDENTLY ACCEPTED (Codex r5), STAGED (verified live) | e109c3d..08a9192 | — |
| Live voice (PTT, STT, spoken replies) | INTEGRATED | live-voice receipt; voice tests 42+29 at 54ad7be (reused) | human-voice qualification (owner) |
| Voice → TI (conversation + drafting, INT-3) | INTEGRATED, widget-tested | TIWS r12-r14 (reused) | live microphone run (owner) |
| Text Intelligence (draft desk) | INTEGRATED | TIWS receipt | — |
| TI → A2UI handoff (typed and transcript) | INTEGRATED, tested | `tests/ws/test_ti_desk_bridge.py` a2ui cases (in this session's 590-pass run) | — |
| A2UI proposal / revision / approval | INTEGRATED | A2UI receipt (Codex r7 AwF) | — |
| Scheduler (engine, review, calendar) | INTEGRATED | scheduler receipt; 71/71 this session | real-Claude execution (BLOCKED: login), Windows task, festival jobs: not activated |
| Restart: stale/unauthorised action rejection | STAGED | A2UI process check (STALE_SURFACE, DRAFT_CHANGED), worker forged-digest journey, UI restart reuse, Brain restart | — |
| Production cutover | PLANNED | `CUTOVER_PLAN.md` | owner approval |
| VRAM efficiency | RESEARCH in progress | `research/vram-efficiency-20261010` | — |

Incident INC-1 (2026-10-10): the host reset without a bugcheck (Kernel-Power 41, all parameters 0, no power-button
event) about 10:06 local, during the first VRAM screening load (frozen configuration, prefill phase); it was back at
17:19. Earlier unexpected resets: 2026-10-09 ~13:57 and 2026-10-09 after 23:32 (that one while a resident Brain was
idle). The pattern (no bugcheck, no power-button press, long gaps) fits a power loss with automatic power-on better
than a GPU hang, but nothing on disk proves either. From here every GPU run is accompanied by an fsynced heartbeat
(`research/vram_efficiency/heartbeat.py`).
