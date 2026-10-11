# URI development lifecycle (skill `uri-development-lifecycle`)

Status: implemented 2026-10-11 as an extension of AO-4 (`scripts/dev_workflow`). Plan and acceptance criteria:
`LIFECYCLE_PLAN_AND_ACCEPTANCE.md`. Qualification record: `LIFECYCLE_QUALIFICATION.md`.

## 1. What it is

| Part | File | Role |
|---|---|---|
| Skill | `.claude/skills/uri-development-lifecycle/SKILL.md` (pointer in `.agents/skills/`) | tells the coordinating Claude session when and how to run it |
| Driver | `scripts/dev_workflow/lifecycle.py` | deterministic state machine, evidence, gates, integration, receipts |
| Workers | `scripts/dev_workflow/lifecycle_providers.py` | separate reviewer / implementer processes (`claude_cli`, optional `codex_cli`, `command` for tests) |
| Config | `docs/dev_workflow/lifecycle/<milestone>.json` (template `TEMPLATE.json`) | milestone scope |
| Tests | `tests/dev_workflow/test_lifecycle.py`, fixture worker `tests/dev_workflow/lifecycle_fixture/worker.py` | DEVTEST scenarios |
| Live demo | `scripts/dev_workflow/lifecycle_demo.py` | real separate Claude processes on a DEVTEST fixture |

It reuses: AO-4 `WorkflowState` and `VALID_TRANSITIONS` (stages), AO-4 `is_devtest_identifier` (test namespace),
`scripts/ws_frozen_check.py` `PROTECTED` (default protected paths), `uri_operational_intelligence.gpu_lease run`
(GPU gates), `uri_a2ui.Surface` (status surface), `scripts/phase2d_pytest.ini` (test scope). It does not change AO-4.

## 2. Stages (AO-4 state names)

```
ACCEPTED (plan recorded) -> IMPLEMENTING -> AUDITING --REJECT--> FIXING --repair committed--> AUDITING ...
                                              |ACCEPT                       |refused (protected/scope) -> BLOCKED
                                              v
                                          VERIFYING (gates vs baseline) --new failure--> FIXING
                                              | ok + independent ACCEPT on this SHA
                                              v
                                          VERIFIED --integration policy--> COMPLETE | BLOCKED (owner authorisation)
reviewer missing/failed/not independent -> WAITING_FOR_MODEL -> (next run) READY_TO_RESUME -> AUDITING
BLOCKED --(owner: unblock --note)--> READY_TO_RESUME -> resumes at the blocked stage
```

## 3. Guarantees and how they are enforced

| Guarantee | Mechanism |
|---|---|
| Reviewer independence | separate OS process, fresh `--session-id`, prompt built from config + earlier findings only, clean detached worktree at the candidate SHA, edit tools and git-writing commands denied; after the run the checkout status, HEAD and all local refs must be unchanged, else the round is INVALID. Session id must differ from the implementers' and the configured coordinator's |
| No false ACCEPT | VERIFIED needs an independent round with ACCEPT/ACCEPT WITH FINDINGS on the **exact** candidate SHA plus passing gates; providers other than `claude_cli`/`codex_cli` count only for DEVTEST milestones; relayed (`import-review`) rounds never count |
| Verdict integrity | effective verdict recomputed from findings; raw output, round record and repair record hashed into a hash-chained `events.jsonl`; `verify` detects edits |
| Repair discipline | driver commits, not the worker; protected or out-of-scope change ⇒ refused and reverted; each regression test file must fail on the pre-repair commit and pass after; doc-only findings (`category: documentation`) need no test |
| Bounded loop | `max_repair_attempts` per defect (reviewer's `prior_findings` NOT_FIXED or same file+title fingerprint), `max_rounds` overall, driver step limit |
| Baseline-aware gates | pytest via junit, Flutter via `--machine`; failures compared with the baseline by id and by cause (exception type); `allowed_flaky` globs; protected-path diff against the baseline |
| Resume | `state.json` + evidence bound to SHAs; a commit made outside the driver after audit ⇒ BLOCKED (EVIDENCE) and re-audit; a forged stage without evidence ⇒ BLOCKED |
| Integration | re-reads the target tip from the remote, refuses a moved target or a non-fast-forward, `merge` mode re-runs all gates on the merge commit; without `authorized: true` stops with the exact push command |

## 4. Invocation examples

```
/uri-development-lifecycle W1-A0-closure                     # in Claude Code: loads the skill
python -m scripts.dev_workflow.lifecycle run    <cfg.json>   # drive to COMPLETE/VERIFIED or a stop
python -m scripts.dev_workflow.lifecycle status <cfg.json> [--a2ui]
python -m scripts.dev_workflow.lifecycle verify <cfg.json>
python -m scripts.dev_workflow.lifecycle unblock <cfg.json> --note "owner: approved X on 2026-10-11"
python -m scripts.dev_workflow.lifecycle import-review <cfg.json> --file r.txt --provider ccr_session --session-id <id> --source "<where>"
python -m scripts.dev_workflow.lifecycle_demo /tmp/demo    # live DEVTEST demonstration
```

## 5. Outputs

`<state_dir>/state.json` (machine state), `events.jsonl` (hash chain), `rounds/R<n>/` (prompt, raw stdout/stderr,
parsed result, `round.json` with worker identity and integrity check), `repairs/P<n>/` (prompt, output,
`repair.json`, regression logs), `gates/<sha>/` (logs, junit), `receipt.json`, `RECEIPT.md`.

## 6. Limits (stated, not hidden)

- Containment inside a cloud container runs as root: file permissions do not stop a worker; tool denials plus the
  post-run integrity check do, and the container is the outer boundary. On the owner's PC the same checks apply.
- Tool-deny rules are prefix rules (e.g. `Bash(git commit*)`); a differently spelled command is caught by the
  post-run ref/HEAD/status check, not prevented.
- The retry fingerprint relies on the reviewer's `prior_findings` and on file+title similarity; `max_rounds` is the
  hard bound.
- The A2UI status surface is produced and validated; it is not wired into the Developer Console UI.
- `codex_cli` adapter is untested (Codex not installed where this was built).

## 7. Repository note

The frozen root `.gitignore` ignores `.claude/`. The skill file was added with `git add -f` (a tracked file inside an
ignored directory); `.gitignore` itself is unchanged. If the owner prefers, the skill can live only under
`.agents/skills/` and be copied into `.claude/skills/` locally.
