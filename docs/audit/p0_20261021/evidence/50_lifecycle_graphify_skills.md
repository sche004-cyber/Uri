# P0 audit 2026-10-21 — 50: Lifecycle, Graphify, Skills/Harnesses, Reviewer-availability policy

Auditor: Claude subagent (read-only evidence auditor). Canonical = `uri-repo/integration/git-sync-20261008` @ `ec2fab54`
(audit worktree `D:/uri-dev/uri-p0-audit`, clean; only this file was written). Local `integration/git-sync-20261008`
is stale at `348677b7`. Status words are kept apart: IMPLEMENTED / TESTED / REVIEWED (with class) / INTEGRATED
(ancestor of ec2fab54) / LIVE-VERIFIED. Memory notes and Antigravity audits are treated as REPORTED claims only.

## (a) Acceptance criteria for this evidence file

- AC1 Every capability row names location, branch@commit, and canonical status established by `git merge-base --is-ancestor <sha> ec2fab54`.
- AC2 Every test claim states count, result, commit, and who ran it; tests I ran are marked RUN-HERE with the exact command.
- AC3 Every review verdict names the record path and the review class (driver-verified, subagent, imported, self-audit).
- AC4 Incomplete, pending or killed evidence is never counted as a pass.
- AC5 Dev-tool graphify and URI-native graphify are kept separate, and the native runtime wiring is traced to the serving path actually used by the working system.
- AC6 Each Antigravity claim in scope gets a verdict (CONFIRMED / PARTIAL / INCORRECT / UNSUPPORTED) backed by primary evidence.
- AC7 Gaps are listed with whether they affect a verdict.

## Commands run here (all CPU-only, in `D:/uri-dev/uri-p0-audit` @ ec2fab54 unless stated)

| # | Command | Result |
|---|---|---|
| T1 | `python -B -m pytest -q -p no:cacheprovider test_graphify_index.py` | 15 passed |
| T2 | `... tests/graphify` | 15 passed (11 leak + 4 repair) |
| T3 | `... test_graph_authority_boundary.py test_graph_context_boundary.py test_graph_engine_traversal.py test_graph_ingest_controlled.py test_graph_store_crud.py test_graph_store_type_registry.py` | 62 passed |
| T4 | `... test_graph_isolation.py` | 3 failed, 1 passed: `ValueError: URI_EXTERNAL_CREDENTIAL_SECRET ... must be set` (environment) |
| T4b | same with `URI_EXTERNAL_CREDENTIAL_SECRET=p0-audit-throwaway-test-secret` (throwaway test value) | 4 passed |
| T5 | `... "test_decision_engine.py::GraphifyHintActivationTests"` | 7 passed |
| T6 | `... test_phase1_offline_components.py` | 1 failed, 13 passed, 23 errors: `RuntimeIdentityError ISOLATED_INTERPRETER_REQUIRED / SYNTHETIC_ROOT_REQUIRED`; needs the materialized runtime, so NOT VERIFIED here (not a defect finding) |
| T7 | `... test_skill_router_v1.py test_skill_evaluator_v1.py test_skill_registry_v1.py test_skill_router_v1_eval_score_contract.py` | 87 passed |
| T8 | `... test_gemma_worker_mcp.py test_qwen_coordinator_mcp.py` | 29 passed, 1 skipped |
| T9 | `python -I milestone_manager.py stats` and `verify` (cwd outside the scratch dir; code read first: `save_ledger` is never called, so both are read-only) | 18 milestones; verify "36 present / 0 missing" |
| G1 | `git grep -l -i -E "mission control\|skill command center\|developer studio\|milestone manager\|milestones_ledger"` over all 179 refs/heads+refs/remotes, then restricted to `*.py *.dart *.json *.yaml` (evidence session JSON excluded) | docs only; zero code hits |
| G2 | `git merge-tree --write-tree ec2fab54 67d45317` | clean (note: writes loose objects to the object DB, no refs) |

`git status --short` after all runs: only `?? docs/audit/` (pre-existing untracked audit folder).

## (b) Capability table

| ID | Capability | Objective | Location | Branch@commit | Tests (count/result/commit) | Review verdict (+path) | Live verification | Canonical status | Limitations | Remaining work | Dependencies | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LC-1 | Lifecycle driver (AO-4 + `uri-development-lifecycle`) | Deterministic plan→implement→independent audit→repair→gates→integrate→receipt | `scripts/dev_workflow/lifecycle.py`, `lifecycle_providers.py`, `lifecycle_report.py`, `containment.py`; skill `.claude/skills/uri-development-lifecycle/SKILL.md`; ref doc `docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md` | canonical ec2fab54 | `tests/dev_workflow` 316 passed / 5 skipped (Linux-only) on 348677b7, Windows, `D:/uri-dev/uri-ui-v2-freeze/af-review-R3/gate_dev_workflow.log` (REPORTED by UI V2 session, log read here) | per milestone below | Driver used for real Windows milestones that reached COMPLETE + driver push (DL3 r5 7d3d0f63; DL3B c3 57f2d567) | INTEGRATED | Tamper-evident, not tamper-proof (doc line 48); per-milestone state only | — | Codex/Claude CLI | — |
| LC-2 | DEV-LIFECYCLE-2 (Windows) | Make driver Windows-capable (Job Objects, launcher binding) | same | `milestone/dev-lifecycle-2-20261011` 73bdbef1 → cbdf3f2c; receipt `receipts/dev-lifecycle-2-20261011` 86221a2b (not in canonical) | Windows 238 passed/0 failed at cbdf3f2c (receipt `docs/dev_workflow/DEV_LIFECYCLE_2_INTEGRATION_RECEIPT.md` on receipt branch) | claude_cli R2 session e5872d00 ACCEPT WITH FINDINGS on cbdf3f2c (driver-verified) | Receipt itself says Windows end-to-end NOT VERIFIED at the time; later superseded by DL3 runs | INTEGRATED (73bdbef1, cbdf3f2c ancestors) | Open LOW r3.R2-01 (documented limitation; later "R2-01" finish() fix described in doc line 46, test `test_lifecycle_dl2_r2_repair.py`), r2.R1-05 documented limitation | — | — | none |
| LC-3 | DEV-LIFECYCLE-3 (UI-first + Codex-first policy) | 12-stage map, Stage 8 live UI qualification, auditor selection | skill + docs | `milestone/dev-lifecycle-3-ui-first-20261015` 7d3d0f63 | driver gates (state `C:/Users/cheta/Development/uri-dl3-run/r5/state`) | codex_cli R1 ACCEPT on 7d3d0f63, driver-verified (`uri-dl3-run/r5/state/RECEIPT.md`), stage COMPLETE | n/a (policy) | INTEGRATED | Earlier C1-C3 Claude-agent reviews were imported (not counted); open LOW C3-01 (REPORTED, memory) | — | — | none |
| LC-3A | DEV-LIFECYCLE-3A (Codex Windows sandbox, DRV-1/2) | Codex reviewer works on Windows | lifecycle_providers.py | `milestone/dev-lifecycle-3a-codex-win-sandbox-20261015` 777f8d81 | driver gates | Codex ACCEPT (REPORTED; run state `uri-dl3a-run/r2/state` = BLOCKED OWNER_AUTHORIZATION, integrated as ancestor of 7d3d0f63) | n/a | INTEGRATED | Codex reviewer's own pytest blocked in read-only sandbox (driver gates supply tests) | — | Codex quota | none |
| LC-3B | DEV-LIFECYCLE-3B (Flutter gates, DRV-3) | No vacuous Flutter gate passes | lifecycle.py | `milestone/dev-lifecycle-3b-flutter-gates-20261016` 57f2d567 | AC tests `tests/dev_workflow/test_lifecycle_drv3_flutter_gates.py` (23 test fns) | codex_cli R2 ACCEPT WITH FINDINGS on 57f2d567, driver-verified; driver push eaeb10c1→57f2d567 (`uri-dl3b-run/c3/RECEIPT.md`) | n/a | INTEGRATED | Open LOW R2-01 (plan states outdated gate schema version) | — | — | none |
| LC-3C | DEV-LIFECYCLE-3C auditor fallback | (duplicate) | — | `milestone/dev-lifecycle-3c-auditor-fallback-20261016` 4ca4a02a (3 ahead) | state `uri-dl3c-run/r1`: R1 Codex QUOTA, R2 Claude AUTH → WAITING_FOR_MODEL (REPORTED) | none | — | NOT integrated; STOPPED as duplicate of LC-4 (commit 4ca4a02a message) | — | none (superseded) | — | Archive/preserve only |
| LC-4 | Auditor fallback (tiers 1-2) | Codex preferred, claude_cli fallback, NO_INDEPENDENT_REVIEWER block with self-recheck | lifecycle.py, lifecycle_providers.py, `tests/dev_workflow/test_lifecycle_auditor_fallback.py` (30 test fns) | `milestone/lifecycle-auditor-fallback-20261016` 348677b7 | 316 passed/5 skipped (above) | Codex r1 REJECT on 79fd4660; af-review-R1/R2/R3 = fresh read-only Explore subagents run by the UI V2 session, R3 ACCEPT WITH FINDINGS on 348677b7 (`D:/uri-dev/uri-ui-v2-freeze/af-review-R3/AUDIT_RESULT.json`, AF-S3-01/02 LOW). Class: subagent, NOT driver-verified. Driver run `LIFECYCLE-AUDITOR-FALLBACK-r3` = WAITING_FOR_MODEL on 8c362121 | Fallback path observed live only as UNAVAILABLE (QUOTA/AUTH) classification in r9-r12 runs | INTEGRATED by owner-approved FF 3e769fdf→348677b7 (`D:/uri-dev/lifecycle/LIFECYCLE-AUDITOR-FALLBACK/INTEGRATION_RECEIPT_348677b7.md`) | claude_cli fallback unusable until owner `claude` login; integration rested on subagent reviews which canonical SKILL.md line 116-119 itself calls "imported review (not driver-counted)" (see D) | Open LOW AF-S1-02/03/04/06, AF-S3-01/02 | owner login | Owner: `claude` sign-in |
| LC-5 | Reviewer tiers 3-5 (subagent / session / owner-attested), audit handoff, assurance classes | Keep reviewing when tiers 1-2 unavailable; record owner attestation separately | lifecycle.py (1193 lines changed), lifecycle_report.py, SKILL.md, `tests/dev_workflow/test_lifecycle_reviewer_tiers.py` (67 test fns) | `milestone/lifecycle-owner-attested-review-20261017` 67d45317 (16 ahead / 66 behind ec2fab54; worktree `D:/uri-dev/uri-owner-attested`) | Last complete full suites: 457cd5cc 394 passed/0 failed; 3dea0741 1 failed/407 passed (`test_r8_01_env_injected...` Windows PermissionError, intermittent, also on 1f44cf2b); 67d45317 `D:/uri-dev/lifecycle/suite_67d45317.log` = 64 bytes of dots, no summary → INCOMPLETE/NO_OUTPUT | r9 subagent ACCEPT WITH FINDINGS on older 063cfb7c (VERIFIED, later invalidated by r10 finding); r10 subagent REJECT on 457cd5cc; r11 subagent REJECT (R3-01, R3-02 blocking) on 3dea0741; r12 on 67d45317: tiers 1-2 UNAVAILABLE (QUOTA/AUTH), tier-3 `REVIEW_STARTED` 2026-10-17T18:15:36Z (nonce 77f5c732...), never collected; stage AUDITING (`D:/uri-dev/lifecycle/LIFECYCLE-REVIEWER-TIERS-r12/state/events.jsonl` seq 18) | none | NOT integrated | No review of 67d45317 at all; no complete suite on 67d45317 | Review 67d45317, full suite, owner integration approval | LC-4 (base) | See (c) |
| LC-6 | "Lifecycle V3.1" | Planned persistent task/cache state | none | — | — | — | — | NOT IMPLEMENTED; only "planned V3.1 persistent task/cache architecture" (`docs/dev_workflow/DEV_LIFECYCLE_3B_PLAN_AND_ACCEPTANCE.md:49`) and "Lifecycle V3.1 task state" listed out of scope (`docs/ui_v2/completion/00_COMPLETION_PLAN_AND_ACCEPTANCE.md:37`) | — | Plan + design | — | Owner scope decision |
| LC-7 | Persistent task ledger / history / recovery | Cross-task ledger | — | — | — | — | — | NO cross-milestone ledger exists. What exists: per-milestone `state_dir` with hash-chained `events.jsonl`, `state.json`, `receipt.json`, `AUDIT_HANDOFF.md`, resume via READY_TO_RESUME/CHECKPOINT/WAITING_FOR_MODEL (outside the repo, e.g. `D:/uri-dev/lifecycle/*`); AO-4 `state_manager.py` writes `docs/plans/<id>_STATE.md`; ids are config strings, not UUIDs | Fragmented across C:/Users/cheta/Development/uri-dl*-run and D:/uri-dev/lifecycle | Design if wanted (V3.1) | — | Owner decision |
| LC-8 | Milestone Manager | Milestone ledger/console | NOT in any repo ref (G1). Prototype only at `C:/Users/cheta/.gemini/antigravity/scratch/uri-milestone-manager-v1/` | — | none (no tests) | none | — | NOT in repo | Static JSON viewer; see (e) | — | — | Treat as unreviewed prototype |
| GR-1 | Graphify DEV skill + CLI | Code navigation for agents | `.agents/skills/graphify/SKILL.md` (v0.9.58), `graphify` CLI 0.9.58 on PATH, CLAUDE.md rules; canonical tracks only `graphify-out/.graphify_detect.json`, `.graphify_python`, `.graphify_root` | canonical | none (third-party tool) | n/a | `graphify update` ran in phase2ops (`docs/evidence/phase2/phase2ops/graphify_update.log`, 16199 nodes) | Tooling present; NO `graph.json` in canonical or audit worktree → CLAUDE.md query rule inert here; `graph.json` exists only in `C:/Users/cheta/Development/Uri/_V1/graphify-out` (2026-09-27, stale) and the uri-agent main checkout | Tracked `.graphify_detect.json` holds machine paths of `C:\Users\cheta\Development\uri-agent`; `graphify update .` would rewrite tracked files | — | — | Owner: keep out of product scope |
| GR-2 | Native Graphify index (M30) | System-level read-only pointer index of capabilities/skills/workflows/memory/services | `uri_core/core/graphify_index.py` (390 lines) | canonical | `test_graphify_index.py` 15 passed (T1, RUN-HERE, ec2fab54) | M30 STATE: "Self-audit verdict: ACCEPT" (`docs/plans/M30_GRAPHIFY_FOUNDATION_STATE.md:127`) = self-audit, not independent | M30 claims live startup check (REPORTED) | INTEGRATED | Docstring cites `test_graphify_index_authority_boundary.py`, which does not exist; the AST proof lives inside `test_graphify_index.py` | — | CapabilityDirectory, SkillMemory, MemoryStore | doc fix (LOW) |
| GR-3 | M34 Graphify hint activation | Feed skill/memory pointers to the Brain as `capability_index_hint`, killswitch `GRAPHIFY_HINT_ENABLED` | `uri_core/core/decision_engine.py:65,1062`, `uri_core/app/server.py` | canonical (78fb5e15) | `GraphifyHintActivationTests` 7 passed (T5) | Claude independent audit ACCEPTED, 171 tests rerun (`docs/plans/M34_GRAPHIFY_HINT_ACTIVATION_STATE.md:42-54`) | "User live-verified" 2026-09-19 on the legacy server (REPORTED) | INTEGRATED | Applies only to the legacy `uri_core/app/server.py` orchestrator path | — | — | — |
| GR-4 | GRAPHIFY-LEAK-1 | Per-user memory pointers only | `uri_core/app/server.py` `_MemoryScopedGraphifyView`; `tests/graphify/*`; `docs/graphify/GRAPHIFY_LEAK_1_PLAN_AND_ACCEPTANCE.md` | 9ae7c60c, 6c62281f → integrated e761ce8f | 15 passed (T2) | claude_cli R1 REJECT on 9ae7c60c, R2 ACCEPT WITH FINDINGS on 6c62281f, both driver-verified independent (`lifecycle-checkpoint/lifecycle-runs/GRAPHIFY-LEAK-1-final/RECEIPT.md` on branch `uri-repo/ccr-cab5ed06-9hwyc4` @301184ac, not in canonical) | not recorded | INTEGRATED; `server.py` hash approved in `scripts/ws_frozen_check.py` APPROVED (decision GRAPHIFY-LEAK-1/D12) | Open R2-01 LOW: `skill:` records in user views come from install-wide SkillMemory → GRAPHIFY-SKILL-1 listed only (`lifecycle-checkpoint/PROMPT_NONFROZEN_WORK.md:37`), never implemented | GRAPHIFY-SKILL-1 | frozen exception needed | Owner decision |
| GR-5 | Native graphify in the WORKING-SYSTEM path | Same hint for the paired/integrated server | `uri_core/core/paired_reasoning.py:78-110` (frozen Phase 1, 925ad45c) → `paired_coordinator.py:140` → `paired_brain.py:77` sends `canonical(prepared["request"])` to the Brain | canonical | `test_phase1_offline_components.py:233` asserts `prepared["graphify"].records`; NOT VERIFIED here (T6 needs materialized runtime) | no graphify-specific review | none graphify-specific | INTEGRATED (frozen) | Per-turn in-memory `build_index(capability_directory=...)` only (no skills/workflows/memory, no persisted file); `relevant_subset` result forwarded unfiltered (capability records, unlike M34's skill/memory filter); `GRAPHIFY_HINT_ENABLED` is not consulted on this path (only `decision_engine.py:1062` reads it) | Decide whether WS path should honour the killswitch/filter | frozen paired_reasoning.py | Owner/architecture decision (see d) |
| GR-6 | M23 graph store/engine | Per-user fact graph | `uri_core/core/graph_store.py`, `graph_engine.py`, `graph_ingest.py`, `graph_context.py` | canonical | 62 passed (T3) + isolation 4 passed with throwaway secret (T4b) | M23 VERIFIED (REPORTED via M30 STATE) | UNKNOWN | INTEGRATED | `test_graph_isolation.py` needs `URI_EXTERNAL_CREDENTIAL_SECRET` set | — | — | — |
| SK-1 | Dev skills | Agent guidance | `.agents/skills/{graphify,uri-development-lifecycle,uri-ux-design}`, `.claude/skills/uri-development-lifecycle` (differs from the `.agents` copy), `.agents_quarantine_2026-09-11/rules/*.md` (4 authority rule files), root `SKILL.md` (uri-development) | canonical | n/a | n/a | n/a | in repo | Two divergent lifecycle SKILL.md copies; `_V1` worktree has untracked `.agents/skills/impeccable-design/` (not in any commit) | — | — | Owner: pick one authoritative copy |
| SK-2 | skill_router_v1 / skill_evaluator_v1 / registry | Standalone skill scoring | root `skill_router_v1.py`, `skill_evaluator_v1.py`, `build_skill_registry_v1.py`, `uri_workspace/skill_registry.json` | canonical (last 38587b8f, 2026-09-04) | 87 passed (T7) | 2026-09-04 architecture audit docs (`SKILL_ROUTER_V1_ARCHITECTURE_AUDIT.md`) | none | in repo, DE-WIRED from runtime (`uri_core/core/orchestrator.py:221-223` comment; not imported by working-system modules, checked by import probe) | Dormant | — | — | Classify as dormant library |
| HA-1 | Harness adapters (Claude Code, Codex CLI) | Client-side external harness boundary | `uri_harness_adapters/__init__.py` (5577 B), `uri_core/client_runtime/harness.py` | canonical (925ad45c) | phase2 suites (not run here) | Phase 2 OQ accepted (REPORTED, memory `uri-phase2-operational-qualification`) | Codex NATIVE QUALIFIED run-scoped; Claude CLI BLOCKED (REPORTED) | INTEGRATED | — | — | — | out of this file's scope |
| HA-2 | Old `_V1` harness line | Harness/Connections/Console, harness-first edge | `preserve/harness-connections-console-20261003` f07f7d40 ("PARTIAL / ACCEPTANCE BLOCKED"), `claude/harness-first-edge` 86de4c02, `codex/harness-connections-console` 62d564cf, `preserve/v1-harness-voice-research-20261004` 6aa9c30b | merge-base e8e3b652, 804 behind canonical | not run | "NOT accepted" (commit message f07f7d40) | none | NOT integrated; superseded base | 494-579 files diff, own architecture | — | — | Preserve; do not merge |
| MC-1 | Mission Control / Skill Command Center / Developer Studio | UI modules | docs only: `docs/ui_v2/completion/02_INVENTORY_A_TO_E.md:29` (class E), office plans list them out of scope, lifecycle SKILL.md:43 names them in scope | — | none | none | none | NOT IMPLEMENTED in any of 179 refs (G1); "Developer Studio": zero hits anywhere | — | Design from scratch | — | Owner prioritisation |
| MCP-1 | Gemma worker / Qwen coordinator MCP bridges | Dev-only stdio bridges | `scripts/gemma_worker_mcp.py` (last 0da36dfa 2026-09-14), `scripts/qwen_coordinator_mcp.py` (8acbad5b 2026-09-10) | canonical | 29 passed/1 skipped (T8) | UNKNOWN | UNKNOWN | in repo | Gemma/Ollama out of test scope (owner, memory `uri-test-brain-qwen-moe-only`); no OpenRouter MCP exists | — | Ollama | — |

## (c) Pending candidate assessment

### 67d45317 — `milestone/lifecycle-owner-attested-review-20261017` (reviewer tiers 3-5)

- Base: merge of canonical 348677b7 (3dea0741), merge-base with ec2fab54 = 348677b7. 16 commits, cb6f5861 … 67d45317 (2026-10-17T23:43+05:30).
- Diff vs ec2fab54 (three-dot) = diff vs 348677b7: 4 files, +2335/-78 (`.claude/skills/uri-development-lifecycle/SKILL.md`, `scripts/dev_workflow/lifecycle.py`, `scripts/dev_workflow/lifecycle_report.py`, `tests/dev_workflow/test_lifecycle_reviewer_tiers.py`). Canonical has not touched these paths since 348677b7; `git merge-tree` clean (G2).
- Acceptance evidence: NONE on the exact commit. r12 (`D:/uri-dev/lifecycle/LIFECYCLE-REVIEWER-TIERS-r12`) state AUDITING, last event REVIEW_STARTED (tier-3 subagent, nonce 77f5c732…) with no REVIEW_RECORDED; `rounds/R3` has only `before.json` and `review_prompt.md`. Earlier rounds on predecessors: r9 AwF on 063cfb7c, then r10 REJECT (457cd5cc), r11 REJECT with 2 blocking (3dea0741); 67d45317 claims to repair R11-01..R11-03, unverified.
- Tests: tier tests 67 functions; no complete suite run on 67d45317 (log truncated, NO_OUTPUT). Last full suites: 457cd5cc 394 passed/0 failed; 3dea0741 1 failed (`test_r8_01_env_injected_and_removed_during_the_run_is_not_isolated`, WinError 5 on `.claude.json` rename: intermittent environment flake, seen also on 1f44cf2b).
- Risk: MEDIUM. Lifecycle governs every later acceptance; tier 3 lets a same-model subagent qualify a candidate, guarded by transcript/nonce/before-after checks (SKILL.md 136-157 on the branch). The driver-side SUBAGENT_VERIFIED check is the trust anchor and has had 10 REJECT rounds before; the latest repair is unreviewed.
- Frozen impact: none of the 4 files is in `ws_frozen_check` (no match for `dev_workflow`/`.claude/skills`); lifecycle.py reads `ws_frozen_check` for `protected_paths` only.
- Rollback: candidate is a pure fast-forward-able addition; rollback = do not integrate, or revert the 4 files to 348677b7 blobs; configs without tier commands are unaffected (driver keeps policy hash for configs without new keys — REPORTED in memory, not re-checked).
- Verdict: NOT READY. Needs (1) a full `tests/dev_workflow` run on 67d45317, (2) a completed independent review on 67d45317 (tier 1/2 now possible if Codex quota reset 2026-10-22 14:03 holds, REPORTED), (3) owner integration approval.

### Other pending items in scope

- 4ca4a02a (DL3C): stopped as duplicate; no action besides preservation.
- Receipt branches `receipts/dev-lifecycle-2-20261011` 86221a2b, `receipts/dev-lifecycle-3-20261015` e23321d1, `receipts/ui-v2-20261016` 64e74109: documentation only, not in canonical; they hold the review/receipt records cited above.
- GRAPHIFY-SKILL-1 (R2-01 LOW of GRAPHIFY-LEAK-1): never started; needs a frozen exception for `server.py`.

## (d) Graphify reconciliation

1. Two different things share the name.
   - Development skill/tool (GR-1): third-party `graphify` 0.9.58 used by agents for code navigation. It is not part of URI. In canonical it is configuration only: the graph itself (`graph.json`) is not tracked and is absent in the audit worktree. The only graphs on disk (`_V1`, uri-agent main) date from September and do not describe ec2fab54.
   - URI-native Graphify (GR-2..GR-5): URI's own runtime pointer index, `uri_core/core/graphify_index.py`. It has no connection to the dev tool.
2. Native implementation: build/refresh/load/save/`relevant_subset`. Never raises. It has no authority imports, and the AST proof passes (T1). The persisted index is `uri_workspace/graphify_index.json` (gitignored, `.gitignore:96`). It is built at legacy-server startup from live collaborators (`server.py` ~941-1001). Canonical ships no index file.
3. Runtime connections:
   - Legacy path: `uri_core/app/server.py` holds the shared index plus a per-user `_MemoryScopedGraphifyView` (GRAPHIFY-LEAK-1). `decision_engine.py:1062` reads it under the `GRAPHIFY_HINT_ENABLED` killswitch, keeping only `skill` and `memory_pointer` records (M34).
   - Working-system path: `run_uri_integrated_server.py` (frozen) → `paired_server.create_app` → `PairedCoordinator` → `paired_reasoning.prepare_canonical_context`. This path builds a fresh capability-only index every turn. It passes `relevant_subset(text, 5)` as `capability_index_hint` with no kind filter and no killswitch, and `paired_brain.py:77` sends it to the Brain inside the decision request. So native Graphify IS live in the current serving path, as a reduced variant that behaves differently. Static evidence only; no graphify-specific live record was found.
4. Tests: 15 + 15 + 7 + 62 + 4 RUN-HERE pass at ec2fab54. The paired-path assertion (T6) is NOT VERIFIED here because it needs the materialized runtime.
5. Reviews:
   - M30: self-audit ACCEPT.
   - M34: independent Claude audit ACCEPTED, and the user live-verified it on the legacy server on 2026-09-19.
   - GRAPHIFY-LEAK-1: driver-verified claude_cli R2 ACCEPT WITH FINDINGS, integrated e761ce8f.
   - The working-system variant (GR-5) was never reviewed as a Graphify feature. It entered with the frozen Phase 1 core at 925ad45c.
6. Correct classification: native Graphify is IMPLEMENTED, TESTED, INTEGRATED and FROZEN.
   - Legacy path: ACCEPTED and live-verified on 2026-09-19 (reported).
   - Working-system path: wired but divergent (capability-only, no killswitch, no kind filter). It is not separately reviewed or live-verified.
   - Open items: R2-01 / GRAPHIFY-SKILL-1. The two paths also differ in behaviour (finding GRF-P0-1, LOW/MEDIUM design gap, owner/architecture decision; not a leak: capability pointers only).
   - Antigravity Part 1 "D. Partially Implemented" is INCORRECT. It assessed the dev skill (`.agents/skills`), not URI's runtime module.

## (e) Antigravity claim verdicts

Sources: `C:/Users/cheta/.gemini/antigravity/brain/2f49f16d-03d7-44e2-8bf8-777a43b24ac1/{URI_DEV_AUDIT_20261020.md, URI_HISTORICAL_RECOVERY_AUDIT_20261020.md, URI_AUTHORITATIVE_MASTER_REGISTER.md}` and the scratch prototype.

| Claim (source:line) | Verdict | Evidence |
|---|---|---|
| Graphify "D. Partially Implemented" (DEV_AUDIT:130) | INCORRECT | (d) above |
| Lifecycle V3/Auditor Fallback "A. Implemented & Verified … Accepted (AF-R3) … Ready" (DEV_AUDIT:146) | PARTIAL | Integrated 348677b7, 316 passed. But AF-R3 is a subagent review, not driver-verified, and the claude_cli fallback cannot run until the owner signs in. "Ready" is overstated. |
| "Persistent UUID task IDs with strict sanitization" and "Gate Transition Machine DRAFT→INTENT_DISCOVERED→PLAN_APPROVED→EXECUTION→VERIFIED→COMPLETED" at 348677b7 (MASTER_REGISTER:87-89; RECOVERY:37,148,196) | INCORRECT | `git grep INTENT_DISCOVERED\|PLAN_APPROVED` at ec2fab54: 0 hits. The real states are `scripts/dev_workflow/state_machine.py:30-46` (DRAFT, AWAITING_USER_APPROVAL, … READY_TO_RESUME) and the driver's PLAN/AUDITING/FIXING/VERIFYING/VERIFIED/COMPLETE/BLOCKED/WAITING_FOR_MODEL. The only `uuid` in dev_workflow is the reviewer session id (`lifecycle_providers.py:558`). Milestone ids are config strings. UUID ledger ids exist only in the runtime OI answer-planner ledger (`tests/oi` `test_ledger_ids_are_uuids_only`), which is a different subsystem. |
| MS-LIF-01 evidence = `test_approval_gate.py`, `test_authoritative_facts_immutability.py`, `test_audit_trail.py` (MASTER_REGISTER:117) | INCORRECT attribution | These are root-level runtime uri_core tests, not lifecycle tests. The lifecycle tests are `tests/dev_workflow/*`. |
| Milestone Manager V1 "36/36 files verified present … 0 discrepancies" (MASTER_REGISTER:226) | NUMBER REPRODUCED, MEANING UNSUPPORTED | See the notes below this table. |
| Lifecycle "V3.1" exists / "DL3.1 lifecycles stalled" (RECOVERY:18,98; DEV_AUDIT:260) | INCORRECT | V3.1 is only a planned or out-of-scope label (LC-6). There is no "DL3.1" in the repo. |
| Reviewer Tiers R12 "Repairs completed … Pass … Blocked (Quota)" (DEV_AUDIT:147,166) | PARTIAL | The blocked state is correct for tiers 1-2. But a tier-3 review was started and abandoned, there is no complete test run on 67d45317, and the last completed review is a REJECT on 3dea0741. |
| MS-MCP-01 / INIT-14 "Antigravity & OpenRouter MCPs … 43224b1a … Approved and implemented" (MASTER_REGISTER:124; RECOVERY:44) | UNSUPPORTED | `git cat-file -t 43224b1a`: not a valid object (also absent in the uri-agent checkout). The files exist (MCP-1) and their tests pass (T8), but no approval record was found, there is no OpenRouter bridge, and the bridges target local Ollama, which is out of test scope. |
| Mission Control / Skill Command Center "Class E, zero implementation in any branch" (MASTER_REGISTER:162-163; RECOVERY:41-42) | CONFIRMED | G1 found no code in any of the 179 refs. |

Milestone Manager V1 "36/36" claim, details:
- `verify` only checks that each relative path exists under any of 6 roots. Those roots include non-canonical worktrees such as `D:/uri-dev/uri-owner-attested` and `uri-ui-controls-typo`. The check looks at no commit, content or test.
- The ledger cites nonexistent SHAs: 43224b1a (MS-MCP-01) and 36395b09 (MS-OFF-02).
- MS-UX-03 marks Brain Quick Controls as "Staged", but feaabe3f is an ancestor of ec2fab54. It also conflates this with UI-CONTROLS-TYPO e9ee7409.
- MS-LIF-02 cites `test_audit_comparison.py`, which is unrelated to reviewer tiers.
- The tool is an unreviewed, untested static viewer, not "autonomous governance". It is not in any repo.

## (f) Evidence gaps

| Gap | Affects verdict? |
|---|---|
| No complete `tests/dev_workflow` run on 67d45317 (not run here: ~42 min > budget) | Yes, (c) stays NOT READY |
| Paired-path graphify test (T6) not runnable outside the materialized runtime; no live record shows `capability_index_hint` content in a working-system turn | No for classification; yes for "live-verified" (stays NOT VERIFIED) |
| M34 user live verification and the M30 live-startup check are REPORTED in state docs only | No (marked reported) |
| DL3A/DL3 open LOW lists (C3-01 etc.) taken from memory and receipts, not re-derived from round.json | No |
| Phase 2 harness qualification (HA-1) not re-verified here | No (out of scope, reported) |
| Whether configs without tier keys keep their policy hash on 67d45317 | Low; affects rollback claim only |
| `git merge-tree` wrote loose objects (no refs) | No |

## Policy (D): development pause and reviewer availability, written sources

- Canonical `.claude/skills/uri-development-lifecycle/SKILL.md` (ec2fab54):
  - lines 97-121: Codex primary; claude_cli fallback needs `claude auth status` loggedIn true; "independent auditing is mandatory, a provider never is" (2026-10-16); `reviewer_fallbacks` chain; all unavailable ⇒ BLOCKED `NO_INDEPENDENT_REVIEWER`, progress kept, next `run` re-checks, no owner unblock; signing in is never done by the driver or coordinator.
  - lines 116-121: a separate Claude session or agent review is recorded with `import-review` and "never an independent ACCEPT … does not allow VERIFIED or canonical integration".
  - line 120: nothing available ⇒ `INDEPENDENT AUDIT: BLOCKED`; never self-review.
  - line 163: exit code 5 WAITING_FOR_MODEL.
- `docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:13,34,47,50`: provider roles, the wait/resume state path, the no-false-ACCEPT rule, and quota ⇒ CHECKPOINT + WAITING_FOR_MODEL.
- `ORCHESTRATION.md:137-143,325-333`: waiting is a valid state; the permanent quota-exhaustion invariant (2026-09-11).
- Tiers 3-5 and the owner decisions of 2026-10-17 ("AUTONOMOUS INDEPENDENT REVIEW"; subagent or session ACCEPT qualifies with no owner inspection; owner approval still mandatory for canonical integration) are written ONLY on the unintegrated branch 67d45317 (SKILL.md lines 116-181, 301-319) and in memory notes `uri-lifecycle-reviewer-tiers.md` and `uri-auditor-fallback-policy.md`.
- Finding POL-P0-1 (MEDIUM, governance): canonical policy text contradicts practice. Integrations 348677b7 and ec2fab54 were accepted on fresh-subagent reviews that were "not driver-verified" (`BRAIN-QC-CLOSURE/REVIEW_QCC_R3.md:5`), plus explicit owner approval. Canonical SKILL.md still classes such reviews as imported and not sufficient for integration. The owner decision that authorises the practice is not in canonical. Repair: integrate or re-state the 2026-10-17 decisions in canonical, or record each such integration as an owner exception.

## Self-review against AC1-AC7

- AC1: every SHA was checked with `merge-base --is-ancestor`. I confirmed that 43224b1a and 36395b09 do not exist.
- AC2: T1-T9 give exact commands. Rows without RUN-HERE say REPORTED and give the log path.
- AC3: every verdict gives its record path and review class. The M30 self-audit is labelled as a self-audit.
- AC4: the 67d45317 suite (NO_OUTPUT), the r12 tier-3 review (started, never collected) and T6 (errors) are not counted.
- AC5: GR-1 is kept separate from GR-2..GR-5. The working-system wiring was traced by code reading plus an import probe. Correction during drafting: I first assumed native Graphify was legacy-only. `paired_reasoning.py:78` proves it is used in the working-system path, and GR-5 and (d) now record this.
- AC6 and AC7 are met in (e) and (f).
