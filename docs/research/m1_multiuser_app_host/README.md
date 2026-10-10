# URI Milestone 1 research: multi-user server, storage, Web Intelligence and app hosting

**Status: research and planning only.** Nothing here authorizes implementation, a merge, a deployment, a subscription
change or a change to frozen systems.

This package was prepared on 2026-10-10 by Claude in cloud sessions while the owner's development PC was offline. Start
with `M1_RESEARCH_SUMMARY.md`.

## Contents

| File | Purpose |
|---|---|
| `M1_RESEARCH_SUMMARY.md` | Findings, recommendation, risks, report map |
| `M1_REPOSITORY_CAPABILITY_INVENTORY.md` | Baseline; Planned → Integrated ladder; defects found |
| `M1_THREE_USER_SERVER_ARCHITECTURE.md` | Gateway-first topology, identity propagation, Brain sharing, network |
| `M1_HARNESS_ACCESS_AND_LICENSING.md` | Provider terms; compliant access modes |
| `M1_STORAGE_ACCESS_DESIGN.md` | Storage and Access Manager |
| `M1_WEB_INTELLIGENCE_ARCHITECTURE.md` | `uri_web`, SafeFetcher, source records, scheduled watch |
| `M1_SOCIAL_PLATFORM_RESEARCH.md` | Platform-by-platform access routes and video intelligence |
| `M1_BROWSER_AUTOMATION_AND_SECURITY.md` | Playwright placement and controls; consolidated threat model |
| `M1_REA_EVALUATION.md` | REA verdict |
| `M1_APP_HOSTING_DESIGN.md` | Minimal app host and demo app |
| `M1_IMPLEMENTATION_SLICES.md` | P0-P6 slices with acceptance criteria; old→new ID mapping |
| `M1_OFFLINE_BLOCKERS_AND_STATUS.md` | Cloud-verified items, PC-deferred verification, decisions |
| `evidence/CLOUD_TEST_EVIDENCE.md` | Runs 1-3 (commands and results) |
| `M1_ARCHITECTURE_AUDIT_AND_PLAN.md`, `M1_IMPLEMENTATION_STATUS_LEDGER.md`, `M1_STORAGE_ACCESS_MANAGER.md` | Superseded or moved pointer stubs. Full text is in git history. |

## Acceptance criteria (set before each drafting round)

**Round 1** (`be55d19`):
- **AC-1.** The canonical baseline is identified from git and governance records.
- **AC-2.** Component status comes from code and tests, never from design documents.
- **AC-3.** Positive claims cite a path, line or commit. Only `COMPLETED_WITH_RESULT` runs count.
- **AC-4.** Provider terms are cited, primary vs secondary is labelled, and "possible" is kept apart from "permitted".
- **AC-5.** Reuse comes before new infrastructure.
- **AC-6.** Frozen systems are identified for every slice.
- **AC-7.** Every slice has testable criteria and a cloud or PC label.
- **AC-8.** No hardware, login or Windows claims.
- **AC-9.** Unverified items are named, with their effect on the verdict.
- **AC-10.** Defects are reported proactively.

**Round 2** (`a6ef74f`, storage): SA-1..SA-6, listed in `M1_STORAGE_ACCESS_DESIGN.md` §0.

**Round 3** (this revision):
- **AC-11.** All twelve named deliverables exist, with no duplicated explanations. Each topic has one home, and other
  reports link to it.
- **AC-12.** Every capability is placed on the Planned → Prototyped → Implemented → Tested → Independently accepted →
  Integrated ladder, with evidence.
- **AC-13.** Web, social and browser research uses official or legitimate routes only. Anything that would evade
  access controls is excluded explicitly.
- **AC-14.** Existing browser, search and scraping tools are inspected before any new framework is proposed.
- **AC-15.** The scheduler is reused, not duplicated.
- **AC-16.** Consistency checks run before commit:
  - every referenced report exists;
  - every cited repository path exists at the baseline;
  - slice IDs are consistent across reports.

## Method

- **Git.** `git ls-remote` and `fetch` of both repositories. Remote tips re-checked at the start of round 3: no new
  canonical commits.
- **Code audit.** Four read-only audit subagents in round 1. Every decisive claim was re-verified by the author before
  use. Rounds 2 and 3 were inspected by the author directly: `file_store`, `turn_runner`, `postconditions`,
  `permission_binding`, `web_search`, `fetch_url`, the `yt_dlp` descriptor, `tool_schema`, the scheduler engine and
  architecture, and the voice ASR references.
- **Cloud runs** were made in a separate detached checkout: `evidence/CLOUD_TEST_EVIDENCE.md`.
- **External sources.** Anthropic, GitHub (`morluto/rea` README, `playwright-python`) and Meta pages were fetched
  live. Google, YouTube, OpenAI and Reddit pages could not be resolved from this sandbox (DNS), so their facts are
  secondary search summaries and are marked EXT-S.

## Self-review and correction record

Rounds 1 and 2 (SR-1..SR-7, SS-1..SS-6) are kept in git history: `git show a6ef74f:<path>/README.md` and
`M1_STORAGE_ACCESS_DESIGN.md` §11.

Round 3:

| # | Flaw found in the round-3 draft | Repair |
|---|---|---|
| SR-8 | The first threat model (round 1) left out SSRF. Round 3 found that `fetch_url` has no address checks. | Confirmed by a run (Run 3) rather than assumed. Added as SSRF-1 / T-9. Interim grant revocation; repair is P1-5 T9; SafeFetcher P3-1. |
| SR-9 | The draft proposed server-side authenticated browsing. That conflicts with the owner-authorized ownership principle, and a remote user cannot complete a login there. | Authenticated automation moved to the client device (`M1_BROWSER_AUTOMATION_AND_SECURITY.md` §3). The server keeps public browsing only. |
| SR-10 | The draft listed `skill.yt_dlp` as a YouTube capability. | Corrected. It is pinned to Wikimedia Commons, and widening it to YouTube is advised against on terms grounds. |
| SR-11 | The draft had the scheduler summarise with the Brain directly. That breaks the scheduler's accepted "runs without the Brain" rule (A-AC1). | Collection is now deterministic. The summary is a separate low-priority gateway turn made as the job's user. |
| SR-12 | The draft offered "captions exposed through official embeds" as a transcript route. | Removed: it is unverified and edges toward scraping. Only the user's own videos, user-supplied transcripts or user-uploaded media remain. |
| SR-13 | The slice IDs (S1-S17) clashed with the new P0-P6 priorities. | Unified renumbering, with a mapping table in `M1_IMPLEMENTATION_SLICES.md`. Old files are kept as stubs. |
| SR-14 | The pre-commit consistency check (AC-16) found two wrong repository paths: `model_providers/base.py` (really `uri_core/core/model_providers/base.py`) and `scheduler/engine.py` (really `uri_scheduler/engine.py`). | Both fixed. The re-run found no missing reports and no undefined slice IDs. The remaining unmatched names are proposed files (`uri_apphost/*`, `app.json`) or runtime file names (`token.json`, `auth.json`, `robots.txt`), which is expected. Ten line citations were spot-checked against the source and all matched. |

## Isolation record

- **Repository:** `github.com/sche004-cyber/Uri`.
- **Branch:** `research/m1-multiuser-app-host`.
- **Worktree:** `/home/user/uri-m1-multiuser-research`, a genuine `git worktree`.
- **Base:** `54ad7be72847675ae662e2fd4f3b3b9d253e6d4e`.
- **Verified before each round's writes** (branch, HEAD equal to the remote, clean tree):
  - round 1: base `54ad7be`, clean;
  - round 2: HEAD `be55d19`, clean;
  - round 3: HEAD `a6ef74f`, clean.
- **Tests and probes** ran only in a separate detached checkout of the same base (`/home/user/scratch-ti`). It was left
  clean after every run.
- The commit SHAs for this round are reported in the session hand-back. They are not written here, because this file is
  part of that commit.
