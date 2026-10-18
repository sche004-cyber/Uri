# RUNTIME-PROFILES-INTEG — controlled integration and live qualification of Runtime v1 resource profiles

Owner decision 2026-10-17 (after independent audit round 3 ACCEPT on `7c7a7776`, research branch
`research/runtime-vram-r1-20261017`, pushed to `uri-repo`). This plan was written before any integration step.

## Scope

- **Code to integrate:** only the independently accepted files, byte-identical to `7c7a7776`:
  - `uri_operational_intelligence/runtime_profiles.py`
  - `uri_operational_intelligence/runtime_v1.py`
  - `scripts/ws_brain_host.py`
  - `tests/oi/test_runtime_profiles.py`
  - `docs/operational_intelligence/RUNTIME_PROFILES_UI_CONTRACT.md`

  This plan and the lifecycle config are process documents. Research evidence stays on the research branch.
- **Candidate:** branch `milestone/runtime-profiles-integ-20261017`, worktree `D:\uri-dev\uri-runtime-profiles-integ`,
  baseline canonical `integration/git-sync-20261008` = `25048709` (verified with `git ls-remote uri-repo` on
  2026-10-17). Code commit `adeb6d08`.
- **Not in scope:** changing URI's default Brain configuration; touching frozen Runtime v1
  (`model_lab/integration/local_brain.json`, the freeze record, pinned artifacts); deploying or freezing profiles;
  new Assist adapters; enabling Assist vision in the product. Any change beyond the accepted files gets its own
  re-review.

## Capability classification

| Capability | Class | How it is verified |
|---|---|---|
| Derived profile configs, measured requests, lease fit per profile | INTERNAL | unit tests, gates, live Brain host runs |
| Brain host `--profile` (start, restart, stop, contention wait) | INDIRECT (consumer: the URI app's Brain status and turns) | live Windows UI V2 runs with the Brain host started on each profile |
| Thinking / Vision / Context controls | USER_FACING later; there is no UI control yet (UI contract only) | not qualified here; the owner said no default change |
| URI Assist vision on a profile | INDIRECT. Assist's capture adapters (browser channel, UI Automation, screen capture) are not implemented and `vision_qualified` is False in the product worker, so a real-UI Assist vision journey cannot run without new code and owner decisions (Assist checklist items 7-10) | Assist application-path vision test (checklist item 7): `AssistCommands` with `vision_qualified=True` in a test harness only, a synthetic screenshot through a test adapter, against the real Brain on each Vision profile. Plus the real-UI Assist view journey (opens, shows OFF / UNAVAILABLE) |

## Acceptance criteria

- **IC-1 Scope.** The candidate differs from `25048709` only in the files listed above (plus this plan and the
  config). The code files are byte-identical to `7c7a7776` (`git hash-object` check).
- **IC-2 Frozen preserved.** The frozen config diff is empty. `expected_argv(frozen)` is byte-identical. The host
  without `--profile` behaves as before. Gates: `tests/oi`, `tests/ws` and the frozen check pass, with no new failure
  against the baseline.
- **IC-3 Independent review.** A driver-counted independent round accepts the exact candidate SHA (Codex or
  claude_cli). An imported review does not satisfy this (owner decision D1).
- **IC-4 Integration.** Fast-forward only, after IC-1..IC-3, with your explicit authorisation and
  `expected_target_tip`. Receipt written and remote verified.
- **LQ-1 UI V2 on profiles.** On each of P1 64K + GPU vision, P2 64K main only and P3 32K + GPU vision, the real
  URI Windows app (UI V2), driven by the canonical UI V2 driver, completes its first-time and returning-user journeys
  with the Brain started by the production host on that profile. Record each journey PASS / FAIL with
  COMPLETED_WITH_RESULT evidence. Record Brain residency and decode throughout, and whether demotion occurred.
- **LQ-2 Assist.** P1 and P3 (vision profiles): the Assist application-path vision test answers about the synthetic
  screenshot correctly. Record latency and decode before and after. The real-UI Assist view opens and shows its
  states.
- **LQ-3 Sustained operation.** At least 60 minutes per preferred profile (P1, P2) with the URI app open and an
  ordinary browser workload. Periodic decode and residency samples; no unplanned demotion, or demotion recorded with
  its trigger.
- **LQ-4 Startup and recovery.** Cold start, a host restart, a profile switch (P2 -> P1 -> P2) with conversation
  continuity in the app, and VRAM release measured.
- **LQ-5 Accuracy.** Already established on research runs for P2 and 64K + MTP (suites D, DG, P, F, C, H, S, O, R,
  L; V on 64K + vision). This plan does not re-run them unless the integrated code differs.
- **LQ-6 Report.** Results reported to you before any default change is proposed. MTP stays optional, with a
  VRAM warning.

## Owner-only decisions / blockers recorded now

- B-1 Independent driver-counted reviewer: Codex is over its usage limit until 2026-10-22 14:03, and the claude_cli
  login is expired (`claude auth status`: loggedIn false; only you can run `claude login`). Until one is available,
  IC-3 and IC-4 are BLOCKED.
- B-2 Real-UI Assist vision requires new adapters and enabling `vision_qualified` (Assist checklist items 7-10).
  Not done here.
- B-3 GPU time is shared with the UI V2 and Office sessions, which are waiting to run the frozen Brain. Coordinate
  by message and through the lease.

## Auditor selection

Primary `codex_cli` (`gpt-6-sol`), available after 2026-10-22 14:03. If you log in the claude CLI first, a revision
config with `claude_cli` will be used instead. This is chosen before the first driver run.

## Amendment A1 (2026-10-17, after the first live runs and independent review RPI-R1) — correction note

IC-1 above limited the code to the five files accepted in URI-RUNTIME-VRAM-R1. That turned out to be insufficient:
- With only those files, the app could not use a profile Brain. The worker verified against the frozen argv and
  reported FOREIGN_INSTANCE (live run `p1-main`).
- Reviewer finding R1-01 led to CONTEXT-1: a profile switch restarted the worker and lost the in-memory conversation.

The candidate therefore also contains changes **beyond the accepted scope**, reviewed on their own (subagent review
rounds RPI-R1 and later), never presented as covered by the earlier acceptance:
- `fa0a70e6`: `uri_operational_intelligence/runtime_profile_selection.py` (new), the worker reads
  `control/oi/brain_profile.json`, tests.
- `4d782ef1`: `ProfileFollower` (the worker follows the selection without restarting, so the conversation survives
  a switch); the guard pins the frozen superset of artifacts; `brain_health.backend()` names the serving profile;
  tests.

The five accepted files remain byte-identical to `7c7a7776`. IC-1 now reads: the accepted five files, plus the files
of `fa0a70e6` and `4d782ef1`, plus plan, config and evidence documents. Nothing else.

The default Brain stays the frozen Runtime v1. Integration (IC-4) still requires your explicit authorisation.

## Amendment A2 (2026-10-18, after subagent review RPI-R3) — baseline revalidation and LQ-4 deviation

- **Baseline.** Canonical moved from `25048709` to `348677b7`. It was merged into the candidate as `f3d5eb29`
  ("revalidation before integration"). `f3d5eb29` is the code tested live; later commits on this branch change
  only documents: evidence under `docs/operational_intelligence/profiles_live/`, this plan (A2) and the lifecycle
  config (correction after review R4-03). IC-1 and IC-2 are now checked
  against `348677b7`. The file list of A1 stays the same. `07dca2a8` (content-based `ProfileFollower`, reviews
  R2-05 and R2-06) changes only `runtime_profile_selection.py` and its test, which are A1 files. The lifecycle
  config records the new baseline and review focus.
- **Source binding.** Since review R2-02, every live harness records a source binding before it runs
  (`profiles_live/evidence/harness/binding.py`). A run counts as evidence for a commit only when the binding is
  clean and names that commit.
- **LQ-4 deviation (review R3-02).** This plan names the switch P2 -> P1 -> P2. The run used P2 -> P3 -> P2,
  because P1 is unqualified (CRASH-1, DEMOTE-P1) and P3 is the qualified vision profile. Continuity is verified
  at worker level, not through UI clicks. The mapping of cold start, host restart and VRAM release to evidence is
  in the record's `annotations` ("LQ-4 deviation"). A P2 -> P1 -> P2 switch stays open together with P1.
- **LQ-3 (review R3-01).** "At least 60 minutes per preferred profile (P1, P2)": P2 needs a bound soak
  (`soak-p2-e`). P1 stays unqualified. P3 has a bound soak (`soak-p3-e`) because the owner prioritised 32K +
  vision for Assist.

## Amendment A3 (2026-10-18, owner decisions D1-D5: conditional integration approval)

- **Approved for canonical integration (D1):** P2 (64K, main only) and P3 (32K, GPU vision), on the qualified code
  `f3d5eb29`, plus the change below. The default Brain stays the frozen Runtime v1 (D2). Nothing is deployed or
  frozen (D5).
- **D3 guard (code, after qualification):** `runtime_profile_selection.SELECTABLE` limits what the worker follows
  to the frozen combination, P2 and P3. Every other measured combination, P1 included, keeps the frozen config with
  `PROFILE_NOT_QUALIFIED`, and `write()` refuses it. The Brain host's `--profile` still accepts every measured
  combination for research. A worker never verifies against such a host, which it reports as FOREIGN_INSTANCE
  (fails closed).
  - Effect on P2 and P3: none. The same derive path and the same argv are used; only an unqualified choice is now
    refused.
  - Verification: unit tests (every measured unqualified key refused, follower ignores a switch to P1), the
    regression gates, a bound live switch run on the final code, and an independent review.
  - Brain Quick Controls already restricts its host-side reconfigure to its catalog (frozen, P2, P3), so the two
    lists agree.
- **Integration mechanics:** canonical `integration/git-sync-20261008` is still `348677b7`, which the candidate
  contains, so integration is a fast-forward. The push is verified with `git ls-remote`, and a receipt is written.
  Rollback: a revert commit on canonical (non-destructive), or a force reset to `348677b7` with owner
  authorisation; at run time the frozen fallback is the absent selection file.
