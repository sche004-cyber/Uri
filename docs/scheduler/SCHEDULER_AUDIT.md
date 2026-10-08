# URI Scheduler — Independent Audit Record

Reviewer: Codex CLI 0.158.0, model `gpt-6-sol`, reasoning `medium`, read-only sandbox, through the local `codex-exec`
bridge (owner rule: audits run on Codex). Review clone: `C:\Users\cheta\Development\sra` (`core.autocrlf=false`), diff
`99f8041..<candidate>`. Every Codex finding was re-checked against the code by Claude before being accepted or disputed.

## Round 1 — candidate `152c8e9` — **REJECT**

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| 1 | Blocking | API token authenticates the caller, but the caller names its own `principal` | confirmed (`service.py` read `principal` from the body) | **repaired**: one principal per service (`--owner`); mismatch → 403 `PRINCIPAL_MISMATCH`; reads filtered by owner; test added |
| 2 | Blocking | Claude gets Read/Edit/Write with no enforced filesystem boundary | partly confirmed. Claude Code docs: `dontAsk` denies every un-approved Edit/Write and anything outside the working directory — which also means the accepted profile could not write its output at all | **repaired + limitation**: `--allowedTools Edit(./**) Write(./**)` scoped to the per-attempt workspace; boundary = Claude Code permission engine, not an OS sandbox; not yet verified live; owner acceptance requested |
| 3 | Blocking | restart requeues every interrupted occurrence even if the work had finished | confirmed | **repaired**: recovery reconciles artifact rows and the supervisor ledger first (`COLLECT_PENDING`, absence-proven requeue, `NEEDS_ATTENTION`); 5 tests |
| 4 | High | calendar refresh / later years schedule dates the owner never saw | confirmed (proposal preview is 400 days) | **repaired**: only shown dates are confirmed; others `AWAITING_CONFIRMATION` until the owner confirms; tests + UI *Confirm date* |
| 5 | High | exceptions in package/execution leave the occurrence `RUNNING` | confirmed | **repaired**: every claimed occurrence is settled (`_execute_settled`); params validated at proposal; test |
| 6 | High | cancelling a job leaves pending reviews approvable | confirmed | **repaired**: cancel closes every open state; review refuses `JOB_CANCELLED`; test |
| 7 | High | cancel/dispatch race: claim ignores job state | confirmed | **repaired**: job state inside the claim's compare-and-set; test |
| 8 | High | `festival.key` reaches the output file name (path traversal) | confirmed | **repaired**: slug validation at proposal, slugged names, resolved-path containment check; test |
| 9 | Medium | oversize GIF can still become a candidate | confirmed | **repaired**: size budget is part of `ok`; test |
| 10 | Blocking | real Claude generation not run | confirmed (documented as NOT RUN) | **open — owner action**: Claude CLI login; cannot be repaired by the agent |

## Round 2

(appended below after the review runs)
