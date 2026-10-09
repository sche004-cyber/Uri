# Live voice, Brain coexistence and companion activation: plan of record

Date: 2026-10-09. Branch `phase/live-voice`, worktree `C:\Users\cheta\Development\uri-live-voice`, created from
the canonical development tip `integration/git-sync-20261008` = `b02ed4f` (fetched from `uri-repo` at 17:15 IST;
the brief named `f24d57a`, which the scheduler integration had since fast-forwarded). Written before
implementation. Changes after this point are recorded in section 9, not made silently.

## 1. Baseline (inspected, not assumed)

| Capability | State on `b02ed4f` | Evidence |
|---|---|---|
| Voice presentation: `VoiceSession` reducer, `VoiceSessionController` watchdog, `VoiceServiceAdapter` seam, waveform, transcript, `VoiceCompanionSource` | IMPLEMENTED, ACCEPTED, fed only by scripted signals (SIMULATED) | `uri_ui/lib/living/voice/*`, companion settings report section 5 |
| Installed-voice catalog, previews, rate/pitch/volume (measured) | IMPLEMENTED, ACCEPTED | `windows_voice_catalog.dart`, `assets/voice/voice_engine.ps1` |
| Microphone capture, speech recognition, URI reply speech | NOT IMPLEMENTED | companion integration receipt section 6 item 1 |
| Conversation over Core + OI + Runtime v1 | IMPLEMENTED, ACCEPTED (`OiConversation.send` -> integrated worker `oi_turn`) | `docs/working_system/WS_BLUEPRINT.md` |
| Deterministic routing of simple commands | IMPLEMENTED: local presentation commands in the composer (`parseLocalUiCommand`), OI triage for Brain status, memory and similar | `living_composer.dart`, `uri_operational_intelligence/triage.py` |
| Drafting desk for transcripts (`uri.text_input.v1`, `sendTranscript`, `uri.ti.draft.v1`) | NOT ON CANONICAL. Text Intelligence line, Codex TIWS r4 ACCEPT WITH FINDINGS, landing on canonical pending (TI session, message 2026-10-09) | `integration/ti-on-ws-hardening-20261009` |
| A2UI | NOT ON CANONICAL; `phase/a2ui` Codex round 1 REJECT (A2UI session, message 2026-10-09) | `phase/a2ui` |
| URI Doctor | no Doctor module on canonical (search of the tree); Brain health exists (`brain_health`) | `git ls-tree` search |
| Prior art not on canonical | `_V1` `scripts/uri_voice_transcribe.py` (faster-whisper base.en CPU int8 after SAPI dictation failed owner acceptance on 2026-10-04); `feature/uri-dictation` (faster-whisper helper, polish prompt) | `_V1/docs/plans/CAMERA_VOICE_GEMMA_STT_REPAIR.md` |
| Local assets already on this PC | faster-whisper base.en model with a hash manifest at `%LOCALAPPDATA%\URI\models\faster-whisper-base.en` (MIT, revision `3d3d5de`); `_V1\.venv_voice` with faster-whisper 1.2.1, ctranslate2 4.8.2, sounddevice 0.5.6, av 18.1.0 | file listing, manifest |
| Microphone | `Microphone (Sennheiser Profile)`, default input; default output `Speakers (High Definition Audio Device)` | sounddevice enumeration |

Feasibility probe (17:33 IST, scratch, not evidence of the product): a System.Speech sentence played through the
speakers was captured by the real microphone and transcribed by base.en on CPU (model load 338 ms; 6.5 s of
audio in 692 ms; words correct, numbers normalised to "3.30"). The same probe shows that URI's own speech reaches
the microphone, so an open microphone during playback would create a feedback loop.

## 2. Decisions

1. **Recogniser: faster-whisper base.en, CPU, int8**, on demand in a separate voice process. Reasons: already
   present and hash-pinned (no download), CPU only (the Brain keeps the GPU), owner-run research on 2026-10-04
   chose it after System.Speech dictation failed acceptance, and the probe works. The comparison in the report
   measures it against System.Speech dictation on the same real-microphone recordings. Larger Whisper models,
   whisper.cpp, Moonshine and Vosk are researched and not installed unless base.en fails the accuracy criterion
   (AC-3); then the smallest model that passes is proposed to the owner before any download.
2. **Interaction: push-to-talk, half-duplex.** The microphone is open only while the user holds the talk control
   (button or key). Pressing it while URI speaks stops URI first (barge-in), then opens the microphone. The
   microphone is never open while URI's audio plays. No always-on listening and no wake word in this phase.
   Voice-activity detection is used only inside a held capture (onset for the waveform, Silero VAD filter in the
   recogniser).
3. **Speech output: the existing Windows bridge** (`voice_engine.ps1`, both engines, the user's voice, rate, pitch
   and volume). The voice process renders each sentence to audio, plays it itself, and measures the level of the
   audio it plays, so the speaking animation follows the real output. Replies are spoken sentence by sentence as
   they stream.
4. **Authority unchanged.** A finished transcript is submitted exactly like typed text: the local presentation
   command parser first, then `OiConversation.send`. Speech can never approve, confirm, deny or select a Brain;
   those remain buttons. When URI asks for approval, it says so aloud and points to the card.
5. **Modes.** Conversation mode: transcript -> turn -> spoken reply. Drafting mode: transcript -> Text
   Intelligence draft desk (`sendTranscript(..., dictation: true)`, original and corrected text shown by the
   existing Draft panel). Drafting mode is shown unavailable, with the reason, until TI is on canonical and merged
   here. No drafting logic is written in this phase.
6. **Placement.** Voice process: `uri_ui/assets/voice/uri_voice_service.py` (bundled beside `voice_engine.ps1`, run
   from the application's own asset directory with `python -I`). Its interpreter: a pinned virtual environment
   provisioned by `uri_ui/tool/voice/provision_voice_env.ps1` under `%LOCALAPPDATA%\URI\voice\venv`, or
   `URI_VOICE_PYTHON`. Dart: `lib/services/live_voice_service.dart` (process, protocol, `VoiceServiceAdapter`) and
   `lib/living/voice/voice_interaction.dart` (push-to-talk, modes, reply speech). No change under `uri_core/`,
   `uri_supervisor*/`, Runtime v1, frozen files, launchers or `uri_operational_intelligence/` is planned.
7. **Brain coexistence.** Investigate start order with per-process residency evidence under the machine-wide GPU
   lease; do not change Runtime v1. The voice path uses no GPU.

## 3. Acceptance criteria

| ID | Criterion | Evidence required |
|---|---|---|
| AC-1 | Microphone list, selection persisted, default device used when none chosen; a missing or denied microphone gives a specific, recoverable message | unit tests + live run with the real device |
| AC-2 | Push-to-talk captures the real microphone; live level drives the waveform; partial transcripts appear while speaking; the final transcript arrives after release | live run, event log |
| AC-3 | Recognition quality measured on real-microphone audio: word error rate per engine on the same recordings; base.en accepted only if WER <= 10 % on the office/conversation set | comparison table + raw transcripts |
| AC-4 | Latency measured: release -> final transcript; final transcript -> first reply audio; CPU, RSS, VRAM of the voice process | measurement table |
| AC-5 | Cancel (Esc / button), recognition failure, empty speech, and maximum capture length each end cleanly with a notice; no orphan process; disposing the app ends the voice process | tests + live |
| AC-6 | Conversation mode end to end on the real worker and Brain: spoken question -> recognised -> Core/OI turn -> answer -> spoken through the selected voice | live receipt |
| AC-7 | Speech never authorises: spoken "yes/approve/send it" while an approval card is open does not approve; approval text is spoken as a pointer to the card | unit tests + live |
| AC-8 | Companion states follow real activity: listening while capturing, thinking while transcribing and while the turn runs, speaking only while reply audio plays (level from the played audio), idle after; error state on failure | event receipt + captures |
| AC-9 | Interruption: pressing talk or Stop while URI speaks stops audio within 300 ms and drops the rest of the reply; no microphone capture during playback | tests + live measurement |
| AC-10 | Voice settings: voice, volume, rate, pitch apply to replies; speak-replies toggle; microphone choice; mode; nothing simulated presented as working | tests + capture |
| AC-11 | Minimised window: capture and playback keep working or stop explicitly; companion renders no frames while minimised (accepted behaviour unchanged) | live |
| AC-12 | Drafting mode: either working through TI on canonical (dictated informal letter -> corrected draft, original shown, facts kept), or shown unavailable with the reason | live receipt or test |
| AC-13 | Brain coexistence: start-order effect measured with per-process non-local GPU memory; voice adds no GPU memory; Adaptive back-off observed once under a live Brain if the lease permits | evidence files |
| AC-14 | Regression: `flutter test` full, `flutter analyze` on changed paths, `ws_frozen_check.py`, `pytest tests/oi tests/ws`, voice-process unit tests | logs |
| AC-15 | Independent Codex review ACCEPT or ACCEPT WITH FINDINGS with valid findings repaired | review record |
| AC-16 | Integration through an isolated worktree, receipt, fast-forward only, fresh-clone verification; no cutover | receipt |

## 4. Stop conditions

Stop and report if: a frozen or accepted file outside the plan must change; speech would need to approve
anything; a GPU benchmark would run without the lease or against another thread's lease; a model download is
needed (owner decision); the microphone cannot be opened by a desktop app for a reason only an elevated change can
fix.

## 9. Changes to this plan

| When | Change | Why |
|---|---|---|
| 18:07 | Brain runs use the Brain host's own fit check; `--override-contention` only with owner authorisation (given 19:18 for this phase's tests) | the host refused: 15.3 GB needed, 14.2 GB free |
| 18:20 | user vocabulary added (decision 1 extended) | measured: local names were the main errors |
| 19:55 | noise guard and bounded decoding added (decision 1) | room-noise hallucinations and CPU loops found in live runs |
| 20:25 | recogniser recordings kept out of the repository (hashes only) | owner: another household member used the microphone |
| 20:25 | own-voice session (AC-2/3 human talker) deferred | owner away for some weeks |
