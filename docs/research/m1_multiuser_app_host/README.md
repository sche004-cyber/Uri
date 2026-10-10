# URI Milestone 1 research: three-user server and App Hosting Foundation

Status: **RESEARCH AND PLANNING ONLY.** Nothing here authorizes implementation, a merge, a deployment, a subscription
change or a change to frozen systems. Drafted 2026-10-10 by Claude in a cloud session while the owner's development PC
was offline.

## Contents

| File | What it holds |
|---|---|
| `M1_ARCHITECTURE_AUDIT_AND_PLAN.md` | Deliverables 1-9 and the conclusion: inventory, gap analysis, the recommended three-user architecture, harness terms, app host, threat model, slices, audit procedure, cloud vs PC-blocked work |
| `M1_IMPLEMENTATION_STATUS_LEDGER.md` | Deliverable 10: one row per capability with a status, its evidence and the evidence grade |
| `M1_STORAGE_ACCESS_MANAGER.md` | Extension (assignment item 8): Storage and Access Manager, with its own acceptance criteria and self-review (SS-1..SS-6) |
| `evidence/CLOUD_TEST_EVIDENCE.md` | Commands and results of the tests run in this cloud session |

## Acceptance criteria (set before the audit)

- **AC-1.** The canonical baseline is identified from git and governance records, not assumed, and distinguished from
  experimental, donor and preserved lines.
- **AC-2.** Every component the assignment names has a status taken from code (and from tests where they could run).
  Those components are server, client, Brain, harness, scheduler, A2UI, auth, plugins and permissions. A design
  document is never counted as an implementation.
- **AC-3.** Every positive claim has a file path (and line where practical) or a commit. Every test claim names the run
  and its result. Only `COMPLETED_WITH_RESULT` runs support a positive claim.
- **AC-4.** Provider terms are cited from the provider's own pages where reachable. Anything from secondary sources is
  labelled as such. What is technically possible is kept separate from what is permitted.
- **AC-5.** The recommendation reuses existing capabilities before adding infrastructure. Every new component says why
  no existing one fits.
- **AC-6.** Frozen systems are identified, and every slice says whether it touches them.
- **AC-7.** Every slice has testable acceptance criteria and is marked cloud-testable or PC-blocked.
- **AC-8.** Nothing hardware-dependent, login-dependent or Windows-only is claimed as passed.
- **AC-9.** Every unverified item is named, with its effect on the verdict.
- **AC-10.** Defects found during research are reported, not left for the owner to discover.

## Method

1. **Branches and history.** `git ls-remote` and `fetch` of `github.com/sche004-cyber/Uri` (45 branches) and
   `github.com/sche004-cyber/uri-agent` (5 branches). Branch tips were ordered by commit date. Ancestry was checked
   between the integration branches.
2. **Governance.** Read `docs/governance/` and `docs/governance/consolidation/`, the integration receipts, and the
   working-system status and limitation records.
3. **Component audit.** Four parallel read-only audits covered auth/users/plugins, Brain/GPU/scheduler,
   harness/A2UI/client, and governance/history. Each audit's decisive claims were re-checked against source by the
   author before use. Those checks are listed in the ledger as "re-verified".
4. **Cloud tests.** Ran the cloud-runnable tests on a separate detached checkout of the canonical commit, in a scratch
   virtualenv (Linux, Python 3.13). This is first-hand evidence, recorded in `evidence/CLOUD_TEST_EVIDENCE.md`.
5. **Provider terms.** Fetched Anthropic's pages live. OpenAI and Google pages were unreachable from this sandbox
   (DNS), so search results are used for them and labelled as secondary.

## Self-review record (protocol steps 3-6)

The first draft was checked against AC-1..AC-10. Problems found and repaired before return:

| # | Flaw found in the draft | Repair |
|---|---|---|
| SR-1 | The draft called `integration/git-sync-20261008` "the canonical branch" outright. The formal decision document still says PROPOSED (`URI_CANONICAL_BRANCH_DECISION.md:3`). | Now worded as the *operative* canonical line: the owner authorized fast-forwarding it (`URI_UNIFIED_CONSOLIDATION_PLAN.md:96`), but promotion to `main` is still pending. |
| SR-2 | The draft treated a subagent's finding R8 (approved actions lose the principal) as a defect. | Downgraded to UNVERIFIED hypothesis H-1. A cloud characterization test is planned (S3-T1). |
| SR-3 | The draft said the Google "fewer than 100 users" exemption removes the 7-day token expiry. Google's own page describes the 7-day expiry for *Testing* status and a separate unverified *personal-use* path. | The two are now kept apart. The owner must choose the publishing status (D-5). Wording is marked secondary where the primary page was unreachable. |
| SR-4 | The draft listed the Gemini CLI personal-login retirement as fact. | Marked as secondary-source and unverified. It does not affect the verdict, because no Gemini harness exists. |
| SR-5 | The draft read the test failures under `tests/ws`, `tests/oi` and `tests/phase2a` as possible defects. | Root-cause counts show they are dominated by `ModuleNotFoundError: msvcrt` and `WINDOWS_REQUIRED`. They are now classified as platform-blocked, not passed, failed or defective. The few failures not individually root-caused are disclosed as such. |
| SR-6 | The draft proposed a reverse proxy and did not account for the existing loopback-only consent check. | Added threat T-6: a same-host proxy makes every caller look loopback. The gateway now blocks those routes for remote callers itself (S1 AC-4). |
| SR-7 | The draft did not account for `uri_core/` being a frozen prefix. | Every slice is now labelled FROZEN-TOUCH or NON-FROZEN. The plan is reordered so the safety boundary needs no frozen change. |

## Isolation receipt

- **Pre-write check** (verified before any file was written):
  - branch `research/m1-multiuser-app-host`
  - worktree `/home/user/uri-m1-multiuser-research` (a genuine `git worktree` of the session clone of
    `github.com/sche004-cyber/Uri`)
  - base `54ad7be72847675ae662e2fd4f3b3b9d253e6d4e`
  - working tree clean (0 entries in `git status --porcelain`)
- The research branch did not previously exist, locally or on the remote.
- All tests ran in a separate detached checkout (`/home/user/scratch-ti`, same commit), not in this worktree.
- The commit SHA and push status are reported in the session hand-back. They are not written here, because this file is
  inside that commit.
