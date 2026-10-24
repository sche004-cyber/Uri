# URI development lifecycle (skill `uri-development-lifecycle`)

Status: implemented 2026-10-11 as an extension of AO-4 (`scripts/dev_workflow`). Plan and acceptance criteria:
`LIFECYCLE_PLAN_AND_ACCEPTANCE.md`. Qualification record: `LIFECYCLE_QUALIFICATION.md`. Revised 2026-10-15
(DEV-LIFECYCLE-3): Codex-first auditor selection and UI-first live qualification (section 8).

## 1. What it is

| Part | File | Role |
|---|---|---|
| Skill | `.claude/skills/uri-development-lifecycle/SKILL.md` (pointer in `.agents/skills/`) | tells the coordinating Claude session when and how to run it |
| Driver | `scripts/dev_workflow/lifecycle.py` | deterministic state machine, evidence, gates, integration, receipts |
| Workers | `scripts/dev_workflow/lifecycle_providers.py` | separate reviewer / implementer processes (`codex_cli` preferred reviewer since DEV-LIFECYCLE-3 where its sandbox probe passes (on Windows since DEV-LIFECYCLE-3A), `claude_cli` fallback; the template default is `codex_cli`, `command` for tests) |
| UI qualification | `docs/dev_workflow/lifecycle/UI_QUALIFICATION_TEMPLATE.json` | live Windows UI qualification record (section 8) |
| Config | `docs/dev_workflow/lifecycle/<milestone>.json` (template `TEMPLATE.json`) | milestone scope |
| Tests | `tests/dev_workflow/test_lifecycle.py`, fixture worker `tests/dev_workflow/lifecycle_fixture/worker.py` | DEVTEST scenarios |
| Live demo | `scripts/dev_workflow/lifecycle_demo.py` | real separate Claude processes on a DEVTEST fixture |
| Visual report | `scripts/dev_workflow/lifecycle_report.py` | `REPORT.html` + `report_data.json` written with every receipt |

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
                                          VERIFIED --integration policy--> COMPLETE | BLOCKED (integration authorisation)
reviewer missing/failed/not independent -> WAITING_FOR_MODEL -> (next run) READY_TO_RESUME -> AUDITING
BLOCKED --(owner: unblock --note)--> READY_TO_RESUME -> resumes at the blocked stage (a block in VERIFYING/VERIFIED
                                     resumes at AUDITING when the current candidate has no independent ACCEPT)
```

## 3. Guarantees and how they are enforced

(Revised after the independent review DEV-LIFECYCLE-1 R1, which disproved several first-version claims; see
`LIFECYCLE_QUALIFICATION.md` §3.)

| Guarantee | Mechanism |
|---|---|
| Reviewer independence | separate OS process, fresh `--session-id`, prompt built from config + earlier findings only, clean detached worktree at the candidate SHA, edit tools and git-writing commands denied. For a real milestone the executable must be the installed `claude`/`codex` CLI: it is resolved once at PLAN and bound as `reviewer_exec` in the PLAN control state: the absolute path found on PATH, the program that actually runs (`realpath`, SHA-256), its `interpreter` (realpath and SHA-256: a `#!` script's interpreter on POSIX, `node.exe` behind an npm script launcher on Windows), the `launch` argv prefix the driver starts, and on Windows the `.cmd`/`.bat` `launcher` itself (realpath, SHA-256) (DEV-LIFECYCLE-2 W-2). On Windows the driver reads the launcher, never runs it: the program it names on the line that carries `%*` (comment lines ignored) is started directly, never through cmd.exe; a launcher that names several programs, none, a command interpreter (cmd.exe, PowerShell, Windows Script Host) or a `.bat`/`.cmd`/`.ps1` script, or that passes `%*` only elsewhere, is unlaunchable and BLOCKED (REVIEWER_EXEC) (R1-02). It is launched by that bound `launch` prefix, and refused unless it still matches before every step and at launch; any change (a replaced CLI, or another `claude` planted earlier on PATH) is BLOCKED (TAMPER) until the owner unblocks, and several different executables of that name on PATH at the plan are BLOCKED (REVIEWER_EXEC) until the owner leaves one (R6-01; a `binary` override is refused). The reviewer does not load the candidate's CLAUDE.md, `.claude/` settings, hooks, skills, agents or MCP servers (`--safe-mode --setting-sources "" --strict-mcp-config`; codex: `-c project_doc_max_bytes=0`) (R6-02). Nor does it load the user's CLI config, which workers can write because they share the driver's HOME: a `claude` reviewer runs with `CLAUDE_CONFIG_DIR` set to a fresh driver-made directory holding only the credentials file and an allowlist of `~/.claude.json` account keys (no settings, `env`, hooks, plugins or MCP config), a `codex` reviewer with a fresh `CODEX_HOME` holding only `auth.json`; the directory is removed after the run; it is watched for the whole run (not only its end state: R8-01), a settings file or `env`/`apiKeyHelper` seen in it at any moment, even if removed again before the run ends, makes `config_isolated` false, and a real milestone's round counts only with `config_isolated` true. Orphan containment (R8-01, Linux): the driver makes itself the child subreaper, so a worker, gate or test child that calls `setsid()` and leaves the killed process group is re-parented to the driver instead of init; after every worker and every command, and before every worker starts, the driver kills all such adopted processes until none is left (`containment_pre`/`containment_post`, `contained`). A real milestone's round counts only with `contained` true; on Windows (DEV-LIFECYCLE-2) every worker and command runs in its own Job Object through stdlib `ctypes` (`scripts/dev_workflow/containment.py`): created suspended, assigned to the job, then resumed; `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, no breakaway; afterwards the job is terminated and `contained` is true only when it reports `ActiveProcesses == 0`, and every job that went through `finish()`, also one whose termination or check failed, is kept and re-checked before the next worker starts (R1-01); every worker and command that was spawned goes through `finish()`, also when its `communicate()` fails (R2-01), a process that cannot be resumed in its job is killed at spawn, and nothing else is re-checked; a job that cannot be created or assigned gives `contained` false for that run and for every later `precheck` of the driver run (R1-01). Elsewhere (macOS) `contained` is false and a real milestone's review does not count (WAITING_FOR_MODEL with the reason). Not covered on any platform: processes started by other routes (Windows: Task Scheduler, WMI, services, COM out-of-process servers; Linux: systemd-run, cron/at, D-Bus activation, a daemon acting on a worker's request). Claude Code loads the `env` of `~/.claude.json` whatever `--setting-sources` says (probed on 2.1.296), hence the separate directory. The system-wide managed policy directories (`/etc/claude-code`, macOS/Windows equivalents, `/etc/codex`) are bound as `reviewer_policy` in the PLAN control state; a change is TAMPER (R7-01). After the run the driver kills the worker's process group, then checks: audit checkout status and HEAD, implementation worktree status and HEAD, the milestone's refs (candidate branch, baseline ref, integration target), every `refs/replace/*` ref, the repository's hooks, config and `info/` files, and that both worktrees' `.git` still lead to their own git dir. Any change ⇒ the round is NOT_INDEPENDENT. The hooks/config/`info/` digest and the `refs/replace/*` set are bound at PLAN (`control` in the PLAN event) and checked before every step (so before every reviewer, implementer and diagnosis worker), after every review and in the evidence check; any drift from the PLAN state ⇒ BLOCKED (TAMPER, owner), never WAITING_FOR_MODEL. Only `unblock` of that block re-binds it to the then-current state. The read-only diagnosis worker gets the same before/after snapshot (refs, control state, implementation worktree); a change ⇒ BLOCKED (TAMPER). Every driver git command runs with hooks disabled and replace objects ignored (`--no-replace-objects`, `GIT_NO_REPLACE_OBJECTS=1`) and `core.fsmonitor=false`; diffs use `--no-renames`. Other branches are not checked: other sessions move them legitimately |
| No false ACCEPT | VERIFIED needs an independent round with ACCEPT/ACCEPT WITH FINDINGS on the **exact** candidate SHA, passing gates and a clean `verify`; providers other than `claude_cli`/`codex_cli` count only for milestones whose id starts with `DEVTEST`/`TOOLING_TEST`; relayed (`import-review`) and non-independent rounds may route a REJECT to repair but never count as ACCEPT |
| Verdict integrity | effective verdict recomputed from findings (HIGH or unknown severity blocks; MEDIUM blocks unless `blocking: false`; LOW only if `blocking: true`; labels case-normalised). A result whose `findings` (or `prior_findings`) is not a list of objects is unparseable (NO_RESULT ⇒ WAITING_FOR_MODEL), never filtered down to an ACCEPT. The verdict is parsed from the text the worker process returned in memory (its hash is `result_sha256`), never from `reviewer_result.txt`; `verify` re-derives each round's result from the hashed raw stdout and checks `reviewer_result.txt` against `result_sha256`. Raw output, round, repair, qualification and baseline-gate records are hashed into `events.jsonl`; `verify` recomputes the chain and checks every state.json round, repair, gate result, baseline cache and the stage against it: round and repair numbers must be exactly 1..n in order (no duplicates), each recorded round/repair in state.json must equal its hashed `round.json`/`repair.json`, and `resume_to` and `blocker` must equal the values recorded in the last wait/block stage event. The independent ACCEPT used for VERIFIED is read from the hash-bound `REVIEW_RECORDED` events and `round.json` files, never from state.json. `run` calls `verify` first and blocks (TAMPER) on any mismatch; evidence checks call it too. This is tamper-**evident**: whoever can rewrite the whole state directory can rebuild a consistent chain, so commit the receipts to anchor them |
| Repair discipline | the worker never commits; the driver checks HEAD, milestone refs, hooks/config, protected and permitted paths, then commits exactly the checked files with hooks disabled, re-checks the committed file set, and proves regression tests in two fresh worktrees (pre-repair with the new tests copied in, and the repair commit): every test passes after; at least one fails before when a code/security defect is addressed; gate tests named by gate findings must each fail before (a gate test id — junit classname with trailing class components, or a Flutter path relative to the gate's `cwd` — is resolved to its repository file; a gate repair whose named test cannot be resolved to a file with a configured regression runner is refused, not relaxed). A repair that deletes an existing test file is refused; any error after the driver's commit refuses the repair. Any refusal resets the implementation worktree to the pre-repair commit and verifies it is clean — but only after checking that the worktree's `.git` still leads to its own git dir (a redirected gitfile is TAMPER and nothing is reset); the reset moves only the candidate branch: the driver sets `refs/heads/<branch>` to the pre-repair commit, re-points the worktree's HEAD at it (`symbolic-ref`), then runs `reset --hard` + `clean`, and checks HEAD's symref, HEAD and the branch tip. A HEAD redirected to another branch during a repair is TAMPER (and is part of the review integrity snapshot), so no other branch, including the main checkout's, is moved; a hook/config/replace-ref change or a failed reset stops the run (TAMPER) |
| Continuation (no fixed round limit) | continues while findings are actionable and progress is shown: each REJECT round records `PROGRESS` (earlier blocking findings confirmed FIXED, NEW vs REPEAT blocking findings); `stall_rounds` consecutive rounds with nothing fixed and nothing new ⇒ BLOCKED (STALLED); a REPEAT from its `diagnose_after`-th occurrence gets a separate read-only diagnosis worker whose root cause goes into the repair prompt; `max_repair_attempts` (3) repairs of the same defect ⇒ BLOCKED (RETRY_LIMIT, with the diagnosis); `continuation.budget` (rounds cap, cost, hours) ⇒ BLOCKED (BUDGET); quota/unavailable/timeout ⇒ `CHECKPOINT` + WAITING_FOR_MODEL at the current stage, not a failed attempt; driver step limit; every external command has a timeout and its own process group |
| Baseline-aware gates | gates run in a fresh detached worktree at the exact SHA (never in the implementation worktree); pytest via junit, Flutter via `--machine`; a crashed run, a missing report or a failing exit without failures is the failure `<gate>::__run__`; failures compared with the baseline by id and cause; tests that passed on the baseline and disappeared count as failures; `allowed_flaky` globs; baseline results are cached by baseline SHA + command only when COMPLETED_WITH_RESULT (a timed-out, lease-busy or BLOCKED baseline run is retried on the next run, each attempt a `BASELINE_GATE` event); protected-path diff against the baseline; a GPU gate whose lease is not granted (`gpu_lease run` exit 75 with a `refused` report) is BLOCKED (RESOURCE), never a test failure |
| Resume | `state.json` + evidence bound to SHAs and to the event chain; a commit made outside the driver after audit ⇒ BLOCKED (EVIDENCE) and, after `unblock`, re-audit (resume target AUDITING); a forged stage or edited record ⇒ BLOCKED (TAMPER) |
| Policy binding | the config hash and its policy fields (protected/authorised paths, gates, integration, reviewer, implementer, limits, ...) are recorded in the PLAN event. A run whose config hash or resolved-policy hash (the in-effect policy, including the `ws_frozen_check` protected list re-read from the main checkout each run; R4-01) differs from the pair bound in the event chain (never from state.json) records `CONFIG_CHANGED` with the new policy and stops BLOCKED (CONFIG) until the owner runs `unblock --note` with that config and policy; an existing block (e.g. TAMPER) is kept and CONFIG follows it. The config file itself stays agent-writable: the owner's acknowledgement is the control |
| Canonical remote (DEV-LIFECYCLE-2) | the config names `canonical_url`; the driver uses the ONE remote whose URL (after `insteadOf` rewriting) is that repository, never a remote name such as `origin`. No matching remote, several, an integration `remote` that differs, an empty baseline `ls-remote` (`baseline.remote_branch`) or an empty integration-target lookup is BLOCKED, never "no baseline" |
| Integration | re-reads the target tip from the canonical remote, refuses a moved target or a non-fast-forward, `merge` mode re-runs all gates on the merge commit; without `authorized: true` stops BLOCKED `OWNER_AUTHORIZATION` with the exact push command. Runs keep `authorized: false`; after the stage-11 authorisation (standing policy or explicit owner approval) is recorded in the Milestone Manager ledger, the coordinator re-checks the canonical tip and runs that push with a pinned lease (SKILL.md "Integration preconditions and authorisation"). Changing `authorized` in a running config is a policy change (BLOCKED CONFIG, owner `unblock`) |

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

`REPORT.html` (visual milestone report, self-contained) and `report_data.json` (its rows, for a published
dashboard), `<state_dir>/state.json` (machine state), `events.jsonl` (hash chain), `rounds/R<n>/` (prompt, raw stdout/stderr,
parsed result, `round.json` with worker identity and integrity check), `repairs/P<n>/` (prompt, output,
`repair.json`, regression logs), `gates/<sha>/` (logs, junit), `receipt.json`, `RECEIPT.md`.

## 6. Limits (stated, not hidden)

- Containment inside a cloud container runs as root: file permissions do not stop a worker; tool denials plus the
  post-run integrity check do, and the container is the outer boundary. On the owner's PC the same checks apply.
- Tool-deny rules are prefix rules (e.g. `Bash(git commit*)`); a differently spelled command is caught by the
  post-run ref/HEAD/status/hooks check, not prevented.
- A worker child that calls `setsid()` itself leaves the killed process group. On Linux it is still in the driver's
  process tree (child subreaper) and is killed by the sweep after its worker or command, before anything is checked
  and before the next worker starts (R8-01). Not contained: a process started outside the driver's tree (e.g. through
  `systemd-run --user`, `at`/cron or another service) and the workers, commands and orphans of a driver that was itself
  killed (they go to init; a resumed run's sweep does not see them and still records `contained: true`, R10-02). A
  timed-out worker or command no longer blocks the driver on a pipe held by such a child (R10-01). Such a process can write into `state_dir` and the checkouts (caught by the clean-worktree checks and `verify`,
  ⇒ BLOCKED (TAMPER)), and into a reviewer's config dir (caught by the whole-run watch, which polls every 10 ms: an
  injection shorter than one poll interval that the CLI still reads in that window is not excluded). No
  cgroup/namespace isolation is used. On Windows (DEV-LIFECYCLE-2) containment is a Job Object per worker or command;
  its logic is tested with a fake kernel32 and the `windows_only` real-job unit tests passed on the owner's PC, but
  containment inside a real milestone run on Windows is NOT VERIFIED. On macOS there is no containment and real
  reviews do not count.
- The main checkout (`repo`) and branches other than the milestone's are not part of the integrity check.
- The retry fingerprint relies on the reviewer's `prior_findings` and on file+title similarity; `max_rounds` is the
  hard bound.
- The A2UI status surface is produced and validated; it is not wired into the Developer Console UI.
- `codex_cli` adapter is untested (Codex not installed where this was built). Since DEV-LIFECYCLE-3 it is the
  preferred reviewer. Observed 2026-10-15 on Windows (milestone FCV-R-20261014 R1): it launched through the bound
  `node.exe` + `codex.js` prefix, `contained` and `config_isolated` true, then failed because the requested model
  `gpt-6.1-sol` is refused for a ChatGPT login; a probe with `gpt-6-sol` answered. DEV-LIFECYCLE-3 R1 (2026-10-15,
  `gpt-6-sol`, Windows): the round completed and was independent, but Codex's read-only sandbox rejected every shell
  command ("blocked by policy", also `git rev-parse` and `Get-Content`), so it inspected nothing and returned REJECT
  with no findings (driver: BLOCKED NO_ACTIONABLE_FINDINGS). On Windows a `codex_cli` reviewer is therefore NOT
  usable through the driver until a probe in the driver's reviewer environment (SKILL.md "Auditor selection") and a
  first round both show inspection; a driver change to its sandbox/approval settings may be needed. Use the Claude
  fallback meanwhile.
  Correction (DEV-LIFECYCLE-3A, 2026-10-15): the cause was the reviewer's fresh CODEX_HOME, which has no
  `config.toml` and so no `[windows] sandbox` mode (the owner's own config sets `"unelevated"`). With
  `-c windows.sandbox="unelevated"` a probe with the same model, home and `--sandbox read-only` ran `git rev-parse`
  and a write was denied. The driver now passes that flag on Windows; Codex is usable through the driver there when
  the probe and the first round show inspection.
- Driver repairs could not commit a tracked file under the ignored `.claude/` directory: `git add -A -- <path>`
  refuses ignored paths (observed DEV-LIFECYCLE-3-r2 and -r3, BLOCKED REPAIR_FAILED); the coordinator repaired those
  findings in the candidate worktree and re-audited them in a new revision. Fixed in DEV-LIFECYCLE-3A (DRV-1):
  paths tracked in the pre-worker commit are added with `-f`; a new ignored file is refused (`IGNORED_NEW_FILE`).
- On Windows, worker, gate and git output was decoded with the ANSI code page and a UTF-8 character lost the stream
  (DEV-LIFECYCLE-3-r2..r4). Fixed in DEV-LIFECYCLE-3A (DRV-2): UTF-8 decoding with `errors="replace"`.
- The UI qualification of section 8 is enforced by the skill and the auditor, not by the driver: the driver does not
  read the qualification record, and `REPORT.html` / `report_data.json` do not show it: the coordinator shows the
  record's status beside the driver report (SKILL.md "Visual report" item 5). Integration authorisation is the
  control (SKILL.md "Integration preconditions and authorisation": standing policy for routine eligible work,
  explicit owner approval for restricted decisions; ledger before push; revert-only rollback).

## 7. Repository note

The frozen root `.gitignore` ignores `.claude/`. The skill file was added with `git add -f` (a tracked file inside an
ignored directory); `.gitignore` itself is unchanged. If the owner prefers, the skill can live only under
`.agents/skills/` and be copied into `.claude/skills/` locally.

## 8. UI-first live qualification (owner directive 2026-10-15, DEV-LIFECYCLE-3)

Plan and criteria: `DEV_LIFECYCLE_3_PLAN_AND_ACCEPTANCE.md`. Record template:
`lifecycle/UI_QUALIFICATION_TEMPLATE.json`.

### 8.1 Rule

Every new or changed user-facing capability must be discoverable and must work through the actual URI interface on
the intended Windows runtime: the URI Windows app, URI Core, the Brain where it applies, the real service
interfaces, the real permission and approval mechanisms and the real document or automation engines. Backend
behaviour alone is not enough. Mock UI tests, widget tests and CLI runs are supporting evidence only.

| Class | Qualification |
|---|---|
| `USER_FACING` | live journeys in the real app (8.2) |
| `INDIRECT` (no own UI) | live journeys of the user-facing workflow or consumer that exposes it |
| `INTERNAL` (pure infrastructure) | integration and operational verification; the record says why there is no UI |

### 8.2 What each live journey shows

The feature can be found; the user can navigate to it; its controls are understandable; natural-language
interaction works where it applies; it runs through the real URI services; the output is correct; progress and
status are visible; errors give understandable recovery options; permissions and approvals behave as designed; it stays within the
approved resource limits (GPU lease, VRAM); the output can be inspected; the action can be repeated reliably. Run it once as a first-time user (clean profile / no prior state) and once as a returning user.

Example (a Word automation capability): open URI Office, create or select a document, describe the operation,
review URI's proposed changes, approve, inspect the resulting document, save or export it.

### 8.3 UX investigation (not only "does it work")

- **A Discoverability** — can a first-time user find it; are navigation controls well placed; would a contextual
  suggestion help.
- **B Visibility** — are tools and actions clearly shown; are important controls hidden; does the UI say what each
  tool does.
- **C Usability** — can the task be done without developer commands or implementation knowledge; are workflows
  longer than needed; are common actions quick.
- **D Feedback** — current operation, progress, success, failure, approval needed, recovery options.
- **E Functional gaps** — missing or incomplete function that stops the intended workflow; recommendations come from
  the test evidence.
- **F Consistency** — fits URI Workspace, Companion, A2UI, existing navigation, URI visual design, permissions and
  approval flows; no disconnected interface.

### 8.4 Onboarding

Add guidance only where live evidence shows it improves discovery or task completion — not to fill a checklist.
Options: contextual hints, clear action labels, short workflow explanations, example requests, tooltips, guided
first-use steps, empty-state instructions, recovery guidance, discoverable help, automation suggestions. Guidance is
minimal, contextual, non-intrusive, dismissible where appropriate, can be opened again, and is not repeated to
returning users. Both journeys (first-time, returning) are re-run after an onboarding change.

### 8.5 UX improvement loop

```
LIVE TEST (DISCOVER) -> REPRODUCE -> CLASSIFY (MATERIAL / MINOR) AND PRIORITISE
  -> SMALLEST EFFECTIVE REPAIR (approved scope) -> REGRESSION TESTS
  -> INDEPENDENT REVIEW (driver revision <milestone>-u<n>) -> LIVE RETEST of the reviewed SHA -> ACCEPT or ITERATE
```

A repair found in review or in the live retest goes round the loop again. Material discoverability, usability,
onboarding or functional defects are fixed before qualification. A minor item
may be deferred only when the independent auditor confirms it does not compromise an essential journey. No
redesign or feature growth; frozen components only with owner authorisation.

### 8.6 Record and status

The JSON record is authoritative and bound to `code_commit`. Status:

| Status | Meaning |
|---|---|
| PASS | every mandatory journey PASS with COMPLETED_WITH_RESULT live evidence on `code_commit`; no open MATERIAL issue |
| FAIL | a mandatory journey failed, or a MATERIAL issue is open |
| NOT VERIFIED | a mandatory journey was not run (e.g. needs the owner, hardware or a GPU window) |
| BLOCKED | the runtime, permission or independent review needed is unavailable |

The final independent revision reviews the committed record; commits after `code_commit` may touch only evidence
paths. A record that is corrected later keeps the earlier entry in `corrections`.

### 8.7 Auditor duties for live work

The auditor states separately what it inspected, what it executed, what evidence it only reviewed, what live
behaviour it observed itself and what it could not verify (template `environment_notes`). Reviewing screenshots or
reports is never reported as independent live observation. The reviewer records them as JSON keys `inspected`,
`evidence_reviewed_only` and `live_observed` next to `tests_run` and `unverified` (the driver keeps the whole result
object); the qualification record mirrors them under `independent_audit`.
