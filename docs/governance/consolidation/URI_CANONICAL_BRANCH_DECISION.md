# URI Canonical Branch Decision — 2026-10-08

Status: **PROPOSED, awaiting owner approval.** Nothing on GitHub has been renamed, deleted, merged, promoted or
re-defaulted. The candidate exists as local branch `canonical/candidate-20261008` in
`C:\Users\cheta\Development\uri-canonical-candidate` (a fresh GitHub clone) on top of the already-pushed
`integration/git-sync-20261008` (`f8de153`).

## 1. Decision

| Question | Decision | Evidence |
|---|---|---|
| Authoritative repository | `github.com/sche004-cyber/Uri` (`uri-repo`). `github.com/sche004-cyber/uri-agent` (`origin`) becomes a historical mirror, untouched | All development since 2026-09-21 and the verified backup live in `Uri`; `uri-agent` has 4 branches and `master` unchanged since 2026-09-20 |
| Canonical development line | The **Core lineage**: `e8e3b65` → Phase 1 frozen Core → Runtime v1 → Phase 2 (2A–2D, ops, closure) → consolidation records. Proposed final name `main` | Phase 0 consolidation plan chose `e8e3b65` as the accepted Core anchor and the desktop lines as *donors*; owner authorized Phase 1 on that anchor; Phase 1 freeze and Phase 2 acceptances were given on these exact bytes |
| Git history | Option A: preserved. No rewrite, no force push, no squash of accepted commits | Accepted commits keep their hashes; tags pin them |
| Other accepted lines | Not merged. Kept as tagged, read-only **donor** lines and reconciled into the Core only through the C5–C7 reconciliation path with recorded provenance | The desktop mainline and the Core changed the same 5 Core files and ~650 others independently since `e8e3b65`; a git merge would silently decide architecture |

## 2. Why not the other candidates

| Candidate | Why rejected as the canonical line |
|---|---|
| `experimental/desktop-recovery-repair` (`eb73693`, desktop mainline) | Holds frozen M36–M38, M39, INT-ARN-1 and most desktop UX, but has no Phase 1 client/server separation, no launcher authority, no supervisor. Phase 0 named it a donor. Its UI is the one the owner currently uses (installed at `uri-m37-m39-integration`) |
| `codex/*` / `_V1` base `62d564c` | Declared superseded by the `eb73693` tracker itself |
| `origin/master` (`e8e3b65`) | Correct anchor, but 18 days stale; it is the *base* of the canonical line, not the line |
| A merge of Core and desktop lines | Blind merge of incompatible histories; prohibited and architecturally unsafe |

## 3. A constraint found during this consolidation

The frozen Phase 1 module `uri_core/core/runtime_identity.py` refuses to provision or validate a server unless
`git rev-parse HEAD` is exactly `e8e3b65` (`SOURCE_CHECKPOINT_MISMATCH`). Phase 2 tests also assert that Phase 2
remains *uncommitted* on that base. Consequences:

- The committed canonical branch is the **source of truth and the recovery path**. It is not itself runnable by the
  frozen launcher.
- The **runtime checkout is materialized** from the branch: detached `HEAD = e8e3b65` plus the accepted files as an
  uncommitted overlay (procedure in `URI_UNIFIED_CONSOLIDATION_PLAN.md` §5, overlay list in the evidence folder).
  This reproduces exactly the layout the freeze and both Phase 2 acceptances were given on.
- Removing this coupling needs a change to a frozen Core file and is an owner decision (TODO item CONS-7).

## 4. Proposed branch structure (after approval)

| Ref | Role | Points to |
|---|---|---|
| `main` (new, default branch) | Canonical development line | `canonical/candidate-20261008` tip |
| `accepted/*` tags | Immutable acceptance anchors | Phase 1 freeze `925ad45`; Runtime v1 `f791d65`; Phase 2 ops `02fa0e1`; Phase 2 closure `b4a5977`; M36–M38 `bd7c450`; dynamic planning `565eae8` |
| `donor/*` tags | Read-only donor lines for C5–C7 | desktop mainline `eb73693`; dictation `f1e13e9` |
| `preserve/*` branches | Snapshots of formerly uncommitted work | 6 branches pushed 2026-10-08 |
| `integration/git-sync-20261008` | Backup record | `f8de153` (ancestor of the candidate) |
| all other branches | Historical; listed in §5. Proposed: keep until the owner approves archive-tag-then-delete for each | unchanged |

## 5. Classification of every GitHub branch

`uri-repo` (`Uri`):

| Branch | Tip | Classification | Reason |
|---|---|---|---|
| integration/git-sync-20261008 | f8de153 | ACTIVE BASE | Ancestor of the canonical candidate |
| preserve/desktop-int-uncommitted-20261003 | a3dab21 | PRESERVED / DONOR-ONLY | Presentation/document/approval work, not accepted |
| preserve/v1-harness-voice-research-20261004 | 6aa9c30 | PRESERVED / DONOR-ONLY | `_V1` harness, voice, plans, M35 research |
| preserve/harness-connections-console-20261003 | f07f7d4 | PRESERVED / DONOR-ONLY | Partial, acceptance blocked |
| preserve/intent-discovery-20261004 | 2a7c2bc | PRESERVED / DONOR-ONLY | Superseded by Phase 1 C5 |
| preserve/m33-3-r-audit-candidate-20260927 | 8cc688e | HISTORICAL | M33.3-R audit edits |
| preserve/batch-candidate-m37-qual-20260928 | 2031931 | HISTORICAL | Superseded line |
| experimental/desktop-recovery-repair | eb73693 | ACCEPTED DONOR LINE (`donor/desktop-mainline-eb73693`) | Contains frozen M36–M38 and later accepted desktop work |
| claude/project-thread-2vamlf | 5bbf738 | HISTORICAL (freeze record, in donor line) | M36–M38 CLOSED_FROZEN record |
| claude/dynamic-planning-slice1-2eemmh | e4dea8c | ACCEPTED DONOR (`accepted/dynamic-planning-slice1-565eae8`) | Frozen slice, never integrated |
| claude/project-thread-wjykgi / q6a7df / s2qcmk / vhp2g6 | 43101f8 / 1cab035 / 4292528 / 14a0427 | HISTORICAL (dynamic-planning reviews and plans) | Superseded by e4dea8c |
| feature/uri-dictation | f1e13e9 | DONOR (`donor/dictation-f1e13e9`) | Feature line, not in Core |
| claude/harness-first-edge | 86de4c0 | EXPERIMENTAL | Harness-first experiment |
| claude/project-thread-gb7z7s | e0950d4 | EXPERIMENTAL / REJECTED | Edge pair NOT QUALIFIED (owner) |
| claude/needle-granite-planning-nqic37, project-thread-ux1rad | 63557a6, 5f56992 | HISTORICAL | Edge specialist planning |
| wip/batch3-codex-partial | 535135d | QUARANTINED | Unreviewed partial work |
| claude/project-thread-wb7tmm | 6fbb752 | HISTORICAL (duplicate) | Alternative of merge `cc0156e` in donor line |
| claude/project-thread-hrkr7o, 2p12g8, 9rlt5x | 3fefb91, 98d8b1b, 5d60ac2 | HISTORICAL (in donor line) | M37/M39 records merged into eb73693 |
| claude/project-thread-1pcwav, luw6mk, w4o4nu, 8llqxx, vb9lne, y79jjk, wqirwi, dfznke, 4xpkdp, uyzemj, h6lbhn, p9ox5q | various | HISTORICAL | M36–M39 repair rounds; content in donor line |
| claude/office-demonstrator-plan-ljsrvb, edge-harness-minimum-0oj7fe (current GitHub default) | bc12aa1, 610c8f8 | HISTORICAL | Plans/audit packages; **default branch should move to `main`** |
| codex/m36-m38-canonical-audit | 62d564c | SUPERSEDED | Declared superseded |
| m35-uri-v1-parallel-architecture | 405db1f | HISTORICAL | M35/M36 early line |

`origin` (`uri-agent`): `master` e8e3b65 (anchor, HISTORICAL MIRROR), `preserve/running-app-2026-10-01` a91e0e4
(PRESERVED: snapshot of the running legacy app), `m35-uri-v1-parallel-architecture` 70e6065 (HISTORICAL),
`claude/m34-capability-discovery-plan-pooksh` d4074f3 (HISTORICAL).

Local-only commits (not pushed, by owner ruling): `69ef0e4` (harness-first; remote deleted), `98abdd0`
(desktop core fixes; frozen-scope), `869fae5`/`71edc17` (snapshot with graphify artifacts). Classified HISTORICAL /
DISPUTED; they remain in the local repository.

## 6. Promotion procedure (owner-gated)

1. Owner reviews this decision, the verification report and the TODO owner-decision list.
2. Push `canonical/candidate-20261008` and the `accepted/*` / `donor/*` tags (new refs only, no force).
3. Create `main` at the candidate tip on `uri-repo`; set it as the default branch in GitHub settings.
4. Fresh-clone `main`, run the materialization and the gate chain again; record SHAs.
5. Only then, per branch and with explicit approval: tag `archive/<name>` and delete HISTORICAL branch heads.
