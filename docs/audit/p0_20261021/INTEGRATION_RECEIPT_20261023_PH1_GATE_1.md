# Integration receipt — PH1-GATE-1 test-only dependency (2026-10-23)

Authority: owner decision OPEN-22 (DEC-099): narrowly scoped dependency repair with independent verification.
Push approved through the session's permission prompt; fast-forward; no force-push.

| Item | Value |
|---|---|
| Canonical before / after | `b19442000414ae833eee7097a7082aed4bb4d854` -> `c036a901b4544f1df17aa8c118877ef364c48d71` (`ls-remote` 2026-10-23T03:27:16Z; tip re-checked before the push) |
| Change | new `requirements-test.txt` (`jsonschema>=4.18`, test-only) and `docs/governance/PH1_GATE_1_TEST_DEPENDENCY.md`; `requirements.txt` and all code unchanged |
| Independent review | r1 `D:/uri-dev/lifecycle/PH1-GATE-1`: `codex_cli` ACCEPT on `2c3a51ed`; gate failed only by host-load subprocess timeouts (targeted re-run 126 passed / 1 baseline failure); r2 `D:/uri-dev/lifecycle/PH1-GATE-1-r2`: `codex_cli` ACCEPT, no findings, on exact commit `c036a901` (merge of canonical `b1944200`, parents `2c3a51ed` + `b1944200`) |
| Gates on exact commit | driver QUALIFICATION ok: py-office candidate 811 passed / 1 failed vs baseline 810 / 2 (the remaining failure is `test_page_blocks_every_network_attempt_in_edge`: no built Office bundle in a dev checkout); VERIFIED, `evidence_ok_for_candidate: true` |
| Functional evidence | gate venv with `pip install -r requirements-test.txt`: the two `jsonschema` modules pass (68); whole-repository collection 10,534 tests, only PH1-GATE-2 errors left |
| Frozen integrity | `ws_frozen_check` ok on a clean checkout of canonical `c036a901` |
| How to use | test environments: `python -m pip install -r requirements.txt -r requirements-test.txt` |
| Rollback | `git revert -m 2 c036a901` as a new commit |
