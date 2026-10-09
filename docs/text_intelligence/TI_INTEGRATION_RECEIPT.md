# Text Intelligence — Integration Receipt

Date: 2026-10-09. Candidate branch `phase/text-intelligence`, parent `68cac3d` (accepted Working System tip,
published as `integration/working-system-20261008` on `github.com/sche004-cyber/Uri`).

## 1. Gates

| Gate | Result | Evidence |
|---|---|---|
| Independent review | Codex round 16 on `18f79ba`: ACCEPT WITH FINDINGS (16 rounds) | `TI_AUDIT_RECORD.md` |
| Frozen boundaries | `ws_frozen_check.py`: ok, 121/121 Phase 1 files byte-identical, no protected path changed | run at `18f79ba` |
| `tests/ws` | 207 passed, 10 skipped | `18f79ba` |
| `tests/oi` | 161 passed, 8 skipped | `18f79ba` |
| Flutter full suite | 301 passed, 4 skipped | `dd1e49a` (later commits change no Dart) |
| Chain: phase2 | 486 passed / 0 failed / 2 skipped (= accepted) | `uri-ti-gate2\evidence\ti_chain\chain_summary.json` |
| Chain: authority | 134 passed / 0 failed (= accepted) | same |
| Chain: phase1-full | 2,675 passed / 11 failed / 12 skipped; **same failure set as accepted**; one outcome change: `test_gemma_worker_mcp::LiveOllamaIntegrationTests::test_live_ollama_status_and_model` passed → skipped because Ollama is not running since the 06:52 reboot (the same test skips on the accepted gate tree `uri-ws-gate2` today). The chain's strict rule therefore reports `ALL_PASS: false`. | `uri-ti-gate2\evidence\ti_chain2\chain_summary.json` |
| Chain: phase1-scope | PASS: nothing outside Phase 2 scope, no importer of Phase 2/OI packages, 98 frozen files identical | same |
| Chain: residue | PASS | same |
| Live | owner demo passed through the real worker, real widgets and the built app; matrix 160/161 | `TI_TEST_MATRIX.md` |

Gate tree: `C:\Users\cheta\Development\uri-ti-gate2\uri-agent`, materialized with `--exclude-oi-tests` from the
candidate at `9402c94` (the later commits change only `uri_operational_intelligence/text_verify.py`, `tests/ws` and
docs, all outside the Phase 1/2 suites' inputs), with the accepted `evidence\` copied beside it and the accepted
`work\c1\checkpoints` copied in (first chain attempt without them: recorded in the report §6).

Not run: chain gates `flutter` (covered by the full Flutter run), `bridge` and `native` (no change to the Phase 2
bridge or native executors; same choice as the WS integration).

## 2. Publication

- Pushed `phase/text-intelligence` to `uri-repo` (`github.com/sche004-cyber/Uri`) as a new branch, no force.
  Tip and verification: see §3.
- **Not done (owner decision):** moving the canonical development branch `integration/git-sync-20261008`
  (`037229c`) or `integration/working-system-20261008`. Reasons: (1) the WS hardening branch
  `integration/ws-hardening-20261009` (also from `68cac3d`, Codex-accepted, unpublished) plans to fast-forward the
  canonical branch; a merge of both conflicts textually in `worker_bridge.py`, `oi_conversation.dart` and the two
  scope-guard lists (`git merge-tree`, 4 files), so the order is an owner choice; (2) the strict chain flag is false
  for an environmental reason (Ollama), which the owner should accept or have re-run with Ollama started.
- No production cutover, no launcher change, no shortcut change, no paid service, nothing sent.

## 3. Push record

(filled after the push below)
