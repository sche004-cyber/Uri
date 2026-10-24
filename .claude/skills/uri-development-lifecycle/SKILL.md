---
name: uri-development-lifecycle
description: Default process for URI DEVELOPMENT milestones in this repository - new features, development milestones, significant bug fixes, security repairs, runtime changes, UI changes and multi-component integrations. Drives Research -> Plan -> Implement -> Test -> Independent Audit (Codex first, else a separate Claude process) -> Repair -> Re-audit -> Live UI qualification on Windows with a UX and onboarding loop -> Final independent acceptance -> Integrate -> Receipt and qualification record automatically, so the owner never has to ask for an audit, a live test or relay findings. Invoke as `/uri-development-lifecycle <milestone-id>`. Do NOT use for URI user conversations, URI runtime office or document tasks, or anything the URI Brain does at runtime; URI Office development milestones are in scope. For milestones it supersedes the older `uri-development` skill.
---

# uri-development-lifecycle

The deterministic engine is `scripts/dev_workflow/lifecycle.py` (an extension of AO-4 `scripts/dev_workflow`).
You — the coordinator — plan, configure, start it and report. You never review your own work and you never
transcribe a verdict into ACCEPT. Reference: `docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md` (section 8 holds
the UI-first live qualification rules in full).

## The lifecycle (owner directive 2026-10-15, DEV-LIFECYCLE-3)

One lifecycle; stages may iterate, and independent review runs throughout, not only at the end. No stage bypasses
security, owner-approval, frozen-file, stop or repair rules.

| # | Lifecycle stage | Where it happens (skill section) |
|---|---|---|
| 1 | Research and discovery | you, Stage 1 (inspect real code, services and earlier evidence first) |
| 2 | Plan and acceptance criteria | you, Stage 1 — UI journey criteria included for user-facing work |
| 3 | Owner approval where required | Stage 1 owner-only decisions; driver `OWNER_*` blocks |
| 4 | Isolated implementation | Stage 2, candidate branch + worktree |
| 5 | Automated functional testing | targeted tests (you) + driver gates |
| 6 | Independent code and security audit | driver rounds (auditor selection below) |
| 7 | Live end-to-end UI verification | you, Stage 8 below, on the Windows runtime |
| 8 | UX and onboarding improvement | Stage 8 UX loop |
| 9 | Live retest and regression | Stage 8 loop: driver revision run on the repaired SHA + live retest |
| 10 | Final independent acceptance | final driver run on the SHA that holds the qualification record |
| 11 | Controlled canonical integration | driver integration, only with a recorded stage-11 authorisation (standing policy or explicit owner approval) |
| 12 | Integration receipt and qualification record | driver receipt + UI qualification record |

The skill's own section headings (Stage 1, Stage 2, Stages 3–7, Stage 8) are steps of this skill, not the
lifecycle numbers in the first column.

## When it applies

- Applies by default to: features, milestones, significant bug fixes, security repairs, runtime/UI changes,
  multi-component integrations.
- Lightweight path (no driver run): documentation-only changes with no code, test, config or governance-rule
  change. Still verify links and facts you assert, and say that the light path was used.
- In scope: development milestones for any URI component — URI Core integrations, URI Office, Web and Social
  Intelligence, Browser Assistance, URI Companion, A2UI, Voice, Skills and Mods, Mission Control, Skill Command
  Center, hardware integrations and every future module.
- Never: user conversations, URI runtime office or document tasks (what URI does for a user at runtime), URI
  runtime skills (this skill is not in
  `uri_workspace/skill_registry.json` and must not be added there).

## Stage 1 — Plan (you)

1. Verify the canonical baseline yourself; do not trust earlier documents. Canonical is the repository
   `https://github.com/sche004-cyber/Uri`, branch `integration/git-sync-20261008`. Find the ONE remote that points
   at it (`git remote -v`; in the owner's local clones it is `uri-repo`, and `origin` is `uri-agent`, which lacks the
   branch), then `git ls-remote <that remote> integration/git-sync-20261008`. Empty output, no matching remote or
   several matching remotes is BLOCKED, never "no baseline".
2. Write the plan with acceptance criteria FIRST (CLAUDE.md Verification-First standard), e.g.
   `docs/<area>/00_PLAN_AND_ACCEPTANCE_CRITERIA.md`. Classify each capability: `USER_FACING` (has its own UI),
   `INDIRECT` (no own UI; qualified through the user-facing workflow or consumer that exposes it) or `INTERNAL`
   (pure infrastructure; say why there is no UI and how it is verified instead). For `USER_FACING` and `INDIRECT`
   work the criteria include the UI journeys of reference section 8 (discover, navigate, operate, see progress,
   recover from errors, inspect output, repeat), first-time and returning user.
3. List owner-only decisions now (frozen-path changes, new dependencies, credentials, production, push rights).
   Do not start work that needs one; record it as a blocker.
4. Create the milestone config from `docs/dev_workflow/lifecycle/TEMPLATE.json` → `docs/dev_workflow/lifecycle/<milestone>.json`:
   `canonical_url`, baseline (`remote_branch` + the `expect` SHA you verified; the driver finds the remote by URL),
   candidate branch + worktree (outside the main checkout), criteria file, `review_focus`,
   `protected_paths` (`"ws_frozen_check"` = the frozen list), `permitted_paths`, gates, reviewer/implementer
   providers, limits, integration policy (`authorized: false`; integration is decided and performed at stage 11,
   see "Integration preconditions and authorisation", not by changing this field).
   Put `state_dir` OUTSIDE the candidate worktree. Keep the template's UX `review_focus` lines and its
   `environment_notes` (auditor evidence classes) for user-facing work.
5. Select the auditor now (section "Auditor selection"); a provider change after the first run is a config change
   (BLOCKED CONFIG), so choose before it.

## Auditor selection (owner directive 2026-10-15)

1. **Primary: Codex** (`"reviewer": {"provider": "codex_cli", ...}`). Before the first run check that it can
   really work: `codex --version`, `codex login status` ("Logged in"), a one-line probe with the configured model
   (`echo "Reply PROBE_OK" | codex exec -m <model> --sandbox read-only --skip-git-repo-check -`; on 2026-10-15
   `gpt-6-sol` worked and `gpt-6.1-sol` was refused for a ChatGPT login), a sandbox probe in the candidate checkout
   that must run a shell command in the driver's reviewer environment: `CODEX_HOME` set to a new temporary folder
   holding only a copy of `auth.json`, plus `-c project_doc_max_bytes=0` and, on Windows, `-c
   windows.sandbox="unelevated"` (the driver adds the same flag since DEV-LIFECYCLE-3A) (`echo "Run git rev-parse
   HEAD and print its output" | codex exec -m <model> -c project_doc_max_bytes=0 -c windows.sandbox="unelevated"
   --sandbox read-only -C <checkout> -`); the SHA must come back, because a login probe cannot detect a sandbox that
   refuses commands. Always set `reviewer.model` (the
   reviewer gets a fresh CODEX_HOME, so `~/.codex/config.toml` does not apply), and check that one `codex` resolves
   on PATH (the driver's `provider_available` and reviewer binding). The `candidate` SHA in a round's result proves
   nothing (the prompt contains it): judge inspection from `tests_run` and `inspected`. An invocation that was only
   attempted is not an audit.
   Windows history: in DEV-LIFECYCLE-3 R1 (2026-10-15) the driver's fresh CODEX_HOME had no `[windows] sandbox`
   setting, Codex rejected every shell command and its review inspected nothing. DEV-LIFECYCLE-3A fixed the driver
   (it passes `-c windows.sandbox="unelevated"` on Windows). A passing probe makes Codex usable; the first
   `codex_cli` round of each new config must still show inspection before you rely on it. The driver does not read
   `tests_run`: check it yourself after every Codex round. A round whose commands were all BLOCKED, or whose
   `tests_run` and `inspected` are empty, is a Codex failure whatever its verdict — an ACCEPT from it never supports VERIFIED, D1 or any report of
   independent acceptance; go to the fallback.
2. **Fallback: a separate Claude process** (`"provider": "claude_cli"`; needs `claude auth status` loggedIn true).
   Use it when Codex is missing, logged out, out of quota, cannot reach the repository or exact candidate commit,
   or fails to finish. Record the fallback reason and the reviewer identity in the plan and the qualification
   record. Do not retry a Codex failure that is already established for this run.
   **In-driver chain (owner policy clarification 2026-10-16: independent auditing is mandatory, a provider never
   is):** set `"reviewer_fallbacks": [{"provider": "claude_cli", ...}]` and optionally
   `"reviewer_selection": {"max_attempts": 2}`. The driver tries the preferred reviewer first in every round; quota,
   sign-in (AUTH) and not-found move to the next reviewer at once; failures, timeouts, SHA mismatch and unverified
   independence are retried within `max_attempts`. Every reviewer in the chain is bound at PLAN and must pass the
   same independence checks (bound CLI, driver-made config, containment, distinct session, integrity); acceptance
   never depends on the provider name (the Claude Code session running the driver, repair and diagnosis sessions are
   never the reviewer). Every reviewer unavailable or failing (quota, sign-in, not found, disconnect) ⇒ BLOCKED
   `NO_INDEPENDENT_REVIEWER` with the reasons; progress is kept and the next `run` re-checks availability itself
   (preferred reviewer first, `REVIEWER_RECHECK` event) — no owner unblock. Reviewers that returned results for
   another commit or whose independence could not be verified ⇒ BLOCKED `NO_REVIEWER`, an owner matter.
   Signing in (Codex, `claude`) is never done by the driver or the coordinator. Attempt counters are derived from
   the hash-chained events.
   Each round records `reviewer_index` and an `outcome` (ACCEPT, ACCEPT_WITH_FINDINGS, REJECT, UNAVAILABLE, FAILURE,
   SHA_MISMATCH, INDEPENDENCE_UNVERIFIED).
3. **Outside-driver fallback**: if neither CLI can run, a separate Claude session (new thread, agent or cloud
   session; read-only; no implementation or repair authority; given requirements, repository state, diff and
   evidence — never the implementer's conclusion) may review. Record its result with `import-review`. It routes
   findings to repair. Report it as "imported review (not driver-counted)", never as an independent ACCEPT: under
   owner decision D1 it does not allow the driver's VERIFIED or integration by the driver; a driver-counted round
   still does. Work accepted through the Lifecycle V3.1 fallback path ("Review paths", `task_ledger accept`) is
   integrated as in stage 11 "Fallback-accepted work".
4. Nothing independent available ⇒ report `INDEPENDENT AUDIT: BLOCKED`. Never self-review instead.
5. If Codex fails during a run (WAITING_FOR_MODEL, or any round whose commands were all BLOCKED or whose
   `tests_run` and `inspected` are empty — the driver may
   then stop BLOCKED NO_ACTIONABLE_FINDINGS or even reach VERIFIED), do not edit the bound config: start a revision
   config (see "Revision configs") with `claude_cli` and a full audit from round 1.

## Persistent task ledger (Lifecycle V3.1, 2026-10-21)

`scripts/dev_workflow/task_ledger.py` keeps every development task across sessions, models, worktrees and restarts
(one SQLite file outside every worktree: `URI_TASK_LEDGER`, default `~/.uri-dev/task_ledger.sqlite3`). It does not
replace the driver: driver runs stay the source of review rounds, gates and integration; the ledger links them
(`link-v3`, `sync-v3`, `import-v3`, read-only) and adds what the driver lacks: task ids, context, write-ahead steps,
claims, leases, recovery, handoffs. Milestones, roadmap and owner decisions belong to the Milestone Manager.

- Start of a session: `task_ledger recover --actor claude:<session>`, then `task_ledger handoff <task>` - the
  handoff (also written to `<ledger dir>/handoffs/<task>.md`) is the starting point, not the chat.
- While working: `claim` the task, `step-start` before a step and `step-end` after it, `add` decisions,
  constraints, evidence and the `next_action`, `head` for each commit, `test` with its log for each gate run.
- Review paths (owner clarification 2026-10-21): the driver's independent review (Codex, then claude_cli, in the
  reviewer chain) is **primary**. A fresh isolated Claude or Codex subagent/session review is a **fallback** only
  when that mechanism cannot operate: record it with `task_ledger review` (the verdict is re-parsed from the
  reviewer's own output and bound to the exact commit). `task_ledger accept` takes a fallback verdict only when a
  linked driver run's hash chain shows `NO_INDEPENDENT_REVIEWER` on that exact commit, never over a driver verdict
  on that commit, and only with a passing test result recorded on that commit. Fallback reviewers never lower the
  bar: same exact-commit evidence, same findings rules, same gates, a persistent receipt. Item 3 of "Auditor
  selection" (imported review not driver-counted) still governs the driver's own state; the ledger records the
  fallback path and its basis.
- Development pause: `availability --dev claude|codex --unavailable` for both pauses every task with a checkpoint;
  only Claude or Codex, recorded available again, can `resume`. Antigravity and subagents can never resume,
  transition or accept (Antigravity may add notes/evidence).
- Canonical integration is unchanged (driver `integration`, authorised as in "Integration preconditions and
  authorisation"); `task_ledger integrated`
  only records it from ancestry and the receipt.

## Development memory, supervised tests, housekeeping (LIFECYCLE-V3.1-STORAGE)

- **Session start:** run `python -m scripts.dev_workflow.devmemory brief`. It is a compact, token-budgeted digest of active tasks, next actions, open blocking findings, open owner decisions, lessons and environment limits. Then run `task_ledger handoff <task>` for the task you continue, and use `devmemory recall "<topic>"` on demand. The index is derived and rebuildable; the ledger, the Milestone Manager and `decisions.md` stay the sources. Record reusable knowledge with `devmemory remember <task> lesson|failed_approach|environment|procedure "<text>" --actor ...`, which writes to the ledger.
- **Tests you wait on:** start them with `python -m scripts.dev_workflow.testrun start --name <n> --timeout <s> [--stall <s>] [--task <T> --actor <A>] -- <cmd>`, and wait with `testrun wait <run> --timeout <s>`. Never wait with a loop that greps a log for a marker (2026-10-22 watcher incident). Completion comes from the process exit status. `--lock` refuses duplicate concurrent runs. `--reuse` returns an earlier result only for the identical clean tree and command. `testrun select` is advisory and never replaces a mandatory gate.
- **After integration:** `python -m scripts.dev_workflow.housekeeping inventory ... --out plan.json` is a read-only dry run. Show the plan to the owner. Then run `apply --plan plan.json --journal-dir <dir>`. It removes only clean, merged, unreferenced, idle worktrees, missing-worktree registrations (one at a time, never a global prune) and caches, plus merged branches when asked. Driver work trees of a lifecycle run that is not COMPLETE are protected. Everything else needs the owner's `--approve <id>`, and approved items with uncommitted work or evidence are archived and verified first. Evidence directories are never removed, only archived (`archive`, `verify-archive`, `restore`). Destructive cleanup on the owner's machine needs the owner's approval of the plan.

## Revision configs

A revision (`<milestone>-c` for a new auditor, `<milestone>-u<n>` after a UX repair, `<milestone>-final`) is a new
config file with a NEW `milestone` id and a NEW `state_dir`. Reusing a `state_dir` loads the old `state.json`, and
the changed config hash stops the run BLOCKED (CONFIG) until the owner unblocks. Keep the same baseline. The
candidate SHA is not a config field: it is the candidate worktree's HEAD when the run starts, so commit first.

## Stage 2 — Implement

Implement in the candidate worktree only (or give the task to a `claude_cli` implementer). Commit there. Run the
targeted tests. Never edit the canonical checkout, protected paths, or other sessions' worktrees.
One milestone has one branch and one worktree; each of its driver runs has its own config, milestone id and
`state_dir` (a revision, see "Revision configs"). Its findings, decisions and evidence stay in that milestone's
records. Never cherry-pick, rebase, reset or merge another thread's branch into a
milestone, never run another thread's gates and never use its GPU reservation. A fix the milestone needs in shared
tooling (for example the driver) is its own milestone with its own branch, review and integration; a milestone may
be based on such a prerequisite milestone of the same thread only when its plan says so, and the two are integrated
in order.

## Stages 3–7 — hand over to the driver (automatic)

```
python -m scripts.dev_workflow.lifecycle run docs/dev_workflow/lifecycle/<milestone>.json
```

Run it in the background; it can take hours. It will, without you:
- launch a **fresh reviewer process** (the configured CLI: `codex exec` or `claude -p`; new session id, read-only tools, clean detached worktree at the
  exact candidate SHA) and record its raw output, hash and verdict;
- recompute the verdict from the findings (any HIGH/blocking ⇒ REJECT);
- send blocking findings to a **separate implementer process**, refuse protected/out-of-scope changes, demand a
  regression test that fails before and passes after, commit the repair itself;
- re-audit the new SHA with another fresh reviewer, continuing while there is evidence of progress (see the
  continuation policy below);
- run the gates on the candidate and the baseline and compare failures by test id and cause;
- integrate only per policy and only with a recorded stage-11 authorisation; write `receipt.json` + `RECEIPT.md`.

Each stop also writes the visual report (see below). Exit codes: 0 COMPLETE/VERIFIED, 3 BLOCKED, 4 NOT_VERIFIED, 5 WAITING_FOR_MODEL (reviewer unavailable — never an
ACCEPT). Re-running `run` resumes from `state.json`; it cannot skip a stage (evidence is bound to SHAs).
For user-facing work set `integration.mode: "none"` in the code-commit run and in every `-u<n>` revision: the
driver then stops VERIFIED (exit 0, integration `NOT_INTEGRATED_BY_POLICY`), which is the entry point for Stage 8;
driver VERIFIED is a source-code result, not phase qualification. Only the final revision (and `INTERNAL` work) uses
`fast-forward` with `authorized: false`: after VERIFIED it stops BLOCKED `OWNER_AUTHORIZATION` with `blocker.stage:
VERIFIED`, the expected "ready for integration authorisation" state (stage 11 decides whether the standing policy
covers it or the owner must approve).

## Stage 8 — Live UI qualification and UX loop (you, Windows runtime)

Mandatory for `USER_FACING` and `INDIRECT` capabilities, after a driver VERIFIED (or ACCEPT WITH FINDINGS) round on
the code commit. Full rules: reference section 8.

1. Run the real journeys through the actual URI Windows app with the real Core and services (Brain, permissions,
   approval cards and document/automation engines where they apply). Mock UI tests, widget tests, harness-only
   calls and CLI runs support but never replace this. Drive the real app (a scripted run of the built app, or
   computer use) and keep screenshots/recordings and logs.
2. Check function and UX together: functionality and output correctness; discoverability and navigation;
   first-time understanding and contextual onboarding; clear controls and feedback (operation, progress, success,
   failure, approval needed); error handling and recovery; security and permissions (approval cards, refusals);
   performance within the approved resource limits (GPU lease, VRAM); returning-user workflows; integration
   behaviour and consistency with Workspace, Companion, A2UI, navigation, visual design and approval flows.
   Test a first-time user and a returning user.
3. Reproduce each issue (steps, evidence) before you classify it. Classify each issue: `MATERIAL` (a user cannot discover, understand, complete or recover an essential
   journey; or output is wrong) or `MINOR`. Repair material issues with the smallest effective change inside the
   approved scope (no redesign, no feature growth, no frozen path without owner authorisation). Add onboarding
   only where the live evidence shows it helps; it is minimal, contextual, dismissible, can be opened again and is
   not repeated to returning users.
4. Commit the repair, run the regressions, and re-audit it with a fresh driver revision config
   (`<milestone>-u<n>`, new `state_dir`; see "Revision configs"). Then repeat the full live journey. Loop until no
   material issue is left. A `MINOR` item may stay open only if the independent auditor confirms in writing that it
   does not compromise an essential journey. The loop is DISCOVER → REPRODUCE → PRIORITISE → REPAIR → INDEPENDENT
   REVIEW → LIVE RETEST. Prefer small, unobtrusive changes supported by the evidence; no unneeded redesign.
5. Write the qualification record from `docs/dev_workflow/lifecycle/UI_QUALIFICATION_TEMPLATE.json` (JSON is
   authoritative; any Markdown summary or dashboard is generated from it) bound to the exact code commit tested.
   Status: PASS only when every mandatory journey is PASS with COMPLETED_WITH_RESULT live evidence on that commit
   and no MATERIAL issue is open; any failed journey or open MATERIAL issue = FAIL; any mandatory journey not run = NOT VERIFIED or BLOCKED (with what is missing), also when the real Windows
   runtime is unavailable. Never
   report a capability as qualified while a mandatory UI or live check is open.
6. Final independent acceptance (lifecycle stage 10): commit the record (evidence-only commit: only evidence/record paths
   may differ from the tested code commit) and run a final driver revision whose `review_focus` asks the auditor to
   check the record against the code commit, the live evidence and the UX criteria.

Purely `INTERNAL` work skips steps 1–4, uses integration and operational verification, and records why it has no
UI in the plan and the record.

## Verdicts

Driver reviewers emit three labels (ACCEPT, ACCEPT WITH FINDINGS, REJECT). You and outside-driver auditors report
with five: **ACCEPT** (criteria met with verified evidence), **ACCEPT WITH FINDINGS** (no blocking issue;
non-blocking findings documented), **REVISE** (correctable issues; repair and re-review), **REJECT** (material
failure invalidates the candidate), **BLOCKED** (evidence, permission, runtime or independent reviewer missing).
Driver outcomes map by stage and blocker kind:

| Driver outcome | Report as |
|---|---|
| round REJECT routed to repair (FIXING) | REVISE |
| BLOCKED `STALLED` or `RETRY_LIMIT` | REJECT (this candidate) |
| BLOCKED `OWNER_AUTHORIZATION` with `blocker.stage: VERIFIED` | the verdict, ready for stage 11 ("Integration preconditions and authorisation" decides standing policy or owner) |
| any other BLOCKED `OWNER_*` (including `OWNER_DECISION` for a repair refused as protected or out of scope), or a finding with `owner_decision: true` | BLOCKED (needs the owner) |
| BLOCKED `NO_ACTIONABLE_FINDINGS` | BLOCKED; if all the round's commands were BLOCKED, or its `tests_run` and `inspected` are empty, an auditor failure (Auditor selection) |
| any other BLOCKED kind (e.g. `TAMPER`, `CONFIG`, `EVIDENCE`, `RESOURCE`, `BUDGET`, `REVIEWER_EXEC`, `REPAIR_FAILED`, `STEP_LIMIT`), WAITING_FOR_MODEL, NOT_VERIFIED | BLOCKED |
| VERIFIED / COMPLETE on an independent ACCEPT or ACCEPT WITH FINDINGS | that verdict |

An ACCEPT on source
code alone never means the phase is qualified: live UI, security, regression and owner gates must also pass.

## Reporting (you)

- `python -m scripts.dev_workflow.lifecycle status <cfg>` (add `--a2ui` for the Developer Console surface) and
  `verify <cfg>` (hash chain). Report stage, rounds, reviewer session ids, open findings, gates, integration,
  blockers — from the receipt, not from memory.
- Only `stage: VERIFIED/COMPLETE`, or BLOCKED `OWNER_AUTHORIZATION` with `blocker.stage: VERIFIED`, together with
  `evidence_ok_for_candidate: true` supports "independently accepted". Work accepted through the V3.1 fallback
  path is reported as **FALLBACK-ACCEPTED** (the task ledger ACCEPTED on the exact SHA with its fallback basis,
  plus the coordinator's gate results of stage 11), never as driver-counted.
  WAITING_FOR_MODEL, BLOCKED, NOT_VERIFIED or a missing receipt means NOT QUALIFIED; say so.
- BLOCKED `OWNER_AUTHORIZATION` with `blocker.stage: VERIFIED` ⇒ go to stage 11 ("Integration preconditions and
  authorisation"); ask the owner only when the explicit-approval path applies. The driver's wording "needs owner
  authorisation" is fixed driver text; stage 11 decides.
- Any other BLOCKED with `OWNER_*` ⇒ ask the owner the specific question in `blocker.needs`; after their answer,
  record it with `unblock <cfg> --note "<their decision>"` and run again. Never set `authorized: true` or extend
  `authorized_protected_changes` on your own, and never run `unblock` for a CONFIG block yourself (the owner's
  acknowledgement of a policy change is the control).
- A review made by another channel (e.g. a separate cloud session) may be recorded with `import-review`; it can
  route findings to repair but never counts as an ACCEPT.
- Report the auditor used (Codex or Claude, fallback reason), the reviewed SHA, the verdict in the words above and
  the UI qualification status (PASS / FAIL / NOT VERIFIED / BLOCKED). Say which claims the auditor only read
  about and which it ran or observed itself.
- Owner decision D18: every summary to the owner is short and in plain words; detail stays in the linked evidence.
- Report these states separately; each needs its own evidence and none implies another: **IMPLEMENTED** (committed
  on the candidate branch), **TESTED** (targeted tests and driver gates COMPLETED_WITH_RESULT on the SHA), **LIVE
  VERIFIED** (UI qualification record PASS on the code commit), **INDEPENDENTLY ACCEPTED** (driver-counted ACCEPT or
  ACCEPT WITH FINDINGS on the exact SHA, `evidence_ok_for_candidate: true`), **FALLBACK-ACCEPTED** (V3.1 fallback
  path, see Reporting and stage 11), **INTEGRATED** (the canonical branch
  contains the SHA; receipt written and `verify` OK), **FROZEN** (owner freeze decision recorded), **BLOCKED** (with
  the blocker and the smallest owner action).

## Integration preconditions and authorisation (stage 11)

Integrate (or ask the owner) only when all of these hold, and name them in the authorisation record:
the exact accepted commits; a final driver-counted independent ACCEPT/ACCEPT WITH FINDINGS on that SHA (for
fallback-accepted work, the fallback acceptance described below); no open
blocking finding; canonical re-checked for intervening changes (a moved canonical means rebase and re-review); a PASS UI
qualification record for each user-facing capability (or the owner's explicit acceptance of the named
NOT VERIFIED items); frozen-file integrity (`protected_paths` diff); provenance; combined regression gates;
security and approval boundaries checked; the driver receipt (`receipt.json`, `verify` OK) as the reproducible
integration record (for fallback-accepted work, the record described below). Never merge unqualified work
silently. Development-branch acceptance is never authorisation for production deployment.

Authorisation has two paths (owner decision LDEC-016 and its 2026-10-24 clarifications; basis DEC-041);
fallback-accepted work takes the first one:

- **Standing policy (automatic).** When every precondition above holds (all independent reviews, tests, security
  checks and integration gates pass on the exact commit) and no significant owner-level decision is involved, the
  integration proceeds without a fresh owner approval. Record the standing-policy authorisation in the Milestone
  Manager ledger first: an `INTEGRATION` approval for the exact commit, resolved with `owner_words` = the verbatim
  LDEC-016 clarification (for fallback-accepted work also the owner's 2026-10-24 follow-up decision) and `source` =
  "LDEC-016 standing policy (not a per-commit owner approval)", plus the evidence that each precondition holds.
- **Explicit owner approval.** Mandatory for significant security, privacy, permission, architectural or other
  restricted decisions, among them: security exceptions or unresolved security findings; privacy-policy or
  sensitive-data changes; new permissions, credentials, privileges or dependencies; frozen or protected paths
  (`authorized_protected_changes`); production deployment or cutover; any finding marked as an owner decision;
  work the owner has reserved or deferred. Ask the owner, with the preconditions, and record their words.
- **Fallback-accepted work (owner, 2026-10-24).** A commit accepted through the V3.1 fallback path is covered by
  the standing policy on the same terms, provided it passes the same gates. Fallback acceptance means: the driver
  recorded `NO_INDEPENDENT_REVIEWER` on the exact SHA; a fresh isolated fallback review of that SHA returned ACCEPT
  or ACCEPT WITH FINDINGS with no blocking finding, recorded with `task_ledger review`; and `task_ledger accept`
  accepted the task. The driver stops before its gates on this path, so the coordinator supplies the same checks:
  run every gate bound in the run's `PLAN` event (the run config unchanged since: `lifecycle verify` OK, no
  `CONFIG_CHANGED`) on the exact SHA in a fresh detached worktree (fixtures installed where a gate needs them);
  run a failing gate's command on the baseline too and accept only zero new failures by test id (known baseline
  failures named); a gate that executed no tests is not a pass unless the gate carries a written
  `allow_zero_tests` justification (DRV-3); the changed paths baseline..SHA touch no path of the run's resolved
  `protected_paths` outside `authorized_protected_changes`, and `ws_frozen_check` exits 0. Record the results
  with `task_ledger test` and as Milestone Manager evidence. The reproducible record is the stored fallback review output, the gate logs, the
  accepted task and the integration receipt. Restricted decisions still take the explicit owner approval path.

Both paths:

- **Ledger before push.** The independent review, the acceptance and the authorisation are recorded in the
  Milestone Manager ledger before anything is pushed to canonical; the integration record and the receipt follow
  the push.
- **How the integration is performed.** The run stays `authorized: false`. A driver-counted run stops BLOCKED
  `OWNER_AUTHORIZATION` at VERIFIED with the exact push command in `blocker.needs`; the expected tip is the
  driver's recorded `target_tip_before`. A fallback-accepted run stops at `NO_INDEPENDENT_REVIEWER` with no push
  command; the expected tip is the run's baseline `expect`, and the command is `git push
  --force-with-lease=refs/heads/<target>:<expected tip> <canonical remote> <sha>:refs/heads/<target>`. After the
  authorisation is recorded, re-check the canonical tip (`git ls-remote`; it must equal the expected tip,
  otherwise rebase and re-review) and confirm `git merge-base --is-ancestor <expected tip> <sha>`, then push
  with the lease pinned to that tip (a moved target is refused), and verify the remote afterwards. Do not edit
  `authorized` in a running config (that is a policy change: BLOCKED CONFIG, cleared only by the owner).
- **Revert-only rollback.** The integration receipt written by the integrating session names the rollback as
  `git revert --no-edit <base>..<tip>` followed by a reviewed fast-forward; never a force-push or a history
  rewrite.
- A push refused by the session's permission check is not routed around: record a blocker and ask the owner.

## Current application: URI Office (owner directive 2026-10-15)

Priorities: O2 Unified Office Workspace, O3 Word automation, O4 PDF intelligence, O5 PowerPoint automation. O2P
(printing and hardware discovery) is DEFERRED: printing stays off by default; its code and evidence are kept for
later; it does not block other Office qualification. O2 live qualification must cover, through the real UI:
Office navigation; Word, PowerPoint and PDF previews; Save as PDF; Excel workspace continuity; natural-language
tasks; approval cards; document validation; file integrity; error recovery; discoverability; first-time onboarding;
contextual automation suggestions; responsiveness; Brain integration where it applies. Repair material UX issues
and re-run the live tests. Do not freeze O2 while a mandatory live check is open. The Office thread owns this
work; this skill states the rules and does not run Office work.

## Adopting a policy change

A lifecycle change applies to milestones started after it is integrated. Running milestones adopt it through
their own normal process. Do not invalidate existing evidence only because the policy changed: name the mandatory
evidence that is missing and let the owning thread supply it.

## Continuation policy (owner directive 2026-10-11)

There is no fixed round limit. Review → repair → re-audit continues while findings are actionable and progress is
shown, inside every existing safety, resource and permission boundary:
- **Progress** is judged from evidence each round (`PROGRESS` event): earlier blocking findings the reviewer confirms
  FIXED, and blocking findings that are NEW (not a repeat). A round with nothing fixed and nothing new is a stall;
  `continuation.stall_rounds` (default 2) consecutive stalls stop the run (BLOCKED, STALLED).
- **Recurrence**: a finding the reviewer says is NOT_FIXED, or that matches an earlier one's files and title, is a
  REPEAT, not a new defect. From its second occurrence (`diagnose_after`) a separate read-only diagnosis worker
  names the root cause before the next repair, and the repair prompt carries that diagnosis — no blind retries.
  After `limits.max_repair_attempts` (3) repairs of the same defect the run stops (RETRY_LIMIT) with the diagnosis.
- **Budget**: `continuation.budget` (`max_rounds` safety cap, `max_cost_usd`, `max_hours`) stops the run as BLOCKED
  (BUDGET); the owner raises it by a config change (which itself stops until acknowledged).
- **Checkpoints**: quota exhaustion, an unavailable reviewer/implementer/diagnoser or a timeout records a
  `CHECKPOINT` and parks the run in WAITING_FOR_MODEL at the stage it was in (not counted as a failed attempt).
  Schedule a resume (e.g. a one-off check-in) and run `run` again; environmental blockers (GPU lease, missing tool)
  stop as BLOCKED (RESOURCE) and resume after `unblock`.
- Never: weaker gates, suppressed findings, a self-certified ACCEPT, or crossing frozen-file / owner boundaries to
  keep a loop going.

## Visual report after every milestone (owner directive 2026-10-11)

Every time `run` stops — COMPLETE, VERIFIED, BLOCKED, NOT_VERIFIED or WAITING_FOR_MODEL — and when a milestone
closes, give the owner a visual report without being asked:

1. The driver has already written `<state_dir>/REPORT.html` (self-contained page: stage, review rounds chart,
   reviewer log with session ids, findings and their repairs, gates, what needs the owner) and
   `<state_dir>/report_data.json` (the same as rows). `python -m scripts.dev_workflow.lifecycle report <cfg>`
   regenerates them.
2. Where the Artifact tool is available, publish the milestone's dashboard from `report_data.json` (Dashboard
   type; one dashboard per milestone, updated in place on later runs — keep its URL in
   `<state_dir>/dashboard_url.txt`). Otherwise send `REPORT.html` to the owner as a file (SendUserFile or
   equivalent). Never hand-type figures: every number comes from `report_data.json`.
3. In the reply, give the link and three lines: stage, what was achieved this run, and what needs the owner
   (`summary.owner_actions` / `owner` rows). If `summary.evidence_ok` is false, say "not qualified" plainly. For
   user-facing work add a fourth line: the UI qualification status (item 5).
4. A program-level view across milestones (like the W1/A0 + skill dashboard of 2026-10-11) is updated the same way
   when several milestones run together.
5. Structured evidence is authoritative (`events.jsonl`, `round.json`, `receipt.json`, the UI qualification JSON).
   Reports and dashboards are views generated from it and never replace or round up either. The driver report
   reads only driver evidence: its "qualified" wording and `summary.evidence_ok` mean an independent ACCEPT with
   passing gates on the source commit, never LIVE VERIFIED. For `USER_FACING` and `INDIRECT` work show the UI
   qualification status beside it, copied from the record's `status`, `status_reason` and `code_commit` (in the
   dashboard as rows of their own, read from the JSON file; in the reply as its own line). No record means NOT
   VERIFIED. Driver support for reading the record is a later milestone.

## Containment

Workers get tool denials for edits (reviewer), protected paths (implementer) and all git-writing commands; after
every worker the driver kills its process group and re-checks the audit checkout, the implementation worktree, the
milestone's refs and the repository's hooks/config, and discards the run if anything changed. The driver's own git
commands ignore hooks. Receipts are tamper-evident (`verify`), not tamper-proof: commit them. GPU gates run
under `gpu_lease`; no lease ⇒ BLOCKED. Production deployment, service cutover and permission changes are never part
of this skill.
