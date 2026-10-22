# Integration receipt — Lifecycle V3.1 and git-control v2 fix (2026-10-22)

Authority: owner "URI — Consolidated Owner Authorization & Execution Directive" (2026-10-22, items 1 and 2;
`decisions.md` DEC-096) and the owner's follow-up instruction to complete the OPEN-19 integrations through the normal
permission-approval mechanism. Both pushes were approved through the session's permission prompt; nothing was
force-pushed and no security control was changed.

## Sequence

| Step | Before | After | Time (UTC) | Verification |
|---|---|---|---|---|
| 1. Lifecycle V3.1 | `2aa0141e4fa5a1b76a369644335350e867cf3309` | `4ef707ba383656ff3d126f50a0ba1be9720ba154` | 2026-10-22T08:15:03Z | `git ls-remote uri-repo refs/heads/integration/git-sync-20261008` and fresh fetch = `4ef707ba` |
| 2. git-control v2 fix (combined candidate) | `4ef707ba` | `38a6d124d52c6f85fcff8834a7467c80ca1df95d` | 2026-10-22T08:15:29Z | `ls-remote` = `38a6d124`; tip re-checked to be `4ef707ba` immediately before the push |

Both were fast-forwards (`git merge-base --is-ancestor` 2aa0141e -> 4ef707ba -> 38a6d124 checked before pushing).

## Lifecycle V3.1 (`4ef707ba`)

| Gate | Evidence |
|---|---|
| Independent review | Lifecycle V3 driver `D:/uri-dev/lifecycle/LIFECYCLE-V3-1-r6`, round R2, `codex_cli` `gpt-6-sol`, ACCEPT, `blocking_ids` [], independent, COMPLETED_WITH_RESULT (primary path) |
| OPEN-17 | owner-directed `unblock` x2 (06:21:39Z EVIDENCE, 06:22:08Z TAMPER re-bind), drift limited to `.git/info/refs` (verified) |
| Qualification on exact commit | driver QUALIFICATION ok: dev_workflow 423 (baseline 316), oi+ws 840 (807), a2ui/assist/ssrf/web 6111 passed / 25 failed on both (baseline-equal, missing Playwright) |
| Driver state | VERIFIED, `evidence_ok_for_candidate: true`, then BLOCKED OWNER_AUTHORIZATION with the push command used here |
| Live | Windows UI live run `D:/uri-dev/uri-v31-live/live/v31-long-p3b/` 10/10 PASS (P3 profile, automation input); Brain-level long conversation PASS (`e474f510`, same context code) |
| Frozen integrity | `ws_frozen_check` clean on `4ef707ba` |

## git-control v2 fix (`38a6d124` = `4ef707ba` + `3def4023`)

| Gate | Evidence |
|---|---|
| Independent review | driver `LIFECYCLE-GITCTL-V2` BLOCKED `NO_INDEPENDENT_REVIEWER` on `3def4023` (fallback basis); fallback subagent FB1 ACCEPT WITH FINDINGS (G1-01..G1-03 LOW) — `evidence/gitctl_v2/FB1_subagent_3def4023.txt` |
| Integration-specific change | `--no-ff` merge onto `4ef707ba`; `lifecycle.py` and the new test byte-identical to `3def4023`; no conflicts |
| Tests on exact commit | `tests/dev_workflow` 428 passed / 5 Linux-gated / 0 failed (`evidence/gitctl_v2/devworkflow_38a6d124.log`) |
| Frozen integrity | `ws_frozen_check` on a clean checkout of canonical `38a6d124`: ok, no unapproved change or drift |

## Post-integration

- Canonical `38a6d124` frozen check ok (checkout `D:/uri-dev/uri-canon-38a6d124`).
- The v2 driver is now canonical; per G1-03, a run touched by a v2 driver must be resumed with a v2 driver copy.
- Rollback: `git revert` of the range as new commits (no force-push); the pre-integration tip is `2aa0141e`.
