# URI Consolidation Round 2 — Final Audit and Evidence Report (2026-10-08)

Auditor of record: Claude (this session), with independent read-only review by Codex CLI (`gpt-6-sol`, medium
effort) through the local `codex-exec` bridge. Only `COMPLETED_WITH_RESULT` runs are used as evidence.

## 1. Acceptance criteria (set before implementation)

| # | Criterion |
|---|---|
| C1 | Accepted Phase 2 OQ `-g` (`0b49d86d…c4cd`) in the canonical integration line byte-exact, with evidence and records |
| C2 | Frozen Phase 1 files unchanged (`31a34dcb…98cf7`) |
| C3 | No silent merge of competing implementations; every conflict resolved in a labelled commit |
| C4 | Runtime checkout reproducible from Git and identical to the accepted tree |
| C5 | Own regression evidence on the integrated tree, judged by the accepted chain's criteria and pinned baselines |
| C6 | The ~140 tok/s result identified from primary evidence, artifacts verified, reproduced against an unmodified baseline with quality, memory and errors; no new optimization passed off as the original |
| C7 | PC state re-verified, not assumed; nothing deleted, disabled or cut over without the owner |
| C8 | Durable records 1–7 exist and do not overclaim; C7 and `/ask` remain open |
| C9 | Independent review of the round-2 work, or a labelled self-audit if unavailable |
| C10 | Traceable, non-destructive push of accepted work to `integration/git-sync-20261008` only after verification |

## 2. Task checklist

| Task | Status | Evidence |
|---|---|---|
| Verify Phase 1 and OQ zip hashes | DONE | recomputed; both equal |
| Import OQ `-g` byte-exact | DONE | `6dea266` (154/154 manifest hashes), `fcb619a` evidence, `759d0d4` records; tag `accepted/phase2-oq-g-0b49d86d` |
| Resolve ledger conflict with round 1 | DONE | `94ad32e` (byte-exact re-insertion) |
| Rematerialize runtime from Git | DONE | `RUNTIME_OVERLAY_PHASE2OQ_G.txt` (273 paths); runtime candidate and gate checkout byte-equal to the live accepted tree |
| Regression chain on the Git-materialized tree | DONE — ALL_PASS | `docs/evidence/consolidation/chain_cons2/` |
| Runtime v1 artifact hashes | DONE — 5/5 match | `docs/evidence/consolidation/inference_repro_20261008/runtime_hashes.json` |
| Runtime v1 reproduction, MTP vs no-MTP | DONE | `model_lab/evidence/runs/repro20261008_*` |
| PC re-verification (task, listeners, UI binding, Ollama, fake_executor) | DONE | `URI_CLEANUP_AND_QUARANTINE_MANIFEST.md` §1 |
| Authority manifest + checker tests | DONE — 66 passed | manifest updated for OQ `-g` |
| Records 1–7 | DONE | section 5 |
| Independent review | see section 4 | — |
| Push to `integration/git-sync-20261008` + `accepted/*` tags | see section 6 | — |
| Containment, legacy stop, cutover, deletions, `main` rename | NOT DONE — owner (RED) | `URI_OUTSTANDING_AND_PHYSICAL_ACCEPTANCE.md` §3 |
| Runtime v1 ↔ Core wiring | NOT DONE — new milestone, owner | `URI_INFERENCE_OPTIMIZATION_RECOVERY.md` §4 |

## 3. Verified facts

1. Phase 1 zip and OQ `-g` zip hashes match; 121/121 frozen files unchanged at the tip; the OQ zip overlaps the
   freeze in two files, both byte-identical.
2. The live Phase 2 worktree's 273 uncommitted paths equal the canonical tip at `759d0d4`; a Git-materialized
   checkout reproduces them with zero differences.
3. Regression chain 15:30–15:57: Phase 2 486/0/2; authority 134; Phase 1 full 2,676/11/11, same 2,698 outcome IDs,
   pins hold; scope, residue PASS; Flutter 205/2; bridge 10/10; native Codex `SETTLED_VERIFIED`, mid-run cancel PID
   DEAD; native worker refuses `HARNESS_NOT_USABLE` unauthenticated. Identical to accepted chain10. No process left
   behind.
4. "~140 tok/s" = median decode of Runtime v1 (stock llama.cpp b11425 Vulkan + Qwen3.6-35B-A3B IQ3_S + MTP draft
   head). Reproduced today with identical scores on 10 suites and 0 errors: 133.2 tok/s with MTP vs 98.3 without
   (frozen: 141.2 vs 101.0). Not Ollama; the rejected 7-line patch is unrelated.
5. Live PC: legacy `\URIServer` server still serves 127.0.0.1:8000; shared UI preferences still bind to it;
   `fake_executor.py` no longer runs; Ollama app (started 09:42 by its own launcher pattern) idle with no model.

## 4. Independent review history (auditable; no earlier result overwritten)

| Round | Reviewed | Verdict | Findings | Disposition |
|---|---|---|---|---|
| 1 | `b5b331f` | **REJECTED** | A1–A7 PASS (byte-exact import, frozen files, overlay, ledger restore, chain consistency, inference numbers, no overclaim). FAIL: H runbook overlay ref lacked the file; H containment restore lacked `-BackupRoot` and wrong undo order; M manifest EXE-1 stale (+ salvage ledger); M manifest pointed at an uncommitted overlay list; L recovery ref stale | all five confirmed by me and repaired in `aa20afe` |
| 2 | `aa20afe` | **REJECTED** | the five repairs verified; H `-Restore` without `-BackupRoot` remained in the cleanup manifest and plan §7; M documents implied the push/tags already happened and cited this (then missing) file; L a stray carriage-return byte inside a ledger cell (`E:phase2oq_review\round7`), present in the Phase 2 session's own post-acceptance bytes | all confirmed and repaired in the next commit; the CR fix changes one byte of a post-acceptance record and is labelled as such |
| 3 | `093e5fe` | **REJECTED** | H bare `-Restore` in round 1's `URI_PC_CONTAMINATION_AUDIT.md`; M cleanup manifest said candidate and integration tips were equal before the push | confirmed, repaired in `d2c2a78` |
| 4 | `d2c2a78` | **REJECTED** | three publication-tense statements (plan P-1, authority manifest recovery entry, ledger CONS-15) | confirmed, repaired in `7b320be` |
| 5 | `7b320be` | **ROUND 2 ACCEPTED WITH FINDINGS** | M runbook said the Phase 1 zip is in Git at `925ad45` (only its files are) | confirmed, repaired in the commit that adds this row |

## 4a. Review outcome

Codex review round 5: **ROUND 2 ACCEPTED WITH FINDINGS**; the single finding is repaired. A1–A7 (byte-exact
import, frozen files, overlay, ledger restore, chain consistency, inference numbers, no overclaim) passed from
round 1 and nothing they depend on changed afterwards. The repair of the round-5 finding was not re-reviewed by
Codex (documentation wording only); it is self-checked against `git ls-tree` (no zip in Git).

## 5. Records produced or updated (deliverables 1–7)

1. Canonical inventory / source of truth: `URI_SOURCE_OF_TRUTH_MANIFEST.md`, `docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json`
2. Phase 1 + Phase 2 integration: `URI_PHASE1_PHASE2_INTEGRATION_REPORT.md`
3. Inference optimization: `URI_INFERENCE_OPTIMIZATION_RECOVERY.md`
4. Git/PC cleanup and quarantine: `URI_CLEANUP_AND_QUARANTINE_MANIFEST.md` (+ round 1 `URI_PC_CONTAMINATION_AUDIT.md`, `URI_SALVAGE_AND_RETIREMENT_LEDGER.md`)
5. Runtime and rollback: `URI_RUNTIME_BUILD_AND_ROLLBACK_RUNBOOK.md`, plan §5
6. Outstanding + physical acceptance: `URI_OUTSTANDING_AND_PHYSICAL_ACCEPTANCE.md`; ledger CONS-15..18
7. This report

## 6. Publication

**NOT PUBLISHED.** After the round-5 acceptance the session attempted a non-force fast-forward of
`integration/git-sync-20261008` (GitHub tip `f8de153`, an ancestor of the candidate; branch not protected) plus the
seven `accepted/*` tags. The session's permission layer denied the push, so nothing on GitHub changed. The
accepted work therefore exists in Git only locally, in `C:\Users\cheta\Development\uri-canonical-candidate`
(branch `canonical/candidate-20261008`), and GitHub recoverability (CONS-15) stays PENDING.

Owner action to publish (no force, new tags only), from that checkout:

```powershell
git push origin canonical/candidate-20261008:integration/git-sync-20261008
git push origin accepted/phase1-core-freeze-31a34dcb accepted/runtime-v1-freeze-20261007 accepted/phase2-ops-r6-9a0be52c accepted/phase2-closure-f-fcd0d72e accepted/phase2-oq-g-0b49d86d accepted/m36-m38-closed-frozen-bd7c450 accepted/dynamic-planning-slice1-565eae8
```

Then verify with a fresh clone: `git clone` the repository, check the integration tip equals the candidate tip,
and run the runbook section 1 materialization (its ancestor guard must pass).

## 7. Not verified / limitations

- The runtime `.venv` was a copy of the accepted Phase 2 venv; a clean install from `requirements.txt` is not
  qualified (R-3). Does not affect the verdict on the integrated bytes.
- The reproduction did not re-run the long-context (L) and hard-reasoning (RH) suites; their frozen results stand.
  The 2–7 % lower decode today has no isolated cause.
- Runtime v1 itself has never had a Codex audit; it is frozen by owner ruling.
- No physical acceptance, no production activation, no cutover. C7 gate 5 (`/ask` Chat path) stays NOT MET.
