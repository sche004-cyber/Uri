# URI Source-of-Truth Manifest — 2026-10-08 (consolidation round 2)

Status: **CANDIDATE.** It names the one source tree, the one runtime source and the accepted artifacts.
The live PC has not been switched to it. Production cutover, containment of the legacy server and branch
promotion are owner decisions (section 6). Machine-readable form: `docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json`.

Round 1 of this consolidation (Codex rounds 1–14, commits `e239b72..13bf68a`) built the authority manifest,
the checker and the PC audit. Round 2 (this record) imports the accepted Phase 2 operational-qualification
candidate, re-verifies the PC, and recovers the local-inference result.

## 1. One repository, one line

| Item | Value | Verified how |
|---|---|---|
| Authoritative repository | `github.com/sche004-cyber/Uri` | `git remote -v` in the canonical checkout |
| Canonical integration line | `integration/git-sync-20261008` (owner-designated) | GitHub branch API: not protected, tip `f8de153` before round 2 |
| Canonical development checkout | `C:\Users\cheta\Development\uri-canonical-candidate`, local branch `canonical/candidate-20261008` | fresh GitHub clone (round 1) |
| Base anchor | `e8e3b65` (ARN.1, legacy master tip) | `origin/master` of `uri-agent` |
| Historical mirror | `github.com/sche004-cyber/uri-agent` — untouched | — |

The proposed later rename of the line to `main` (and making it the GitHub default branch) is unchanged from
`URI_CANONICAL_BRANCH_DECISION.md` and still needs the owner.

## 2. Accepted artifacts and where they live in Git

| Artifact | SHA-256 (archive) | Verdict | Commit (bytes) | Tag (local; see section 6) |
|---|---|---|---|---|
| Phase 1 Core frozen checkpoint `final-closure-20261005-phase1.zip` | `31a34dcb…98cf7` | FROZEN (Phase 1 closure §10) | `925ad45` | `accepted/phase1-core-freeze-31a34dcb` |
| Runtime v1 research + freeze record (`model_lab/`) | — (record) | FROZEN 2026-10-07, verdict A STOCK | `f791d65` | `accepted/runtime-v1-freeze-20261007` |
| Phase 2 UI/operations `phase2ops` r6 | `9a0be52c…` | ACCEPTED (Codex r7) | `02fa0e1` | `accepted/phase2-ops-r6-9a0be52c` |
| Phase 2 closure `phase2close-…-f` | `fcd0d72e…` | ACCEPTED (Codex closure r6) | `b4a5977` | `accepted/phase2-closure-f-fcd0d72e` |
| **Phase 2 operational qualification `phase2oq-candidate-20261008-g`** | **`0b49d86d89b26d3332fcbfbc9b4b7b981cdc1075d5dc295588a5cef92a82c4cd`** | **ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE (Codex OQ r7)** | **`6dea266`** (+ evidence `fcb619a`, post-acceptance records `759d0d4`) | `accepted/phase2-oq-g-0b49d86d` |

Round-2 checks, all `COMPLETED_WITH_RESULT` on 2026-10-08 ~15:00 IST:
- archive hashes of the Phase 1 zip and the OQ `-g` zip recomputed: both match;
- the 121 frozen Phase 1 files at the canonical tip are byte-identical to the Phase 1 zip (the 122nd zip member,
  `GIT_DIFF.patch`, is checkpoint metadata, never a tree file);
- all 154 OQ tree files written from the zip match the zip's own `MANIFEST.json` SHA-256 values;
- the OQ zip overlaps the Phase 1 freeze in only two files (`C6_UI_INTEGRATION_CONTRACT.md`,
  `C7_CUTOVER_REQUIREMENTS.md`), both byte-identical to the frozen copies: **no frozen file changed**;
- every one of the 273 uncommitted paths in the live Phase 2 worktree (`.codex\worktrees\uri-phase2a\uri-agent`)
  is byte-identical to the canonical tip at `759d0d4`, so Git now holds the exact accepted tree.

## 3. One runtime source

| Item | Value |
|---|---|
| Runtime checkout (proposed authoritative) | `C:\Users\cheta\Development\uri-canonical-runtime-candidate` (materialized: `HEAD = e8e3b65` + uncommitted overlay) |
| Overlay | `docs/governance/consolidation/RUNTIME_OVERLAY_PHASE2OQ_G.txt` (273 paths) checked out from `759d0d4` |
| Why materialized | frozen `uri_core/core/runtime_identity.py` refuses unless `git HEAD == e8e3b65` (CONS-7, owner decision to change) |
| Authorized entrypoints | C1 launcher family only (`scripts/uri_server.ps1`, `uri_server_launcher.py`, `run_uri_isolated_server.py`, `run_uri_phase2_server.py`, client launchers, supervised worker) |
| Forbidden even inside it | `Launch URI.bat`, `scripts/launch_uri.ps1`, `scripts/uri_server_ctl.ps1`, `scripts/run_uri_server.py` |
| Start gate | `scripts/uri_authorized_start.ps1` (refuses while the strict checker finds an active legacy runtime) |
| Ports | loopback; frozen C1 refuses 8000, 8018, 8021, 11434, 1234 |
| Server / client state | fresh roots provisioned by `provision_uri_server.py` / `provision_uri_client.py`; no legacy `uri_workspace` import |
| Resident Brain runtime | Runtime v1 (section 4) — **not wired into the Core composition** |

## 4. Local inference (Brain) runtime

Runtime v1: official llama.cpp **b11425** Vulkan release + `Qwen3.6-35B-A3B-UD-IQ3_S` + `mmproj-F16` + exported MTP
draft head (`--spec-type draft-mtp --spec-draft-n-max 2`), flags pinned in `model_lab/integration/local_brain.json`.
This is the configuration behind the "~140 tokens/second on the RX 7900 GRE" result. Recovery and the 2026-10-08
reproduction: `URI_INFERENCE_OPTIMIZATION_RECOVERY.md`. Ollama and LM Studio are shared developer tools, not URI
runtimes.

## 5. What is not the source of truth

Everything else is a donor, preserved snapshot, experiment or legacy installation; classifications are in
`URI_SALVAGE_AND_RETIREMENT_LEDGER.md` and `URI_CLEANUP_AND_QUARANTINE_MANIFEST.md`. In particular: the legacy
`uri-agent` master checkout (still the live server via `\URIServer`), `_V1` (`62d564c`, superseded base), the
desktop mainline `eb73693` (donor, installed UI), and the Phase 1 / Phase 2 development worktrees (preserved; their
accepted content is now in Git).

## 6. Owner decisions still open (unchanged unless noted)

P-1 push of `canonical/candidate-20261008` as a new branch is **no longer needed**: the owner authorized pushing
accepted work to `integration/git-sync-20261008`, which round 2 fast-forwards once the Codex review accepts it (see the final audit for the published
SHA). Still open: the `main` rename/default branch (P-6), pushing the `donor/*` tags, containment of `\URIServer`
and the `URI.lnk` shortcuts (P-2, P-3), the authoritative state root and port (P-4), C7 cutover (P-8), CONS-7.
