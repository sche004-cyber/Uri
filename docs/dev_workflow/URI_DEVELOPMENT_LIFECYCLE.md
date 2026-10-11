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
BLOCKED --(owner: unblock --note)--> READY_TO_RESUME -> resumes at the blocked stage (a block in VERIFYING/VERIFIED
                                     resumes at AUDITING when the current candidate has no independent ACCEPT)
```

## 3. Guarantees and how they are enforced

(Revised after the independent review DEV-LIFECYCLE-1 R1, which disproved several first-version claims; see
`LIFECYCLE_QUALIFICATION.md` §3.)

| Guarantee | Mechanism |
|---|---|
| Reviewer independence | separate OS process, fresh `--session-id`, prompt built from config + earlier findings only, clean detached worktree at the candidate SHA, edit tools and git-writing commands denied. For a real milestone the executable must be the installed `claude`/`codex` CLI (path and SHA-256 recorded; a `binary` override is refused). After the run the driver kills the worker's process group, then checks: audit checkout status and HEAD, implementation worktree status and HEAD, the milestone's refs (candidate branch, baseline ref, integration target), every `refs/replace/*` ref, the repository's hooks, config and `info/` files, and that both worktrees' `.git` still lead to their own git dir. Any change ⇒ the round is NOT_INDEPENDENT. Every driver git command runs with hooks disabled and replace objects ignored (`--no-replace-objects`, `GIT_NO_REPLACE_OBJECTS=1`); diffs use `--no-renames`. Other branches are not checked: other sessions move them legitimately |
| No false ACCEPT | VERIFIED needs an independent round with ACCEPT/ACCEPT WITH FINDINGS on the **exact** candidate SHA, passing gates and a clean `verify`; providers other than `claude_cli`/`codex_cli` count only for milestones whose id starts with `DEVTEST`/`TOOLING_TEST`; relayed (`import-review`) and non-independent rounds may route a REJECT to repair but never count as ACCEPT |
| Verdict integrity | effective verdict recomputed from findings (HIGH or unknown severity blocks; MEDIUM blocks unless `blocking: false`; LOW only if `blocking: true`; labels case-normalised). Raw output, round, repair, qualification and baseline-gate records are hashed into `events.jsonl`; `verify` recomputes the chain and checks every state.json round, repair, gate result, baseline cache and the stage against it: round and repair numbers must be exactly 1..n in order (no duplicates), each recorded round/repair in state.json must equal its hashed `round.json`/`repair.json`, and `resume_to` and `blocker` must equal the values recorded in the last wait/block stage event. The independent ACCEPT used for VERIFIED is read from the hash-bound `REVIEW_RECORDED` events and `round.json` files, never from state.json. `run` calls `verify` first and blocks (TAMPER) on any mismatch; evidence checks call it too. This is tamper-**evident**: whoever can rewrite the whole state directory can rebuild a consistent chain, so commit the receipts to anchor them |
| Repair discipline | the worker never commits; the driver checks HEAD, milestone refs, hooks/config, protected and permitted paths, then commits exactly the checked files with hooks disabled, re-checks the committed file set, and proves regression tests in two fresh worktrees (pre-repair with the new tests copied in, and the repair commit): every test passes after; at least one fails before when a code/security defect is addressed; gate tests named by gate findings must each fail before. A repair that deletes an existing test file is refused; any error after the driver's commit refuses the repair. Any refusal resets the implementation worktree to the pre-repair commit and verifies it is clean — but only after checking that the worktree's `.git` still leads to its own git dir (a redirected gitfile is TAMPER and nothing is reset); the reset moves only the candidate branch: the driver sets `refs/heads/<branch>` to the pre-repair commit, re-points the worktree's HEAD at it (`symbolic-ref`), then runs `reset --hard` + `clean`, and checks HEAD's symref, HEAD and the branch tip. A HEAD redirected to another branch during a repair is TAMPER (and is part of the review integrity snapshot), so no other branch, including the main checkout's, is moved; a hook/config/replace-ref change or a failed reset stops the run (TAMPER) |
| Bounded loop | `max_repair_attempts` per defect (reviewer's `prior_findings` NOT_FIXED or same file+title fingerprint), `max_rounds` overall, driver step limit; every external command has a timeout and runs in its own process group, which is killed afterwards |
| Baseline-aware gates | gates run in a fresh detached worktree at the exact SHA (never in the implementation worktree); pytest via junit, Flutter via `--machine`; a crashed run, a missing report or a failing exit without failures is the failure `<gate>::__run__`; failures compared with the baseline by id and cause; tests that passed on the baseline and disappeared count as failures; `allowed_flaky` globs; baseline results are cached by baseline SHA + command only when COMPLETED_WITH_RESULT (a timed-out, lease-busy or BLOCKED baseline run is retried on the next run, each attempt a `BASELINE_GATE` event); protected-path diff against the baseline; a GPU gate whose lease is not granted (`gpu_lease run` exit 75 with a `refused` report) is BLOCKED (RESOURCE), never a test failure |
| Resume | `state.json` + evidence bound to SHAs and to the event chain; a commit made outside the driver after audit ⇒ BLOCKED (EVIDENCE) and, after `unblock`, re-audit (resume target AUDITING); a forged stage or edited record ⇒ BLOCKED (TAMPER) |
| Policy binding | the config hash and its policy fields (protected/authorised paths, gates, integration, reviewer, implementer, limits, ...) are recorded in the PLAN event. A run whose config hash differs from the one bound in the event chain (never from state.json) records `CONFIG_CHANGED` with the new policy and stops BLOCKED (CONFIG) until the owner runs `unblock --note` with that config; an existing block (e.g. TAMPER) is kept and CONFIG follows it. The config file itself stays agent-writable: the owner's acknowledgement is the control |
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
  post-run ref/HEAD/status/hooks check, not prevented.
- A worker child that calls `setsid()` itself leaves the killed process group; its later writes are caught by the
  clean-worktree checks before the next step, not prevented. No cgroup/namespace isolation is used.
- The main checkout (`repo`) and branches other than the milestone's are not part of the integrity check.
- The retry fingerprint relies on the reviewer's `prior_findings` and on file+title similarity; `max_rounds` is the
  hard bound.
- The A2UI status surface is produced and validated; it is not wired into the Developer Console UI.
- `codex_cli` adapter is untested (Codex not installed where this was built).

## 7. Repository note

The frozen root `.gitignore` ignores `.claude/`. The skill file was added with `git add -f` (a tracked file inside an
ignored directory); `.gitignore` itself is unchanged. If the owner prefers, the skill can live only under
`.agents/skills/` and be copied into `.claude/skills/` locally.
