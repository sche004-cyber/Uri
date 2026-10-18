# BRAIN-QC-20261018 - Brain Quick Controls: plan, design and acceptance criteria

Owner-approved milestone (brief: `BRAIN_QC_BRIEF.md` in this folder). Base: runtime-profiles candidate `f3d5eb29`
(`milestone/runtime-profiles-integ-20261017`, unintegrated). Branch `milestone/brain-quick-controls-20261018`.
Nothing here integrates, freezes, deploys or changes the default Brain.

## 1. What already existed (investigated before design; reused, not duplicated)

| Existing piece (f3d5eb29) | What it gives | Reused as |
|---|---|---|
| `runtime_profiles.derive_config / describe / plan_change / thinking_depth`, `MEASURED_MIB` | measured launch profiles derived from the frozen config; shrink refusal; Thinking -> depth | unchanged; the host and the worker call them |
| `runtime_profile_selection.ProfileFollower` + `control/oi/brain_profile.json` | the worker re-verifies the Brain against the selected profile without restarting (CONTEXT-1 repair) | unchanged; the host now writes the file (section 2) |
| `scripts/ws_brain_host.py` (lease, contention wait, release wait, calibration, request file) | controlled stop / start of the single Brain | extended with one request action, `reconfigure` |
| `brain_health` report/request link, worker `brain_restart` gate (`_restart_pending`) | turns refused while the host acts; RECOVERING state | extended (`reconfigure` action, refusal results open the gate) |
| reasoning policy depth `auto / fast / normal / deep` and the existing depth dropdown | per-turn Thinking with no reload | the Thinking chip sets the same `OiConversation.depth` |
| evidence `profiles_live` (P2, P3 PASS; P1 FAIL; switch sw4) | which profiles are qualified | encoded once, in `brain_quick_controls.CATALOG`, with the evidence path per entry |

The UI contract (`../RUNTIME_PROFILES_UI_CONTRACT.md`) listed the host `reconfigure` action and the controls as
"not yet wired". This milestone wires exactly that.

## 2. Design

- **Catalog** (`uri_operational_intelligence/brain_quick_controls.py`, new): the reviewed list of switchable profiles.
  Standard = frozen Runtime v1 (32K, vision, MTP); Long context = P2 (64K main only); Standard (no draft) = P3
  (32K + vision, no MTP: qualified, recognized, not the preferred 32K + vision choice); Long context with vision =
  P1, listed UNQUALIFIED with its reason (CRASH-1, DEMOTE-P1), never switchable. 16K / 128K / 32K main only are not
  offered (measured, not qualified).
- **Host** (`ws_brain_host.py`): request action `reconfigure` with `{ctx, vision, mtp}`. The host validates it again
  against the catalog (authority: a hand-written request for P1 is refused, nothing stops). Then: fit pre-check while
  the current Brain still runs (the running server counts as memory the switch frees); CONTENDED or UNMEASURED ->
  refused, the working Brain stays; otherwise stop -> derive -> write the selection file -> update the lease's
  expected VRAM -> the unchanged start path (release wait, contention wait, load, calibration). A reconfigure is also
  taken while a start waits for the GPU or the lease (a smaller profile may fit). An attached (foreign) instance is
  never switched. The host writes `profile_switch` (from, to, fit, timings, result) into its report. At every host
  start the selection file is synced to what the host runs (absent for frozen), so a stale selection can never make
  the worker refuse the frozen Brain.
- **Worker** (`worker_bridge.py`): `brain_reconfigure {profile_id, confirm_shrink?}` (refused while a turn runs,
  while another Brain request is unfinished, for anything outside the catalog, and without a live host; a context
  smaller than the last answer's context needs `confirm_shrink`). `brain_restart` can never write `reconfigure`.
  `brain_health` carries `controls`: options, the profile the worker VERIFIED as serving (`active`, only in READY /
  BUSY / DEGRADED, no switch pending, host profile equal), the switch in flight and the host's last switch record.
  During a switch: state RECOVERING, reason `PROFILE_SWITCH`, turns refused `BRAIN_RESTARTING`. The conversation
  history stays in the worker process (no restart).
- **UI** (`brain_quick_controls.dart`, new; one mount in `living_composer.dart`; additive state in
  `oi_conversation.dart`): three chips under the Workspace/dashboard chat box: Thinking (Auto / Off / On, per message;
  the menu also says what the last answer actually did), Vision (On / Off), Context (32K / 64K). A Vision or Context
  choice resolves to a qualified profile, says when the other dimension changes too, lists the unqualified
  combination disabled with its reason, asks for confirmation (reload time, conversation kept, GPU memory), and a
  second confirmation when the context shrinks below the conversation. Chips show "(starting)" / "(not running)"
  instead of a value until the worker verified it; "Switching to ..." while a switch runs. They step aside below
  640 x 420 logical pixels (UIV2-F3 no-overflow rule); the existing depth dropdown stays in the conversation header.
- **Not done (disclosed):** the user's choice is not persisted across a host restart (a new host starts Standard,
  and the UI shows what runs); MTP is never a user control; no automatic fallback after a failed start.

## 3. Acceptance criteria (written before qualification)

| ID | Criterion | Evidence required |
|---|---|---|
| QC-1 | Reuse, no duplication: the runtime-profiles modules `runtime_profiles.py`, `runtime_profile_selection.py`, `runtime_v1.py` are byte-identical to f3d5eb29; the switch reuses the existing host start path | `git diff f3d5eb29 --stat` |
| QC-2 | Thinking is per turn with no reload: Off -> `fast`, On -> `normal`, Auto -> `auto`; the UI reports the tier the answer used | widget tests; live: tiers FAST / NORMAL on the same server pid |
| QC-3 | Only qualified profiles are switchable; 64K + vision is shown disabled with its reason; the host refuses a non-qualified target even from a hand-written request, without stopping anything | unit tests (worker + host); live UI screenshot of the disabled entry |
| QC-4 | Readiness truthfulness: a profile is shown as current only after the worker verified the running server against it; while switching the UI says "Switching"; no state shows the target as current before READY | unit + widget tests; live health timeline sampled through the switch, screenshots |
| QC-5 | Safe transitions: fit pre-check before stopping (refusal keeps the Brain); the lease's expected VRAM follows the profile; measured release wait; no start with a CONTENDED fit; no demotion after a switch | unit tests; live host report (`profile_switch`, `gpu.fit`, `release_measurement`), census VRAM, calibration tok/s |
| QC-6 | Continuity: one worker process and one session carry the conversation through Standard -> Long context -> Standard; a fact told before the first switch is recalled after each switch through the real UI | live record: worker pid constant, recall answers |
| QC-7 | Turn safety: a switch is refused while a turn runs; turns are refused while the switch runs | unit tests; live attempt |
| QC-8 | Context shrink below the conversation needs explicit confirmation; history is never discarded | unit + widget tests |
| QC-9 | Frozen unchanged: `model_lab/integration/` (Runtime v1 frozen config) untouched; `scripts/ws_frozen_check.py` ok; UI V2 freeze `7893aaed` files only additive minimal edits | diffs, frozen check output |
| QC-10 | Gates: pytest `tests/oi tests/ws` no new failure vs f3d5eb29 (baseline 731 passed, 23 skipped); `flutter analyze` no new issue; full `flutter test` no new failure; Windows release build | logs in `evidence/` |
| QC-11 | Performance recorded: switch time to READY, VRAM release time, calibration and turn tok/s per profile, VRAM per profile | live record |
| QC-12 | Evidence-backed qualification receipt in this folder; only COMPLETED_WITH_RESULT supports a claim | `BRAIN_QC_QUALIFICATION.json` + report |
