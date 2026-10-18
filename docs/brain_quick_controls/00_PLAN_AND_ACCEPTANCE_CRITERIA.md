# BRAIN-QUICK-CONTROLS: Thinking, Vision and Context quick controls

Milestone id `BRAIN-QUICK-CONTROLS`. Branch `claude/brain-quick-controls-ghikbt`. Baseline canonical
`integration/git-sync-20261008` = `348677b7` (verified with `git ls-remote` on 2026-10-18); UI V2 freeze `7893aaed`
is an ancestor of it. Owner brief: "URI — START EMBER V2.1 AND BRAIN QUICK CONTROLS" (2026-10-18, milestone 2).
Method: ODRD (research the existing system before changing it). Lifecycle: `uri-development-lifecycle`.

## 1. Research findings (primary evidence, 2026-10-18)

| # | Finding | Evidence |
|---|---|---|
| F1 | The Brain is Runtime v1: llama-server b11425 (Vulkan), Qwen3.6-35B-A3B IQ3_S, 32K, vision projector on GPU, MTP draft. The configuration is frozen. | `model_lab/integration/local_brain.json`, `uri_operational_intelligence/runtime_v1.py:76-99`, `tests/oi/test_oi_runtime_v1.py` |
| F2 | The frozen profile requests 15,626 MiB of a 16 GB card: CONTENDED on the owner's desktop (about 15,072 MiB free). | `gpu_lease.py:42-55`, `receipts/ui-v2-20261016:docs/ui_v2/postint/integration/BRAIN_VRAM_HEADROOM_INVESTIGATION_20261017.md` |
| F3 | A research candidate already measured every profile (context x vision x MTP) and wrote the runtime half of these controls: `runtime_profiles.py`, `ws_brain_host --profile`, measured per-profile lease budgets. Status: NOT QUALIFIED, round-3 re-check pending, no owner adoption. It records the owner's 2026-10-17 additions "mutually exclusive Vision / MTP allocation" and the resume directive. | `origin/research/runtime-vram-r1-20261017` @ `7c7a7776`: `research/runtime_vram_r1/RUNTIME_VRAM_R1_REPORT.md`, `docs/operational_intelligence/RUNTIME_PROFILES_UI_CONTRACT.md` |
| F4 | Thinking is already a per-turn parameter end to end (`depth` auto/fast/normal/deep on `oi_turn`; NORMAL = 768-token budget). The UI exposes it as a dropdown, not persisted. | `reasoning_policy.py:44-59`, `worker_bridge.py:43`, `oi_conversation.dart:104,546,746`, `oi_widgets.dart:573-596` |
| F5 | Vision and context are load-time parameters; b11425 cannot unload only the projector or only the draft. A change is a controlled server restart (about 29 s to READY measured), the KV cache is rebuilt (about 10 s per 20K tokens), the worker's history survives. | R1 report sections 5, 8 |
| F6 | **No image reaches the Brain on the working-system path.** `oi_turn` has no image field; the composer's attach button uses the legacy HTTP upload. A Vision control without an image path would be a misleading indicator. | `worker_bridge.py:43`, `oi_conversation.dart:481-551`, `living_composer.dart:210-222` |
| F7 | The worker and the health view check the live server against the FROZEN config only (exact argv, `n_ctx`). Any derived profile would read FOREIGN_INSTANCE / CONTEXT_SIZE_MISMATCH. | `runtime_v1.py:204-240`, `run_uri_integrated_worker.py:182`, `worker_bridge.py:578-608` |
| F8 | Readiness can mislead today: Brain status is not refreshed after a restart request; the dot follows health while the text follows status; `backend()` reports vision and MTP from the config, not the live server; `/props` modalities are collected but never checked. | `oi_conversation.dart:274-305,351-420`, `oi_widgets.dart:508-552`, `brain_health.py:49`, `runtime_v1.py:228` |

Measured device requests used by this milestone (MiB; R1 `MEASURED_MIB`, checked against its probe files by
`tests/oi/test_runtime_profiles.py`):

| Profile | Request | Verdict on the owner desktop (R1) |
|---|---|---|
| 32K, vision GPU, MTP off | 14,360 | FITS |
| 64K, vision GPU, MTP off | 14,764 | AT_RISK (+308) |
| 128K, vision GPU, MTP off | 15,572 | AT_RISK |
| 16K / 32K / 64K / 128K, main only | 13,052 / 13,254 / 13,658 / 14,466 | FITS |
| 16K / 32K, main only + MTP | 14,265 / 14,515 | FITS |
| 32K, vision GPU, MTP on (frozen) | 15,620-15,626 | CONTENDED |

## 2. Design (minimal; reuses the R1 candidate and the existing Brain host)

- **R1 as declared prerequisite.** `7c7a7776` is merged unchanged (merge commit `a2c68bd0`) so its evidence, tests
  and correction log keep their provenance. This milestone's independent review covers the combined diff, which
  includes the R1 code. R1's own status is not upgraded by this merge.
- **Thinking: Auto / Off / On.** Maps to the existing `depth` auto / fast / normal. No runtime change, no reload.
  "Deep" stays an escalation offer and is not a quick control. The choice is persisted in the UI preferences.
- **Vision: Off / On.** On = projector on the GPU with MTP off (owner: Vision over MTP). Off = main only.
- **Context: 16K / 32K / 64K / 128K.** Only measured combinations are offered; AT_RISK combinations are labelled
  "tight" with the measured margin; nothing unmeasured or CONTENDED is offered.
- **Speed boost (MTP), optional.** A settings switch, offered only with Vision off at 16K / 32K (the measured FITS
  MTP profiles). Never a quick control, never chosen automatically.
- **The user's choice** is one file, `control/oi/brain_profile.json` (`uri.oi.brain_profile.v1`), validated by the
  worker and written by the Brain host only once it takes the switch (review R1-02: a refused or ignored request
  leaves the previous choice; the worker writes it only when the choice is the profile already running), read by the
  Brain host at start. `local_brain.json` is never touched. No file =
  the default profile (owner decision BQC-D1).
- **Switch = controlled host reconfigure.** New host request action `reconfigure` with the target profile. The host
  validates it with `runtime_profiles.derive_config` (measured profiles only), stops its own server, waits for the
  VRAM release, re-acquires the fit with the target's measured request, starts, calibrates. A target that does not
  fit waits `WAITING_FOR_GPU` with its explanation; it never falls back to another profile. During that wait (no
  Brain runs or loads) the host takes a new `reconfigure` and retargets the pending start (review R1-01); the UI keeps
  the controls usable, offers "Go back to <previous profile>", and shows how the last switch ended (waiting, did not
  start, refused, not taken) and choice-file errors (review R1-02). Controls lock only while the Brain stops or loads.
- **Identity follows the active profile.** The worker derives the expected config from the host report's active
  profile (measured profiles only, via `derive_config`) and checks the live server's exact argv and `n_ctx`
  against it. An unknown or unmeasured profile in the report is UNAVAILABLE, never accepted.
- **Session state.** The worker keeps the conversation history, pending cards and drafts across the switch; the UI
  keeps its message list. Image turns are recorded in history as text placeholders, so a later switch to Vision Off
  never needs media tokens. A switch is refused while a turn runs or a Brain request is pending.
- **Vision on turns.** `oi_turn` gains an optional `images` list (PNG / JPEG / WebP, at most 2 images and 1.25 MiB
  of decoded image bytes per turn, decoded and type-checked; sized so the base64 JSON stays below the frozen 2 MiB
  worker frame limit `uri_core.client_contracts.FRAME_LIMIT`; the UI scales larger pictures down before sending;
  review R5-03). The answer channel sends them as OpenAI `image_url` parts. Images with Vision
  off are refused `VISION_OFF` (the UI offers "Turn on Vision"); images on a turn that triage sends to Core, a plan
  or a harness are refused `IMAGE_ACTION_UNSUPPORTED`. Nothing is dropped silently.
- **Truthful readiness.** Health reports the active profile, the requested profile while a switch is pending,
  and vision from the live server's `/props` modalities (not the config). The UI refreshes Brain status when health
  changes, shows "Switching to ..." during a reconfigure, and never shows Vision On unless the live server reports it.

## 3. Acceptance criteria

Classification: Thinking, Vision and Context controls are `USER_FACING`; the host reconfigure and identity changes
are `INDIRECT` (qualified through the controls).

| AC | Criterion | Verified by |
|---|---|---|
| AC1 | Frozen files unchanged: `git diff 348677b7 -- model_lab/integration/ model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` empty; `ws_frozen_check` passes; with no profile file and the frozen default, the argv is byte-identical to `expected_argv(frozen)`. | tests + `ws_frozen_check` |
| AC2 | Thinking Auto / Off / On sends depth auto / fast / normal on the next turn without any Brain request or reload; the choice survives an app restart. | Python + Flutter tests; live J1 |
| AC3 | Vision and Context offer only measured, non-CONTENDED profiles; each option shows its cost (reload, "tight" margin). | unit tests on the offer table; Flutter widget test; live J2 |
| AC4 | A Vision or Context change issues exactly one `reconfigure` request, is refused while a turn runs or a request is pending, and the host starts exactly the derived argv after a VRAM release wait and a fit check with the target's measured request. No silent fallback. | host + bridge tests with fakes; live J2/J3 |
| AC5 | A smaller context than the live conversation is refused `CONTEXT_SMALLER_THAN_CONVERSATION` unless the user confirms; the UI asks first. | bridge + widget tests |
| AC6 | Conversation history, pending cards and drafts survive a profile switch; the next follow-up answers in context. | bridge test; live J3 |
| AC7 | With Vision On, an attached image reaches the Brain as an `image_url` part and is answered; with Vision Off it is refused `VISION_OFF` with an offer to turn Vision on; image actions are refused, never dropped. History stores a placeholder, never image bytes. | answer/orchestrator/bridge tests; live J4 |
| AC8 | Readiness is truthful: during a switch the UI shows the switching state and no READY; the Vision indicator follows the live server's modalities; the Brain status text and dot agree after a restart or reconfigure. | health + widget tests; live J2 |
| AC9 | The worker accepts a live server only if its exact argv and `n_ctx` match the derived config of the host's active, measured profile; anything else is FOREIGN / UNAVAILABLE. | runtime/identity tests |
| AC10 | 16 GB GPU: every offered profile's measured request FITS or is labelled AT_RISK; the lease and contention checks use that request; the live run records VRAM per profile with no demotion (decode within the healthy band). | gpu_lease tests; live J5 with census |
| AC11 | No regression: `tests/oi`, `tests/ws`, `tests/phase2a` (where runnable), `uri_ui` `flutter test` pass versus the baseline (failures compared by test id). | driver gates |
| AC12 | First-time and returning user: the controls are discoverable next to the Brain bar, each has a one-line explanation of its cost, the returning user sees the persisted choice. | live J1-J5, first-time and returning |

Live journeys (Windows, real app, owner's PC): J1 Thinking off/on/auto; J2 Vision on, then off; J3 switch with a
running conversation and follow-up; J4 image question with Vision on, and with Vision off; J5 Context 64K and 128K
with VRAM census; each first-time (no profile file) and returning (persisted).

## 4. Owner-only decisions

| Id | Decision | Status |
|---|---|---|
| BQC-D1 | Default profile when no choice exists. Recommended: 32K, Vision on (GPU), MTP off (14,360 MiB, FITS), because Vision is prioritised and an image then needs no reload. Alternatives: R1's 64K main only; or keep the frozen profile (CONTENDED). | ASKED 2026-10-18; development proceeds on the recommendation |
| BQC-D2 | Canonical integration of this milestone (and with it the R1 code). | after qualification |
| BQC-D3 | Live Windows qualification runs on the owner's PC (this project cannot reach it). | runbook provided at Stage 8 |

## 5. Shared files with Ember V2.1 (sibling milestone, integrates first)

This milestone keeps its Flutter changes in `uri_ui/lib/living/integration/oi_conversation.dart`,
`oi_widgets.dart` (Brain bar), `ws_settings.dart` and a new `brain_quick_controls.dart`, plus a minimal hook in
`uri_ui/lib/living/widgets/living_composer.dart` (image attachments on the working-system path). It does not touch
`oi_sources.dart`, `living/screens/settings/*`, the companion window or `windows/runner/*`. Expected shared-file
overlap: `living_composer.dart`, `uri_ui/test/ws/ws_integration_test.dart`. After Ember integrates, this branch is
rebased (merged) onto the new canonical and the affected validation is repeated.
