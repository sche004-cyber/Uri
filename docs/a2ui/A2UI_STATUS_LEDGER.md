# URI A2UI — status ledger and workflow evaluation

Ladder: Researched → Proposed → Prototyped → Implemented → Tested (level) → Independently accepted → Integrated.
Evidence levels: **S** automated simulation (in-process engine, scripted harness, widget tests with a fake HTTP client),
**P** process level (real scheduler service process + real Flutter renderer/hub over HTTP; executor = SYNTHETIC fixture),
**L** live Claude (not available: the scheduler's Claude profile is not logged in).

## 1. Candidate workflows (owner's list) — evaluation

| # | workflow | decision | why |
|---|---|---|---|
| 1 | Scheduler creation, modification, status | **Implemented (vertical slice)** | the owner's target sentence; a proposal with ~40 festivals, a time and an offset is exactly what a conversation is bad at and a small form is good at; the scheduler is the authority and already binds confirmation to a hash |
| 2 | Task approvals, refinement, regeneration | **Implemented** | daily use once scheduling is live; the decision must be bound to the exact artifact shown, and the image must be the bytes that hash to it (renderer re-hashes) |
| 8* | Festival calendar review/correction (owner requirement of Part 1) | **Implemented** | owner asked to "review and correct the calendar"; a picker + date + note with three bound actions replaces raw API calls |
| 3 | Office notes, letters, drafting | Deferred | the draft desk lives on `phase/text-intelligence` (not in this base); its accepted Living `DraftPanel` already gives a structured surface — A2UI would duplicate it now |
| 4 | Gmail draft preparation | Deferred | no connected mail capability in this base; would only render a mock |
| 5 | File and template selection | Deferred | Documents region is simulated (badged) in the working system; no authority to bind to yet |
| 6 | Harness, provider, model selection | Deferred | Brain selection has its own accepted typed command (`brain_select` with a catalog row id); re-expressing it as A2UI adds risk without benefit |
| 7 | Task progress, quota interruptions, recovery | Deferred (next candidate) | worker health/restart commands exist; a recovery surface needs a producer in the worker (import gate) — next slice |
| 8 | Structured clarification during intent discovery | Partially: the proposal surface carries the interpreter's assumptions and makes every assumed value editable | full clarification belongs to Core's accepted intent discovery; not re-implemented |
| 9 | Contextual Companion controls / Workspace transitions | Implemented as placement only | a surface asks for `companion`/`workspace`; the Workspace is opened only through the existing `UiCommand` vocabulary by a user chip |

## 2. Capability status

| capability | status | level | evidence |
|---|---|---|---|
| Research: A2UI v0.9.1 / v1.0 RC, Flutter `genui`, AG-UI | Researched; decision recorded | — | `A2UI_ARCHITECTURE.md` §2 |
| Contract (catalog, limits, actions, validation, digest) | Implemented · Tested | S | `tests/a2ui/test_contract.py` (fixture cases, action gate, 3,000-case fuzz) |
| Python ↔ Dart contract agreement | Tested | S | 39 shared cases, same first error code (`uri_ui/test/a2ui/a2ui_contract_test.dart`) |
| Scheduler surfaces (proposal, status, review, calendar) + action gate + persistence + audit | Implemented · Tested | S, P | `tests/a2ui/test_scheduler_a2ui.py`; live check |
| Worker handoff (deterministic interpreter, no model call, no Core turn) | Implemented · Tested | S | `tests/a2ui/test_schedule_intent.py` incl. bridge turn events |
| Renderer (Living theme, inputs local, registry, digest echo, SHA-256-checked images) | Implemented · Tested | S, P | `uri_ui/test/a2ui/a2ui_hub_test.dart`; live check |
| Companion card / Workspace dock / Tasks region | Implemented · widget-tested | S | companion slot test; not yet captured in the built Windows app |
| Real-Claude generation behind a surface | **Not run** | — | Claude profile not logged in (owner action); FIXTURE only |
| Independent audit | **Accepted with findings** (7 rounds; final r7 AwF; integration review AwF) | — | `A2UI_AUDIT.md` |
| Integration | **Integrated** into `integration/git-sync-20261008` at `dc1ce81` (chain ALL_PASS with outcome identity) | — | `canonical_integration/A2UI_CANONICAL_INTEGRATION_RECEIPT.md` |
