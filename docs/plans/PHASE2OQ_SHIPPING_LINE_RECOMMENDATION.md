# Shipping-line recommendation (Phase 2 operational qualification, item 7)

Date 2026-10-08. Author: Claude (recommendation, not an independent review). **Nothing was merged, rebased, pushed or
cut over.** The decision is the owner's (C7 readiness P2-6). Coordinated with the git synchronization audit
`_V1\docs\governance\git_sync_20261008\GIT_SYNC_AUDIT.md` (sections 4-9, 13), whose facts are reused, not repeated.

## 1. Acceptance criteria (set before the analysis)

1. Use the owner's seven criteria: architectural compatibility, Frozen-Core integrity, feature completeness, test
   evidence, provenance, security boundaries, integration complexity. Commit count is not a criterion.
2. Every fact is from git, the checkpoint zips or an accepted verdict document, read on 2026-10-08.
3. State what each line lacks, not only what it has.
4. Give one recommendation, the steps it implies, and what it depends on in the git-sync work.

## 2. The lines (facts)

| Line | Identity | Relation to `e8e3b65` | Content |
|---|---|---|---|
| Core lineage | `e8e3b65` + Phase 1 frozen checkpoint `31a34dcb…` + Runtime v1 + Phase 2 (r6 `9a0be52c…`, closure `-f` `fcd0d72e…`) + this operational-qualification candidate (uncommitted); committed byte-exact on `integration/git-sync-20261008` (pushed by owner authorization, head after `f91236d`) except this slice | base | the frozen paired Core (client/server, intent discovery, approval, journal), supervisor, bridge, qualification, supervised UI |
| `_V1` | branch `codex/antigravity-harness-recon` at `62d564c` (2026-09-28) + 248 uncommitted paths | 62 commits after `e8e3b65`, NOT an ancestor of `eb73693` | M35 URI v1 research (`uri_v1/`, 94 files), RAR/edge routing additions (9 `uri_core` files, additive), clarification card UI; uncommitted desktop harness, voice, camera, Gemma work (provisional, "awaiting user test") |
| Desktop mainline | `eb73693` (2026-10-03, on GitHub `uri-repo`) | 160 commits after `e8e3b65` | M36-M38 (CLOSED_FROZEN at `bd7c450`), M37-L4, M39 R0, INT-ARN-1 slices A-D; 656 files changed, 31 under `uri_core`, including `server.py` and `capabilities/registry.py` |

Measured on `_V1`'s working tree against the frozen Phase 1 checkpoint: **0 of the 124 checkpoint files are identical**;
113 are absent (the whole paired Core: `uri_core/client_runtime/*`, worker/server profiles, C1-C5 modules, the frozen UI
runtime files) and 11 differ (`server.py`, `dispatcher.py`, `turn_state.py`, `route_classification.py`,
`capabilities/registry.py`, `settings_shell.dart`, governance files). The git-sync audit (C-4) also records that the
`eb73693` tracker declares `62d564c` superseded.

## 3. Assessment against the owner's criteria

| Criterion | Core lineage | `_V1` | Desktop mainline `eb73693` |
|---|---|---|---|
| Architectural compatibility | is the architecture Phase 0 chose (`e8e3b65` anchor; desktop lines as donors) | pre-Core architecture; Phase 1/2 would have to be re-applied onto it | pre-Core architecture; conflicts with Phase 1 on `server.py`, `registry.py` |
| Frozen-Core integrity | checkpoint byte-identical (frozen-core test 8/8) | Core absent (0/124 identical) | Core absent; would need re-application |
| Feature completeness | paired runtime, supervision, approval, cancel, recovery, receipts, handoff; lacks voice, camera, desktop harness UI, M36-M39 desktop features | voice, camera, harness desktop UI (provisional), clarification card | M36-M39 desktop features, INT-ARN-1 clarification rounds |
| Test evidence | Phase 1 freeze accepted; Phase 2 ops accepted (round 7), closure accepted (round 6); full chains recorded | provisional: its own reports mark voice/camera "awaiting user test" or BLOCKED | per-milestone audits (M36-M38 CLOSED_FROZEN; INT-ARN-1 rounds 1-4, final acceptance not re-verified by the sync) |
| Provenance | checkpoint zips + SHA-256 + Codex verdicts; on GitHub since the authorized push | uncommitted; preserved on `preserve/v1-harness-voice-research-20261004` (subset) | on GitHub |
| Security boundaries | digest-bound approval, signed tickets, client-profile isolation (ISO-1), qualification records, containment | legacy `/ask` authority model; voice sends straight to `/ask` | legacy `/ask` authority model |
| Integration complexity | additive ports of donor features into named slices | rebase of ~250 paths onto a different architecture | merge would conflict heavily (sync audit C-1) |

## 4. Recommendation

**Ship from the Core lineage.** Concretely: the shipping baseline is `integration/git-sync-20261008` plus the Phase 2
operational-qualification candidate once it is independently accepted (added the same way the sync added A7-A9:
exact candidate bytes, verified, new commit, push only with the owner's yes). Treat `_V1` and `eb73693` as DONORS:
port their features into the Core lineage as governed slices with recorded provenance, never by `git merge`.

Why not `_V1` despite its 62 commits: it carries none of the frozen Core, none of Phase 2, and its newest work is
provisional and unaccepted; choosing it would discard the only independently accepted runtime and re-open every
security boundary Phase 1/2 closed.

## 5. Donor ports, in order (each a separate slice with its own acceptance)

1. Clarification card UI (`_V1`, approved design record `clarification_card_2026-09-27`; the supervised screen's
   clarification card follows the same contract).
2. Voice (`_V1`) under the voice parity rules of `PHASE2OQ_UI_VOICE_ACCEPTANCE_PLAN.md` section 3.
3. Desktop harness UI (`_V1`, provisional) only after PA-8..PA-10, onto the supervised executor rows.
4. M36-M39 / INT-ARN-1 desktop features (`eb73693`), re-reviewed against the frozen Core's intent discovery.
5. Camera (`_V1`) after its own BLOCKED prerequisites (RTSP, disk budget) are resolved.

## 6. Dependencies on the git-synchronization work

1. The sync's integration branch already holds Phase 1, Runtime v1 and Phase 2 through the closure (`-f`). The
   operational-qualification slice (this work, after 2026-10-08 08:31 IST) is NOT on it; after independent acceptance
   it needs an A11-style commit with exact candidate bytes, read-back verification, and a push authorized by the owner.
2. The governance files diverge four ways (sync audit C-2); a reconciled tracker is an edit on the chosen line, after
   this decision.
3. Disputed commits `69ef0e4`, `98abdd0`, `869fae5` stay local by owner ruling; nothing here depends on them.
4. No merge into `master` and no new `uri-repo/master` is proposed until the owner chooses (sync audit section 9, step 6).

## 7. Owner decision requested

Choose the shipping line (recommended: Core lineage) and authorize, separately, (a) the A11 commit and push of the
accepted operational-qualification candidate, and (b) the first donor slice.
