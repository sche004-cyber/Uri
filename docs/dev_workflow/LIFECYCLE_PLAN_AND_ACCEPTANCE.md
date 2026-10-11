# uri-development-lifecycle — plan and acceptance criteria

Date: 2026-10-11. Author: Claude (coordinator session). Written before implementation. Owner directive of
2026-10-11 ("URI — Implement Automated Development & Independent Audit Skill") is the scope.

## 1. Baseline and inspection (verified)

| Item | Finding | Evidence |
|---|---|---|
| Canonical | `integration/git-sync-20261008` = `ffdf534` | `git ls-remote origin` |
| Existing dev skill | root `SKILL.md` `uri-development` (Explore → Plan → Freeze → Implement → Review → Repair → Validate → Close): process prose only, no automation | file |
| Agent skill dirs | `.agents/skills/{graphify,uri-ux-design}`; no `.claude/skills/` | `ls` |
| Existing orchestration | AO-4 `scripts/dev_workflow/` (state machine with 17 states + `VALID_TRANSITIONS`, DEVTEST namespace, file authority, Gemma/Antigravity/Codex drivers, 90 tests). `claude_verifier.py` deliberately never spawns a Claude session | source; `pytest tests/dev_workflow` 90 passed |
| Runtime skill registry | `uri_workspace/skill_registry.json` is the Brain's runtime registry (office skills) | file; `uri_core/core/capability_registry.py:18` |
| Frozen boundary | `scripts/ws_frozen_check.py` `PROTECTED` prefixes | source |
| GPU | `python -m uri_operational_intelligence.gpu_lease run --purpose … -- <cmd>` | source |
| A2UI | `uri_a2ui.surface.Surface` validates catalog, actions, no URLs | source |
| Integration policy | canonical moves only by fast-forward of `integration/git-sync-20261008` after an independent whole-range ACCEPT, with a receipt (`docs/integration/final_20261010/INTEGRATION_RECEIPT.md`, `CUTOVER_PLAN.md` §1) | docs |
| Separate Claude processes | `claude` CLI 2.1.296 present; a nested `claude -p` ran as its own process with its own session id and denied tools | probe 2026-10-11 |

## 2. Decisions

1. **Extend AO-4, don't replace it.** New modules `scripts/dev_workflow/lifecycle.py` (deterministic driver) and
   `lifecycle_providers.py` (separate-process workers). Stage vocabulary and legal transitions are AO-4's
   `WorkflowState` / `VALID_TRANSITIONS`. DEVTEST identifiers come from AO-4 `is_devtest_identifier`. AO-4's actor
   table (Gemma/Antigravity roles) and `claude_verifier` are left untouched.
2. **Skill** `.claude/skills/uri-development-lifecycle/SKILL.md` (Claude Code native skill, invoked
   `/uri-development-lifecycle <milestone>`), plus a pointer in `.agents/skills/` for other agents. It is a
   development skill only and is **not** added to the runtime registry `uri_workspace/skill_registry.json`, so it can
   never run in user conversations or office tasks.
3. **Independence by construction.** The reviewer is a separate `claude -p` (or `codex exec`) OS process with a fresh
   session id, launched by the driver in a fresh detached worktree at the exact candidate commit, with edit tools
   denied and git commit/push denied. Its prompt is built only from the config (criteria, scope, focus) and earlier
   findings — never from implementer transcripts. After the run, the driver verifies the audit checkout is unchanged
   and all refs are unchanged; otherwise the review is INVALID. Raw output is stored with its SHA-256 in a hash-chained
   event log, so a later rewrite of a verdict is detectable (`verify`).
4. **Deterministic verdict.** The driver recomputes the effective verdict from the findings: any HIGH or blocking
   finding ⇒ REJECT, whatever label the reviewer used. Candidate SHA in the output must match the pinned SHA.
5. **Repairs** are made by a separate implementer process in the implementation worktree. The driver (not the
   worker) commits, after refusing any change to protected or out-of-scope paths, and after proving every new or
   changed regression test fails on the pre-repair commit and passes on the repair commit.
6. **Gates** compare failures with the baseline by test identity (pytest junit, `flutter test --machine`) and by cause
   (exception type); a failure present on both but with a different cause counts as new.
7. **Integration** follows the configured policy (`none`, `fast-forward`, `merge`) and requires a recorded owner
   authorisation flag for the target; without it the run stops BLOCKED with the exact command. Production deployment
   is outside the skill.
8. **Codex optional.** `codex_cli` is a provider if installed; nothing requires it.

## 3. Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| L-AC1 | Stages follow AO-4 `VALID_TRANSITIONS`; illegal transitions raise | unit |
| L-AC2 | A real milestone can reach VERIFIED only with an independent reviewer verdict (provider `claude_cli`/`codex_cli`, separate process, session id ≠ coordinator/implementer, integrity check passed) on the exact candidate SHA; scripted reviewers count only for DEVTEST milestones | unit |
| L-AC3 | Missing/failed/unparseable reviewer ⇒ WAITING_FOR_MODEL or NOT_VERIFIED, never VERIFIED (no false ACCEPT) | unit + live |
| L-AC4 | Effective verdict recomputed from findings; a REJECT-worthy result labelled ACCEPT is treated as REJECT | unit |
| L-AC5 | Findings are passed to a separate implementer process automatically; repair committed by the driver | unit + live |
| L-AC6 | A repair touching a protected or out-of-scope path is refused and not committed | unit |
| L-AC7 | A repair must add/change a regression test that fails before and passes after | unit + live |
| L-AC8 | Re-audit happens on the new SHA by a fresh reviewer process; earlier audits never apply to a different SHA | unit + live |
| L-AC9 | Same blocking finding after `max_repair_attempts` (default 3) ⇒ BLOCKED (RETRY_LIMIT); `max_rounds` bounds the loop | unit |
| L-AC10 | Gate failure set compared with baseline by identity and cause; a new failure blocks VERIFIED and integration | unit |
| L-AC11 | Protected-path change without authorisation blocks qualification and integration | unit |
| L-AC12 | Owner-only conditions (finding marked owner decision, integration without authorisation) stop BLOCKED with a stated reason | unit + live |
| L-AC13 | Integration re-validates target tip and candidate provenance, performs the configured policy, runs combined gates (merge mode), records the resulting commit and writes receipt JSON + Markdown | unit (local bare remote) |
| L-AC14 | Interrupted run resumes from state; a branch moved outside the driver or a tampered stage cannot skip audit/gates | unit |
| L-AC15 | Event log is hash-chained; `verify` detects an edited verdict or raw output | unit |
| L-AC16 | `status` shows stage, commits, reviewer identity, rounds, open findings, gates, integration, blockers; `--a2ui` emits a valid `uri_a2ui` surface (not wired into the UI) | unit |
| L-AC17 | GPU gates run under `gpu_lease run`; lease unavailable ⇒ BLOCKED (RESOURCE) | unit |
| L-AC18 | Live demonstration on a synthetic DEVTEST fixture with real separate `claude` processes: defective candidate rejected, repaired automatically, re-review accepts, receipts preserved | live evidence |
| L-AC19 | AO-4 tests unchanged and passing; no protected path changed | gate |
| L-AC21 | Every receipt also writes a self-contained visual report (`REPORT.html`, no scripts or network, escaped reviewer text) and `report_data.json`; the skill tells the coordinator to present it (published dashboard or file) after every run (owner request 2026-10-11, added after the plan) | unit (`test_every_receipt_writes_a_visual_report`, `test_report_on_a_blocked_milestone_lists_what_needs_the_owner`, `test_report_escapes_reviewer_text`) |
| L-AC20 | The skill itself is reviewed by an independent reviewer process before it is used on W1/A0 | review record |

## 4. Out of scope / not claimed

Wiring the A2UI status surface into the Developer Console UI; running on the owner's Windows PC; Codex runs (not
installed here). Containment note: inside this cloud container the processes run as root, so file-permission
read-only mounts are not effective; containment is tool denial + post-run integrity checks, and the container itself.
