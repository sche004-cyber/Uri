# C7: cutover requirements (preparation only)

Date: 2026-10-05. Status: **PREPARED. Nothing here has been executed or authorized.** No launcher, scheduled task, shortcut, default port, production data or model configuration was changed. This list collects the gates that must all hold before anyone asks the owner for cutover authorization.

## Entry gates (each needs evidence and a reviewer other than the implementer)

| # | Gate | Current state |
|---|---|---|
| 1 | An independent final acceptance audit of the Phase 1 tree (C1 to C7), including the third-review repairs | Not done. The third review is provisional. |
| 2 | The C1 identity and source pin are accepted, including the bootstrap import gate (`scripts/c1_bootstrap.py`) | Repaired in the third review. Not yet accepted. |
| 3 | The C5 Brain activation policy change is reviewed: the manifest `model_policy`, which rows the launched server composes, and the evidence from a real local model | Not started (review decision 2). Seams are built and exercised in-process with real local models. |
| 4 | Native harness qualification (Claude Code, Codex): client-owned login, Windows containment evidence, a live smoke run, `HarnessRegistry.qualify` with evidence. Or the owner explicitly decides to ship without harnesses. | Blocked on native login (owner action). Antigravity stays refused. |
| 5 | C6: Chat connected to the paired runtime, a pinned UI build in the client manifest, voice parity decided | Not done (see `C6_UI_INTEGRATION_CONTRACT.md`) |
| 6 | Owner map and key lineage for every historical installation, plus a copy-first migration rehearsal into fresh roots | Not authorized |
| 7 | Every `execution_uncertain` turn and unsettled client journal entry is reconciled by the user. None is replayed. | Procedure defined. No production data touched. |
| 8 | A fresh checkpoint of the final tree, plus an offline rollback rehearsal from that exact archive (`scripts/phase1_offline_rollback.py`) | To be repeated on the accepted tree |
| 9 | The full-suite failures are triaged. The 11 `e8e3b65` failures are confirmed pre-existing, and each is either fixed or explicitly accepted. | Confirmed pre-existing in the third review. Not fixed. |
| 10 | The owner gives explicit written cutover authorization naming the exact manifests, ports and launch entries | Not requested |

## Cutover procedure (for later; requires gate 10)

1. Keep `Launch URI.bat`, the `URIServer` task and port 8000 untouched until the new launcher is proven on its own port.
2. Provision the accepted server and client manifests into fresh roots, with no legacy data.
3. Start through `scripts/uri_server.ps1` and `scripts/uri_client.ps1` only. Verify the signed identity, the pinned sources and the single instance.
4. Run `validate_c5_live.py` and the C6 bridge against the installed roots. Results must be counts and digests only, never private content.
5. Copy historical data copy-first, only to the client the owner names. Keep the originals.
6. Switch the default entry only after steps 1 to 5 pass and are reviewed. Retire legacy entries in a separate, later review.

## Stop conditions

Stop and report, without proceeding, if any of these is needed: changing production shortcuts, tasks, models or data outside the authorized list; using shared client authentication; replaying an uncertain effect; downgrading a newer schema; substituting a model or provider silently; or weakening any gate to make a step pass.
