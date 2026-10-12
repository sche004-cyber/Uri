# URI A2UI — implementation report (candidate)

Branch `phase/a2ui` (worktree `C:\Users\cheta\Development\uri-a2ui`), merged up to canonical `b02ed4f` (scheduler
integrated). Design: `A2UI_ARCHITECTURE.md`. Ledger and workflow evaluation: `A2UI_STATUS_LEDGER.md`.
**Not integrated. Nothing activated.** All scheduled-GIF evidence uses the SYNTHETIC fixture executor (labelled in the UI);
real Claude is not logged in.

## 1. What was built

| layer | files | role |
|---|---|---|
| Contract | `uri_a2ui/{catalog,actions,validate,surface}.py` | A2UI v0.9.1 subset, catalog `uri:a2ui/catalog/v1`, registered actions, strict validation, surface digest, authority-side action gate |
| Producer + authority (scheduler domain) | `uri_scheduler/a2ui_host.py`, `service.py` (`/a2ui/propose`, `/a2ui/action`, `/a2ui/surfaces`, `/a2ui/calendar`) | builds surfaces from its own validated state; every action re-validated (digest, exact Button, literals, bound values) then by the engine (owner, proposal hash, artifact hash on disk); persisted; audited (`a2ui.action`) |
| Intent handoff (Brain side) | `uri_operational_intelligence/schedule_intent.py`, hook in `worker_bridge.py`, event `a2ui.handoff` in `events.py` | deterministic interpreter for one request family; no model call, no Core turn, no pending decision; ordinary text keeps the existing path |
| Renderer | `uri_ui/lib/living/a2ui/{a2ui_contract,a2ui_hub,a2ui_view,a2ui_dock,sha256}.dart` | same contract checks; batch applied only if every message valid; inputs local (never `/bound`); registry of allowed actions; digest echo; images shown only if bytes hash to the bound SHA-256 |
| Placement | `companion_mode_view.dart` (card under the orb), `workspace_mode_view.dart` (Conversation dock, Tasks dock + calendar entry), `living_app.dart`/`living_scope.dart` (hub wiring), `oi_conversation.dart` (handoff stream) | existing UI kept; Workspace opened only by the user via the existing `UiCommand` vocabulary |

## 2. Acceptance criteria (from `A2UI_ARCHITECTURE.md` §5)

| id | result | evidence |
|---|---|---|
| A-AC1 contract identical both sides | **met** | 39 shared cases, same first code (`tests/a2ui/test_contract.py`, `uri_ui/test/a2ui/a2ui_contract_test.dart`); the real scheduler surfaces validate in Dart |
| A-AC2 untrusted definitions refused | **met** | adversarial cases (URL/script text, colours, icon URL, unknown component/property/action, `functionCall`, cycles, shared/dangling/unreachable nodes, depth/size limits, writes to `/bound`, `sendDataModel`); 3,000-case fuzz never crashes; a batch with one bad message is refused whole and the owner is told (widget test) |
| A-AC3 action gate | **met** | stale digest, forged component, wrong name, changed literal, forged bound hash, undeclared key, bad types refused (`test_contract.py`); engine re-checks owner and hashes; live: `DRAFT_CHANGED`, `STALE_SURFACE` refused by the real service |
| A-AC4 scheduler slice end-to-end | **met (P, fixture executor)** | `scripts/a2ui_live_check.py` → `docs/a2ui/evidence/live_20261009/a2ui_live_result.json` **PASS**: owner sentence → interpreter → proposal surface → selection/time edited → confirm of the un-proposed draft refused → revise (new hash, old PROPOSED job cancelled) → confirm → job ACTIVE with exactly diwali+holi, 08:30, 2 days before; nothing ran before confirm |
| A-AC5 persistence | **met (P)** | live check kills the service process (`taskkill /F /T`), restarts it; the open proposal re-renders from the stored record (revision 2, edited selection); the pre-revision digest is refused; confirm succeeds |
| A-AC6 simple requests stay conversational | **met (S)** | `test_ordinary_requests_stay_conversational` (9 cases), worker bridge test: a question still goes to the answer channel |
| A-AC7 additional workflows | **met** | artifact review (live: bytes SHA-256-verified, wrong hash refused, approve → APPROVED); calendar review (live: dispute recorded as an append-only correction) |
| A-AC8 visual integration | **met** | real built Windows app (`flutter build windows --release -t lib/main_living.dart`), screenshots in `screenshots/`: proposal card under the Sun orb (Companion), review card with the real GIF in Tasks, proposal in the Conversation dock; Living tokens only |
| A-AC9 measurements and recovery | **met** (§3) | |
| A-AC10 frozen/accepted modules | **met** | `ws_frozen_check` ok (121/121, no protected path); guards extended by 15 exact paths; hook lines: `worker_bridge.py` (+21), `events.py` (+2), 6 Dart files (small hooks) |
| A-AC11 independent audit | pending | `A2UI_AUDIT.md` |

## 3. Measurements (live check, this PC, fixture executor)

| step | time |
|---|---|
| worker handoff → proposal surface built, validated (Python), sent, validated and applied (Dart) | 33 ms |
| action round trip (renderer → service gate → engine → reply applied): revise / review / calendar / confirm | 8.6 / 10.7 / 10.4 / 6.5 ms |
| applying a surface batch in the renderer | 0.1–9.9 ms |
| Flutter journey phase a / phase b (process incl. test start-up) | 14.1 s / 5.8 s |

Failure recovery shown to the owner: scheduler not running → notice "the scheduler is not running … Nothing was
scheduled" (widget test); stale surface → refreshed + "This view was out of date…" (live refusal `STALE_SURFACE`);
changed draft → "Press Update proposal first" (live `DRAFT_CHANGED`); invalid definition → refused whole + notice (widget
test); image bytes not matching → "The image was not shown…" (widget path; live: `ARTIFACT_HASH_MISMATCH`).

## 4. Comparison with the accepted baseline

| task | baseline (canonical `b02ed4f`) | with A2UI |
|---|---|---|
| Set up festival GIFs | Dashboard → Scheduled tasks → fixed button → dialog with the default list → Activate; selection, time and offset not editable in the UI | say it in the conversation; an editable proposal appears beside the orb; edit, Update, Confirm; assumptions stated |
| Review a GIF | Scheduler view dialogs | same authority path, inline card in Tasks, image hash-checked before display |
| Correct the festival calendar | API only (`POST /calendar/correct`) | Tasks → Review festival calendar |
| Security | proposal/artifact hashes, owner checks | unchanged, plus surface digest, exact-button and bound-value checks; no new permission anywhere |

## 5. Known limits

- The interpreter is deterministic and covers one request family; other requests are not turned into surfaces.
- Real-HTTP button presses inside Flutter widget tests run through `hub.act` on the real event loop (the widget-test zone
  blocks socket I/O); the tap → act wiring is covered by the widget tests with a fake client, and the real built app was
  shown rendering real scheduler surfaces (no automated clicks: no input injection into a desktop shared with other sessions).
- Images in the A2UI review card are animated GIFs decoded by Flutter; very large GIFs (1.6 MB here) take a moment.
- Workspace dock height is bounded (scrolls inside); the Companion card scrolls when the proposal is long.
- No recovery surface for Brain/worker yet (next candidate).
