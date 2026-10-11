# A0 URI Assist foundation — qualification (cloud, automatable criteria)

Branch `milestone/a0-assist-foundation-20261010` @ `1844b48` (stacked on W1 `db7c02c`), docs after it. Host: Linux
cloud container; Flutter 3.47.7 / Dart 3.13.5; Chromium 1194 via Playwright 1.56 (test harness only).

**Verdict: TESTED — automatable criteria met; NOT independently accepted (Codex); NOT integrated; NOT activated.
Every perception adapter reports UNAVAILABLE in this build, so A0 observes nothing in production yet.**

## 1. Criteria

| ID | Status | Evidence |
|---|---|---|
| A0-AC1 opening observes nothing | MET | Python `test_opening_assist_calls_no_adapter`; Flutter "opening Assist observes nothing" (only `assist_status` sent) |
| A0-AC2 three scope kinds; screen needs second confirmation | MET | access + Flutter screen-confirmation tests |
| A0-AC3 five separate permissions; A0 grants only Observe/Suggest | MET | parametrised refusal tests; UI permission strip |
| A0-AC4 immediate revocation, earlier observations stale | MET (also at worker level after F4: Stop is never queued behind an answer) | access tests; `test_f4_*` |
| A0-AC5 pause/stop | MET | Python + Flutter |
| A0-AC6 observation bound to grant/generation/target/time | MET (adapter must bind the target: L2) | access/perception tests |
| A0-AC7 redaction before use | MET in both layers after the R3 repair, checked in Python and in real Chromium on the hostile fixtures plus 1,442 generated names (a prefix list joined with a secret-stem list, and names ending in code/pin with a short digit value), with readable controls (`hotpot`, `footpath`, `pincode`, `zipcode`, `countrycode`, `promocode`, `author`, `account`, `secretary`); rule completeness is still pattern-based (L-A0-2). **Correction (review R3 of `627f6b9`):** the earlier "MET in both layers after the R1 repair" (and the R2 repair after it) was false — both layers matched secret words only at word boundaries or after a fixed list of prefixes, so run-together names outside that list (`emailverificationcode`, `mfacode`, `onetimecode`, `twofactorcode`, `2facode`, `tfacode`, `authenticatorcode`, `authenticationcode`, `onetimepin`, `smspin`, `cardcode`, `cardverificationcode`, `authtoken`, `accesstoken`, `clientsecret`, `secretkey`) kept their values, and those values reached the Brain request. Both layers now match the secret stems anywhere inside a word and treat a 3–8 digit value as a code when a name, label or placeholder ends in code/pin (postal, country, area, promo, coupon, voucher, referral, bar, sort, IFSC and SWIFT codes excluded); the in-page patterns are string-identical to Python's (checked by test). **Correction (review R1 of `8019d41`):** the earlier "MET in both layers" was false — the in-page layer did not mask title, headings, labels, placeholders or the URL path (R1-04), and both layers missed names such as `OTPCode`, `SMSOTP`, `cvv2`, `MPIN`, `acctNumber` (R1-02). Python's second layer did mask the text surfaces, so the Brain prompt was clean; field values for those names were not. | `test_extension_snapshot_in_real_chromium…`, `test_f5_in_page_layer_matches_python…`, `test_a0_r1_review_regressions.py`, `test_a0_r3_review_regressions.py` |
| A0-AC8 structured browser perception | MET for the snapshot script (Chromium); **channel to URI NOT IMPLEMENTED** | Chromium tests |
| A0-AC9 on-demand vision | MET for gating/building (loopback, freshness, black-out or refusal, debounce, slot, cancellable send); **application path NOT VERIFIED** (no GPU/Runtime v1) and disabled by default | vision tests |
| A0-AC10 no external transfer | MET: loopback URL check and a client that ignores proxy settings (F7) | loopback tests |
| A0-AC11 UI: third entry, orb unchanged, scope indicator, revoke, Ctrl+4 | MET in widget tests; **live on Windows NOT VERIFIED** | `assist_mode_test.dart` (16), existing all-modes orb/voice-dock tests |
| A0-AC12 diagnostics | MET (content-free) | diagnostics tests |
| A0-AC13 no frozen path; gates unchanged | MET (protected part); Phase 1 zip check BLOCKED here | gates below |

## 2. Gates

| Gate | Result | Evidence |
|---|---|---|
| `tests/assist` | 57 passed (incl. 2 real-Chromium tests) | run 2026-10-10 |
| Flutter full | 526 passed, 5 skipped, 1 failed = the pre-existing `reference_render_test: render desktop dashboard` (fails identically on the baseline here) | `evidence/flutter_repaired_1844b48_linux.txt`, `baseline_flutter_linux_ffdf534.txt` |
| Python combined | see `W1_QUALIFICATION.md` §2 (identical failure set to baseline) | same |
| `flutter analyze lib` | 1 pre-existing info (`providers_screen.dart:730`), none in new code | run |

## 3. Not verified (and effect)

Worker hook live on Windows; any real adapter (extension channel, UIA, screen capture); vision through the
application path; GPU memory with the Assist view open; human use. These block ACTIVATION, not the code verdict.
Codex review blocks ACCEPTANCE.

## 4. Carried limitations

- **L-A0-1** Assist permission authority is a new non-frozen module (Core frozen) — owner decision (checklist #2).
- **L-A0-2** Redaction is rule-based; unusual field names or free text secrets may pass; screenshots are refused when
  a visible private field cannot be located.
- **L-A0-3** Capture runs on the worker's command thread (bounded by the adapter, which does not exist yet); adapters
  must be fast and time-limited.
- **L-A0-4** Live Assist findings are format checks only; they never change anything.
