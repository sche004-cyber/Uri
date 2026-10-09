# Text Intelligence + WS hardening: canonical integration receipt

Date: 2026-10-09. Recorded by Claude (the Text Intelligence session) from the primary evidence in `evidence/` next to
this file and in `TIWS_INTEGRATION_REPORT.md`.

## 1. What is integrated

| Item | Value |
|---|---|
| Canonical branch | `integration/git-sync-20261008` on `uri-repo` (`github.com/sche004-cyber/Uri`) |
| Canonical tip before | `b02ed4f` (URI Scheduler; contains companions `f24d57a` and WS hardening `7160614`) |
| Integration commit | the commit that adds this receipt (docs and evidence only, a child of `f0a8103`). Its hash is in the push record (§5) |
| Method | fast-forward of the canonical branch to the TI branch `integration/ti-on-ws-hardening-20261009`. No force, no rebase of published history |
| Content added on top of `b02ed4f` | Text Intelligence (`phase/text-intelligence` `2563ca5`) merged with WS hardening; INT-1/INT-2 glue; L-2 dictation vs commands; L-4 reassignment warning; `uri.ti.draft.v1` fields; L9 live cases; tests; docs and evidence. `text_intent.py` is byte-identical to the round-5-accepted file |
| Not changed | `uri_core/`, `uri_supervisor*/`, `uri_harness_adapters/`, `model_lab/integration/`, root `.gitignore` (frozen check 121/121; Codex r5, r10) |

## 2. Gates

| Gate | Result |
|---|---|
| Chain at `48d2f78` (code = final, except one test file and docs) | ALL_PASS: phase2 486/0/2, authority 134/0, phase1-full 2,676/11/11 with outcome identity, phase1-scope and residue PASS |
| `pytest tests/ws tests/oi` at `f0a8103` | 472 passed, 22 skipped |
| `tests/scheduler` (base interpreter) | 71/71. The venv-redirector failure SCH-ENV-1 also occurs on `b02ed4f` without TI |
| Flutter full | 446 passed, 4 skipped (= canonical 431/3 + TI 15/1). No Dart change after `48d2f78` |
| Frozen check | ok, 121/121 |
| Codex | TI r16 ACCEPT WITH FINDINGS. TIWS r1 AWF, r2/r3 REJECT (repaired), r4 AWF, r5 ACCEPT, r6-r9 REJECT (LV-1 attempts, reverted), r10 AWF (wording, fixed). Codex built none of this code |
| Live (Runtime v1, under the lease, no demotion) | matrix 100/103 (M1 model residue L-6; L9d = LV-1); L-9 closed; real worker TI 2/2 and WS 11/1-skip; Living UI TI and WS pass |

## 3. Limitations carried (owner acceptance needed)

RESIDUAL: L-1, L-3, L-5, L-6, LV-1, LV-2, LV-3, the auto-mode residue of L-2, and the recall limits of the L-4 check.
DESIGN: L-7. ENVIRONMENT: L-8 (VRAM residency). COSMETIC: L-10.
Carried from WS hardening: CUT-1 (no production cutover), SAFE-1 (historical), GPU-2/3/4, R-SHUT, R-STALL, L-MUTEX,
L-CLASSIC, L-RT, L-SIM, L-PLAN, OI-SEC-1, CLOUD, MD-1.
New environment notes:
- ENV-C3: an Ollama launched from Git Bash breaks the phase1 c3 test. Launch Ollama from PowerShell for gates.
- SCH-ENV-1: a scheduler test fails under a venv redirector.
Owner decision pending: P-GOV-1 (handoff).

## 4. Staging and production

Staging is recorded in `TIWS_STAGING_RECEIPT.md`, after this commit is on the canonical branch. No production
cutover: the legacy `\URIServer` on port 8000, its scheduled task, and the shortcuts are untouched.

## 5. Push record

(Filled after the verified fast-forward.)
