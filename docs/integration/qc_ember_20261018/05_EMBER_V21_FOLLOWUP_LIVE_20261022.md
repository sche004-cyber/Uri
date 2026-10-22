# Ember V2.1 - follow-up live journeys on canonical (2026-10-22)

Closes the item left open in `04_EMBER_V21_CANONICAL_INTEGRATION_RECEIPT.md` section 3 (UI V2 returning and perf
journeys with Ember, P0 UIV2-DELTA-1).

| Item | Value |
|---|---|
| Source | `D:\uri-dev\uri-integ-ember` at canonical `9488c0fd` (clean) |
| Runtime | `D:\uri-dev\uri-integ-rt-e` (materialised from `bb61e976`; same Python as `9488c0fd`), installation `integ-e2` port 18301, re-provisioned 2026-10-22 from Git Bash (the 2026-10-18 installation's 24 h Core principal session had expired, which made Core journeys fail with `401 PRINCIPAL_SESSION_INVALID`; that attempt is not evidence) |
| Brain | Runtime v1 P3 (`--profile 32768,gpu,0`), production host, own lease, no override; desktop GPU at AT_RISK -273 MiB after the owner-approved closing of Chrome and ChatGPT |
| Driver | UI V2 driver `docs/operational_intelligence/profiles_live/evidence/harness/uiv2_driver.dart` (unchanged, sha `884902e2...`) |

| Run | Result |
|---|---|
| `e-main` (fresh prefs) | **68/68** |
| `e-returning` (prefs from `e-main`) | **12/12** |
| `e-perf` | **3/3**; decode 95.7-98.1 tok/s, first token 0.26-0.92 s; Brain calibration 106.6 tok/s; idle frame build p95 under 1 ms |

Records: `evidence_followup_20261022/` (observations, native execution, session and Brain records).
