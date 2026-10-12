# URI Phase 1 + Phase 2 Integration Report — 2026-10-08 (consolidation round 2)

## 1. Acceptance criteria (set before the work)

1. The accepted Phase 2 Round 7 candidate (`phase2oq-candidate-20261008-g.zip`, `0b49d86d…c4cd`) is in the canonical
   integration line byte-exact, with its evidence and post-acceptance records, traceable to its acceptance.
2. No frozen Phase 1 file changes.
3. No competing implementation is silently merged: if the earlier consolidation (round 1) or any other line holds a
   different version of a Phase 2 file, the difference is resolved explicitly.
4. The integrated line reproduces the accepted runtime tree exactly when materialized from Git.
5. The integration has its own regression evidence on that materialized tree, judged by the accepted chain's own
   pass criteria and pinned baselines — not by totals alone. Historical acceptance evidence is retained unchanged.
6. Status is reported per level (implemented / tested / independently accepted / physically qualified /
   production-active); C7 stays open.

## 2. What was integrated

| Commit | Content | Check |
|---|---|---|
| `6dea266` feat(phase2) | the 154 tree files of the OQ `-g` zip | each file's SHA-256 equals the zip `MANIFEST.json` entry (154/154); zip SHA-256 recomputed and equal |
| `fcb619a` evidence(phase2) | `phase2oq*` evidence (candidates `-`, `-b`..`-g`, chains 1–10, review rounds 1–7) under `docs/evidence/phase2/` | 431/433 files byte-equal; the two excluded are `__pycache__` bytecode ignored by `.gitignore` |
| `759d0d4` docs(phase2oq) | post-acceptance records written 14:42 (report §R acceptance record, checklist D-final, ledger line) | byte-equal to the live Phase 2 worktree |
| `94ad32e` docs(ledger) | restores the consolidation section CONS-1..14 in `URI_DEVELOPMENT_TODO.md`, which the byte-exact import had replaced with the Phase 2 copy | explicit, recorded; byte-exact re-insertion from `13bf68a` |
| tag `accepted/phase2-oq-g-0b49d86d` | → `6dea266` | — |

Competing versions: the only file both round 1 and the OQ candidate changed was `docs/plans/URI_DEVELOPMENT_TODO.md`
(round 1 added section 5; the Phase 2 session kept its own copy, as round 1 had noted). Resolution: the accepted
bytes were committed first, then section 5 was re-added in a separate, labelled commit. No other overlap existed.
No code from `_V1`, `eb73693` or any donor line was merged.

## 3. Verification

| Check | Result |
|---|---|
| Phase 1 frozen zip `31a34dcb…98cf7` | hash recomputed: equal; 121/121 frozen tree files byte-identical at the canonical tip |
| Overlap OQ ↔ Phase 1 freeze | 2 files (`C6_UI_INTEGRATION_CONTRACT.md`, `C7_CUTOVER_REQUIREMENTS.md`), both byte-identical to the frozen copies |
| Live Phase 2 worktree vs canonical tip | all 273 uncommitted paths byte-identical at `759d0d4` (the earlier 119 non-OQ paths were already in `925ad45`..`2325ad7`) |
| Materialized checkout (Git → `HEAD e8e3b65` + 273-path overlay) vs live worktree | 0 differences; runtime candidate `uri-canonical-runtime-candidate` rematerialized and byte-equal to the gate checkout |
| Regression chain (`scripts/phase2close_chain.py`) on the materialized checkout, 15:30–15:57 | **ALL_PASS**, identical to accepted chain10 (table below) |
| Authority checker tests after manifest update | 66 passed |
| Process cleanup after the chain | no supervisor, worker, Phase 2 server, `codex.exe` or `fake_executor` process left; no listener in 8000–8099 except the legacy 8000 |

| Gate | Accepted chain10 (Phase 2 worktree) | Round 2 (`docs/evidence/consolidation/chain_cons2/`) |
|---|---|---|
| Phase 2 suites | 486 passed, 2 skipped | 486 passed, 2 skipped |
| Phase 1 authority | 134 passed | 134 passed |
| Phase 1 full (Ollama unreachable) | 2,676 / 11 failed / 11 skipped; same failure set; pins hold | 2,676 / 11 / 11; 2,698 IDs, missing/added/changed none; pins hold |
| Phase 1 scope, residue | PASS | PASS |
| Flutter `uri_ui` | 205 passed, 2 skipped | 205 passed, 2 skipped |
| Live UI bridge ×10 | 10/10 | 10/10 |
| Native Codex lifecycle / mid-run cancel | `SETTLED_VERIFIED` / `SETTLED_EXECUTION_UNCERTAIN`, PID DEAD | same |
| Native worker (no client-profile login) | refuses `HARNESS_NOT_USABLE` | same |

Environment notes: gate venv = a copy of the Phase 2 worktree `.venv` (Python 3.13.15); `work/c1/checkpoints`
copied from the Phase 2 worktree (git-ignored, needed by one Phase 1 test, CONS-14); Ollama app running but the
chain points `OLLAMA_BASE_URL` at an unreachable port for the Phase 1 suite, as accepted.

## 4. Status after integration

| Level | State |
|---|---|
| Implemented | Phase 1 Core (frozen) + Phase 2A–2D, ops, closure, OQ |
| Tested | yes — accepted chain10 and the round-2 chain on the Git-materialized tree |
| Independently accepted | Phase 1 (freeze); Phase 2 OQ `-g` by Codex OQ round 7 (historical evidence retained in `docs/evidence/phase2/phase2oq_review/`). The round-2 integration itself: see the final audit for its independent review status |
| Physically qualified | **no** — PA-1..PA-13 pending |
| Production-active | **no** — the live PC runs the legacy server; C7 NOT READY; Chat traffic still on `/ask` (C7 gate 5, **not closed**) |
