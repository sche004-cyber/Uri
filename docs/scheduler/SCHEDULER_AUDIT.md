# URI Scheduler — Independent Audit Record

Reviewer: Codex CLI 0.158.0, model `gpt-6-sol`, reasoning `medium`, read-only sandbox, through the local `codex-exec`
bridge (owner rule: audits run on Codex). Review clone: `C:\Users\cheta\Development\sra` (`core.autocrlf=false`), diff
`99f8041..<candidate>`. Every Codex finding was re-checked against the code by Claude before being accepted or disputed.

## Round 1 — candidate `152c8e9` — **REJECT**

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| 1 | Blocking | API token authenticates the caller, but the caller names its own `principal` | confirmed (`service.py` read `principal` from the body) | **repaired**: one principal per service (`--owner`); mismatch → 403 `PRINCIPAL_MISMATCH`; reads filtered by owner; test added |
| 2 | Blocking | Claude gets Read/Edit/Write with no enforced filesystem boundary | partly confirmed. Claude Code docs: `dontAsk` denies every un-approved Edit/Write and anything outside the working directory — which also means the accepted profile could not write its output at all | **repaired + limitation** (historical; superseded by R2-4: only `Edit(./**)` is passed): `--allowedTools Edit(./**) Write(./**)` scoped to the per-attempt workspace; boundary = Claude Code permission engine, not an OS sandbox; not yet verified live; owner acceptance requested |
| 3 | Blocking | restart requeues every interrupted occurrence even if the work had finished | confirmed | repaired in `04e9eaa` (reconcile artifact rows and the supervisor ledger first); round 2 found a remaining crash window, closed in round-2 repairs |
| 4 | High | calendar refresh / later years schedule dates the owner never saw | confirmed (proposal preview is 400 days) | **repaired**: only shown dates are confirmed; others `AWAITING_CONFIRMATION` until the owner confirms; tests + UI *Confirm date* |
| 5 | High | exceptions in package/execution leave the occurrence `RUNNING` | confirmed | **repaired**: every claimed occurrence is settled (`_execute_settled`); params validated at proposal; test |
| 6 | High | cancelling a job leaves pending reviews approvable | confirmed | **repaired**: cancel closes every open state; review refuses `JOB_CANCELLED`; test |
| 7 | High | cancel/dispatch race: claim ignores job state | confirmed | **repaired**: job state inside the claim's compare-and-set; test |
| 8 | High | `festival.key` reaches the output file name (path traversal) | confirmed | **repaired**: slug validation at proposal, slugged names, resolved-path containment check; test |
| 9 | Medium | oversize GIF can still become a candidate | confirmed | **repaired**: size budget is part of `ok`; test |
| 10 | Blocking | real Claude generation not run | confirmed (documented as NOT RUN) | **open — owner action**: Claude CLI login; cannot be repaired by the agent |

## Round 2 — candidate `04e9eaa` — **REJECT**

Round-1 status per Codex: F1, F4, F5, F6, F7, F8, F9 RESOLVED; F2 PARTIAL (relies on the permission engine; no live
evidence; path-scoped `Write` rules are not consulted); F3 PARTIAL (new crash window). F10 documented truthfully; Codex
states it alone does not block acceptance as a development candidate, only claims of live end-to-end qualification.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R2-1 | Blocking | `_resume_collection` claimed the occurrence and reopened the attempt in two transactions; a crash between them made `recover()` (which looked only at open attempts) requeue completed work | confirmed | **repaired**: claim + reopen in one transaction; `recover()` reconciles the LATEST attempt whether ended or not; test `test_r2_crash_between_collection_claim_and_attempt_reopen_never_reruns` |
| R2-2 | High | an exception after the harness completed (render/IO/recording) went to `_retry_or_fail`, re-running Claude | confirmed | **repaired**: `_post_harness_failure` retries COLLECTION from the workspace with backoff (`COLLECT_PENDING`), bounded by the attempt budget; `_execute_settled` consults the supervisor before choosing; test `test_r2_render_failure_after_harness_retries_collection_only` |
| R2-3 | Medium | docs overstated "duplicates impossible" | confirmed | **repaired**: architecture/ledger state the exact scope of the guarantee (re-run only when the ledger proves no start or no effect; otherwise owner) |
| R2-4 | Medium | `Write(./**)` is not consulted; `Edit(./**)` is the operative rule | confirmed against the Claude Code permissions documentation | **repaired**: only `--allowedTools Edit(./**)` is passed; docs explain it; limitation retained (permission engine, not OS sandbox; not observed live) |

## Round 3 — candidate `02938ca` — **REJECT**

Codex: R2-1 RESOLVED, R2-4 RESOLVED (live enforcement unverified; owner-acceptance limitation), R2-2/R2-3 PARTIAL because of
R3-1/R3-2. F10 and the F2 limitation confirmed as owner-gated items, not reasons for rejecting a development candidate.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R3-1 | High | a COMPLETE supervisor task whose output is missing/invalid goes to `_retry_or_fail` and re-runs Claude, contradicting the no-rerun claim | confirmed; this is intended behaviour (nothing usable exists), but it was undocumented and the docs claimed no rerun | **repaired (documented as a distinct authorized retry)**: "Content retry" defined in the architecture (policy budget, backoff), receipts carry `content_retry: true`, ledger and duplicate-guarantee text updated |
| R3-2 | High | an exception after the artifact insert (e.g. in `_finish`) sends the attempt to collection again, creating a second version of the same work | confirmed | **repaired**: `_settle_recorded_artifact` files the attempt's existing artifact for review in `_post_harness_failure` and at the start of `_resume_collection`; test `test_r3_failure_after_artifact_insert_does_not_duplicate` |
| R3-3 | Low | audit row 2 still shows `Edit(./**) Write(./**)` | confirmed | **repaired**: row labelled historical, pointing to R2-4 |

## Round 4

(appended after the review runs)
