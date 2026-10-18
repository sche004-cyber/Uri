# BRAIN-QC-20261018 - Brain Quick Controls: candidate report

Branch `milestone/brain-quick-controls-20261018` (base `f3d5eb29`). Code: `aa7a1cf6` (UI); the Python runtime code
has not changed since `0d599b6a`, and every session verified that byte for byte. Plan and acceptance criteria:
`BRAIN_QC_PLAN.md`. Record: `BRAIN_QC_QUALIFICATION.json`. Status: the candidate passes; independent review is
pending. Nothing is integrated, frozen, pushed or deployed. The default Brain stays the frozen Runtime v1.

## What the user gets
Three chips under the chat box in the Workspace / dashboard composer: **Thinking** (Auto / Off / On, per message; it
also shows what the last answer actually did), **Vision** (On / Off) and **Context** (32K / 64K). A Vision or Context
choice loads a qualified profile, Standard (frozen) or Long context (64K, no vision), after a confirmation. 64K with
vision is listed but disabled, with the reason it is not qualified (CRASH-1, DEMOTE-P1). The chips show "(starting)"
or "(not running)" until the worker has verified the running Brain, and "Switching to ..." during a reload.

## Live results (real Windows app via production main(), real worker, Core and Brain; automation input)
| Run | Checks | Switch to Long / back to Standard (s) | Decode tok/s Standard / Long / Standard after switch |
|---|---|---|---|
| qc-1 (Brain first) | 20/20 | 29.9 / 35.1 | short answers only |
| qc-2 (UI first) | 20/20 | 31.5 / 34.7 | 122.5 / 98.7 / 149.4 |
| qc-3 (UI first, `aa7a1cf6`) | 20/20 | 31.4 / 36.6 | 125.6 / 99.3 / 147.6 |

- **Thinking:** Off gave tier FAST and On gave NORMAL on the same server. Nothing reloaded.
- **Continuity:** the number 4817, told before the first switch, was recalled after each switch. The worker processes
  stayed the same and the session stayed the same.
- **Turn safety:** a message sent during a switch was refused with BRAIN_RESTARTING.
- **Old server stop:** about 3.5 s.
- **VRAM:** Long context uses 13.9 GB dedicated (fit FITS, +1.64 GB). Standard next to the open app window is
  AT_RISK (-0.29 to -0.34 GB) with 1.7 GB non-local, which is the known frozen-config behaviour. Decode after the
  switch was still healthy.
- **qc-1, Brain-first harness order:** the UI window opened after the Brain loaded. About 0.77 GB moved to system
  memory, and one 257-token Thinking answer decoded at 40 tok/s. This is P-GOV-1, which the launcher order (UI first)
  avoids. qc-2 and qc-3 use the launcher order.
- **Regression:** canonical UI V2 journeys 68/68 (`uiv2-main`, `uiv2-main-2` on the final code).
- **No-Brain run (`dry-1`):** nothing is shown as active, switching is disabled, and the chips say "(not running)".

## Gates (exact commit)
pytest tests/oi + tests/ws 759 passed / 23 skipped (baseline 731 / 23, plus 28 new); flutter test 776 passed;
flutter analyze 4 pre-existing infos; Windows release build OK; ws_frozen_check ok; frozen UI V2 files only additive.

## Open findings / limitations
- QC-F1: the profile choice is not persisted. A new Brain host starts on Standard, and the UI shows what actually runs.
- QC-F2: the context-shrink confirmation is verified by unit and widget tests only.
- QC-F3: the host's 60 s residency alert missed the qc-1 demotion because of timing. This is pre-existing host
  behaviour and is unchanged.
- QC-F4: `test_frozen_core` stray list (pre-existing at base) now also names the two new BRAIN-QC files.
- The new `reconfigure` action changes `ws_brain_host.py`, which the runtime-profiles IC-1 counts as byte-identical
  to 7c7a7776. Integrating BRAIN-QC therefore supersedes that file and needs its own review.
