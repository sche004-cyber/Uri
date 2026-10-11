---
name: uri-development-lifecycle
description: Default process for URI DEVELOPMENT milestones in this repository - new features, development milestones, significant bug fixes, security repairs, runtime changes, UI changes and multi-component integrations. Drives Plan -> Implement -> Test -> Independent Audit (separate Claude process) -> Repair -> Re-audit -> Qualify -> Integrate -> Receipt automatically, so the owner never has to ask for an audit or relay findings. Invoke as `/uri-development-lifecycle <milestone-id>`. Do NOT use for URI user conversations, office tasks or anything the URI Brain does at runtime.
---

# uri-development-lifecycle

The deterministic engine is `scripts/dev_workflow/lifecycle.py` (an extension of AO-4 `scripts/dev_workflow`).
You — the coordinator — plan, configure, start it and report. You never review your own work and you never
transcribe a verdict into ACCEPT. Reference: `docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md`.

## When it applies

- Applies by default to: features, milestones, significant bug fixes, security repairs, runtime/UI changes,
  multi-component integrations.
- Lightweight path (no driver run): documentation-only changes with no code, test, config or governance-rule
  change. Still verify links and facts you assert, and say that the light path was used.
- Never: user conversations, office tasks, URI runtime skills (this skill is not in
  `uri_workspace/skill_registry.json` and must not be added there).

## Stage 1 — Plan (you)

1. Verify the canonical baseline yourself (`git ls-remote origin integration/git-sync-20261008`); do not trust
   earlier documents.
2. Write the plan with acceptance criteria FIRST (CLAUDE.md Verification-First standard), e.g.
   `docs/<area>/00_PLAN_AND_ACCEPTANCE_CRITERIA.md`.
3. List owner-only decisions now (frozen-path changes, new dependencies, credentials, production, push rights).
   Do not start work that needs one; record it as a blocker.
4. Create the milestone config from `docs/dev_workflow/lifecycle/TEMPLATE.json` → `docs/dev_workflow/lifecycle/<milestone>.json`:
   baseline ref, candidate branch + worktree (outside the main checkout), criteria file, `review_focus`,
   `protected_paths` (`"ws_frozen_check"` = the frozen list), `permitted_paths`, gates, reviewer/implementer
   providers, limits, integration policy (`authorized: false` unless the owner granted it for this target).
   Put `state_dir` OUTSIDE the candidate worktree.

## Stage 2 — Implement

Implement in the candidate worktree only (or give the task to a `claude_cli` implementer). Commit there. Run the
targeted tests. Never edit the canonical checkout, protected paths, or other sessions' worktrees.

## Stages 3–7 — hand over to the driver (automatic)

```
python -m scripts.dev_workflow.lifecycle run docs/dev_workflow/lifecycle/<milestone>.json
```

Run it in the background; it can take hours. It will, without you:
- launch a **fresh reviewer process** (`claude -p`, new session id, read-only tools, clean detached worktree at the
  exact candidate SHA) and record its raw output, hash and verdict;
- recompute the verdict from the findings (any HIGH/blocking ⇒ REJECT);
- send blocking findings to a **separate implementer process**, refuse protected/out-of-scope changes, demand a
  regression test that fails before and passes after, commit the repair itself;
- re-audit the new SHA with another fresh reviewer; stop after `max_repair_attempts` on the same defect or
  `max_rounds`;
- run the gates on the candidate and the baseline and compare failures by test id and cause;
- integrate only per policy and only with owner authorisation; write `receipt.json` + `RECEIPT.md`.

Each stop also writes the visual report (see below). Exit codes: 0 COMPLETE/VERIFIED, 3 BLOCKED, 4 NOT_VERIFIED, 5 WAITING_FOR_MODEL (reviewer unavailable — never an
ACCEPT). Re-running `run` resumes from `state.json`; it cannot skip a stage (evidence is bound to SHAs).

## Reporting (you)

- `python -m scripts.dev_workflow.lifecycle status <cfg>` (add `--a2ui` for the Developer Console surface) and
  `verify <cfg>` (hash chain). Report stage, rounds, reviewer session ids, open findings, gates, integration,
  blockers — from the receipt, not from memory.
- Only `stage: VERIFIED/COMPLETE` with `evidence_ok_for_candidate: true` supports "independently accepted".
  WAITING_FOR_MODEL, BLOCKED, NOT_VERIFIED or a missing receipt means NOT QUALIFIED; say so.
- BLOCKED with `OWNER_*` ⇒ ask the owner the specific question in `blocker.needs`; after their answer, record it
  with `unblock <cfg> --note "<their decision>"` and run again. Never set `authorized: true` or extend
  `authorized_protected_changes` on your own.
- A review made by another channel (e.g. a separate cloud session) may be recorded with `import-review`; it can
  route findings to repair but never counts as an ACCEPT.

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
   (`summary.owner_actions` / `owner` rows). If `summary.evidence_ok` is false, say "not qualified" plainly.
4. A program-level view across milestones (like the W1/A0 + skill dashboard of 2026-10-11) is updated the same way
   when several milestones run together.

## Containment

Workers get tool denials for edits (reviewer), protected paths (implementer) and all git-writing commands; after
every worker the driver kills its process group and re-checks the audit checkout, the implementation worktree, the
milestone's refs and the repository's hooks/config, and discards the run if anything changed. The driver's own git
commands ignore hooks. Receipts are tamper-evident (`verify`), not tamper-proof: commit them. GPU gates run
under `gpu_lease`; no lease ⇒ BLOCKED. Production deployment, service cutover and permission changes are never part
of this skill.
