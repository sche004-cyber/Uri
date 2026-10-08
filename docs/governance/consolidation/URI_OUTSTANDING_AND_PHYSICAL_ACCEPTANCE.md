# URI Outstanding Work, Limitations and Physical Acceptance Checklist — 2026-10-08

Status scale: RESEARCHED/PLANNED → IMPLEMENTED → TESTED → INDEPENDENTLY ACCEPTED → PHYSICALLY QUALIFIED →
PRODUCTION-ACTIVE. A component is given the highest level that primary evidence supports. Sources: the
Phase 2 OQ report (`docs/plans/PHASE2OQ_REPORT.md` §I–J), C7 readiness (`PHASE2CLOSE_C7_READINESS.md`), the
ledger (`docs/plans/URI_DEVELOPMENT_TODO.md`) and round-2 checks.

## 1. Component status

| Component | Researched / planned | Implemented | Tested | Independently accepted | Physically qualified | Production-active |
|---|---|---|---|---|---|---|
| Phase 1 Core (C1–C7) | yes | yes | yes | **yes** (frozen 2026-10-05) | no (C7 cutover not done) | **no** — live PC runs the legacy server |
| Phase 2A supervisor (admission, fencing, containment, recovery) | yes | yes | yes | yes (ops r7, closure r6, OQ r7) | no (PA-6/7, PA-11 power loss) | no |
| Phase 2B execution bridge + chat-to-task handoff (C6 Option B) | yes | yes | yes (widget, bridge ×10) | yes (OQ r7) | no (PA-13) | no |
| Native Codex CLI pathway | yes | yes | yes (run-scoped `SETTLED_VERIFIED`; worker up to auth) | yes (OQ r7) | no (PA-8, PA-10; EXE-1b) | no |
| Native Claude CLI pathway | yes | yes (descriptor) | partial (CLI not logged in) | no live acceptance | no (PA-9) | no |
| Worker security / client-profile isolation (ISO-1, CODEX_HOME pin, sandbox mode check) | yes | yes | yes | yes (closure r6, OQ r7) | no | no |
| Permission, approval, sandbox, cancellation controls | yes | yes | yes | yes | no (PA-2..PA-5) | no |
| Crash containment / process cleanup (SUP-1 repaired) | yes | yes | yes | yes (OQ r7) | no (PA-7) | no |
| Regression gates + pinned baselines | yes | yes | yes (chain10; round-2 chain, see final audit) | yes (OQ r7) | n/a | n/a |
| Qualification records + honest UI status | yes | yes | yes | yes | no | no |
| Runtime authority manifest, checker, start gate | yes | yes | yes (66 adversarial tests) | ACCEPT WITH FINDINGS (Codex r14) | n/a | no (not in the live launch path) |
| Runtime v1 resident Brain (llama.cpp b11425 + MTP) | yes | yes (standalone) | yes (qualification + soak 2026-10-07; reproduction 2026-10-08) | FROZEN by owner ruling (self-qualified, no Codex audit) | standalone soak only | **no** — not wired into the Core |
| Operational Intelligence integration (Brain ↔ Core) | planned (freeze record §18) | no | no | no | no | no |
| Chat `/ask` path (C7 gate 5) | — | legacy path | — | **C7 limitation: Chat traffic stays on `/ask`; NOT closed** | no | legacy only |
| Voice parity | planned (rules) | `_V1` status strip only | — | no | no | no |
| Desktop-line features (Google onboarding, Gmail/Drive/Docs, PPT, uploads, M36–M39, dynamic planning, dictation) | yes | yes on donor lines | donor records | donor acceptances only | no | installed donor UI is in daily use, not canonical |

## 2. Physical acceptance checklist (owner at the PC)

Runbook: `docs/plans/PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md`; tooling `scripts/phase2close_acceptance.py`.

- [ ] PA-1 launch the supervised profile from a provisioned install
- [ ] PA-2 approve a proposal; PA-3 deny one
- [ ] PA-4 cancel before dispatch; PA-5 cancel after dispatch (needs PA-10)
- [ ] PA-6 close / restart / reconnect; PA-7 worker and server interruption
- [ ] PA-8 Codex client-profile login (`login-guide`); PA-9 Claude client-profile login
- [ ] PA-10 native execution inside the worker (needs PA-8 and decision EXE-1b)
- [ ] PA-11 power-loss campaign on a VM (needs a hypervisor; owner attestation)
- [ ] PA-12 cutover authorization (written, naming manifests, ports, launch entries)
- [ ] PA-13 Chat → supervised handoff on the real app

## 3. Owner decisions

1. EXE-1b Codex sandbox backend for client profiles (`unelevated` leaves network open; `elevated` needs admin setup).
2. C6 decision 3 (which Brain rows the UI offers); voice rules 3–4.
3. Whether the 11 known Phase 1 full-suite failures are accepted or fixed (C7 gate 9).
4. P-2/P-3 containment of `\URIServer` and the `URI.lnk` shortcuts; stop the legacy server.
5. P-4 authoritative install dir, state root, port. P-6 `main` rename and default branch. Pushing `donor/*` tags.
6. CONS-7: keep runtime materialization or unfreeze `runtime_identity.py`'s `HEAD == e8e3b65` coupling.
7. Start of the Operational Intelligence milestone (Runtime v1 ↔ Core). Optional: remove Ollama's autostart.
8. Phase 2 freeze; C7 cutover.

## 4. Engineering items still to implement

| ID | Item | State |
|---|---|---|
| P2-5 / C7 gate 8 | rollback overlay covering supervisor, bridge, Phase 2 scripts and UI; offline rollback rehearsal from a fresh checkpoint | NOT IMPLEMENTED |
| R-3 | runtime `.venv` built from `requirements.txt` on a clean machine (accepted runs used a copied venv) | NOT QUALIFIED |
| R-4 | stop/uninstall tool for the C1 server (frozen launcher offers validate/start/status only) | NOT IMPLEMENTED |
| CONS-5 | per-installation UI preferences instead of the shared `com.example/uri_ui` file | DESIGN ONLY |
| CONS-9 / P2-6 | port desktop-line capabilities into the Core with provenance (C6 parity) before retiring the installed desktop UI | PLANNED |
| CONS-14 | `work/c1/checkpoints` provisional archives only on local disk | LOCAL ONLY |
| OI-1 | Operational Intelligence: Context Bridge (v1 layout), persistent Brain provider, FAST/NORMAL tier selection, escalation | PLANNED |
