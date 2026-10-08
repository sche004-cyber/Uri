# Camera, voice and Gemma implementation handoff — 2026-10-04

This is a partial, uncommitted delivery under the direct User assignment.
Branch: `codex/antigravity-harness-recon`; HEAD remains
`62d564cf9d2fa25e5a9860d20dcc7070b112badb`. No release commit, push, milestone
closure or independent architecture audit is claimed. Unrelated dirty work
is preserved. Requirement statuses below describe task execution evidence,
not a formal milestone verdict.

## Delivered scope and files

- `scripts/uri_voice_listener.ps1`: opt-in Windows SAPI wake grammar,
  selected SAPI speech output, private status transport, authenticated idle
  session lease, mute and desktop-lock gates, single listener mutex.
- `scripts/uri_voice_transcribe.py`, `scripts/requirements-uri-voice.txt`:
  bounded post-wake microphone capture and CPU INT8 Whisper transcription.
  Raw microphone audio stays in memory. No shell execution of transcript text.
- `uri_ui/lib/widgets/desktop_voice.dart`,
  `uri_ui/lib/services/voice_event.dart`: fresh input events restore existing
  Chat and use canonical authenticated `AppState.ask()`.
- Minimal wiring in `uri_ui/lib/main.dart`, `uri_ui/lib/app.dart`, and
  `uri_ui/lib/services/app_state.dart`; existing harness wiring preserved.
- `uri_ui/lib/screens/settings/providers_screen.dart` and
  `uri_ui/test/m22_5_providers_test.dart`: endpoint/model saves run existing
  authenticated provider verification; failures stay visible and do not claim
  successful model readiness.
- `scripts/launch_uri.ps1`, `Launch URI Voice.bat`: reuse existing launcher
  with opt-in voice and explicit `Speakers (High Definition Audio Device)`.
- `tests/test_uri_voice_input.py`, `tests/test_uri_voice_status.py`,
  `uri_ui/test/voice_event_test.dart`, `uri_ui/test/voice_navigation_test.dart`.
- Four-stage records: root-cause audit, canonical architecture, migration plan,
  and STT repair amendment; approved voice-status design record and index link.

The existing backend Scheduled Task resolves to the legacy `uri-agent`
checkout. `_V1` desktop execution against that backend is live UI evidence;
it does not qualify a new `_V1` Core integration. Protected legacy code was
not edited. The existing one-click launcher started the backend successfully
and leaves the desktop app accessible.

## Requirement disposition

| Requirement | Status | Evidence / remaining condition |
|---|---|---|
| Camera 1 connection | VERIFIED | Authenticated ffprobe observed H.264 2304×1296 and PCM A-law audio at 192.168.1.5. Existing segment readable. Connection qualification only. |
| Camera 2 connection | BLOCKED | User identifies Tapo C210 at 192.168.1.11. Ping succeeds; TCP 554 refuses connection. Enable Camera Account/RTSP in Tapo and retest. PC Ethernet on the same LAN is sufficient. |
| Simultaneous recordings | BLOCKED | Camera 2 RTSP and disk budget prerequisites fail. No new recorder started. |
| Independent stop | NOT IMPLEMENTED | Existing recorder uses shared controls; no replacement implementation enabled. |
| Independent restart | NOT IMPLEMENTED | Same prerequisite stop. |
| Existing recording protection | VERIFIED | No existing recording deleted, moved or used as a cleanup fixture. Existing files left in place. |
| Two 350 GB allocations and 14-day cleanup | BLOCKED | D: free 697,975,984,128 bytes. Existing recording credit 3,133,081,993 bytes leaves only 1.109 GB margin against decimal 700 GB. Conservative 20 GB headroom requires approximately 18.89 GB more free space; binary caps require more. No cleanup run. |
| Spoken wake and restore | IMPLEMENTED — AWAITING USER TEST | User reported hearing recognition of “Oii URI”; navigation component test passes. Repeat minimized-app trial after final repair. Closed-app wake is NOT IMPLEMENTED. |
| Audible “Yes Chetan.” | VERIFIED | On resumed live manual listening test User explicitly answered “I heard ‘Yes Chetan.’” using selected PC speakers. Manual test does not prove wake detection. |
| Second spoken instruction | IMPLEMENTED — AWAITING USER TEST | Actual live Chat previously displayed “help me draft an office order.” and received an office draft. Repeat with final listener and selected Brain. |
| Camera commands without Gemma | NOT IMPLEMENTED | No camera capability or canonical execution adapter added because prerequisites fail. |
| General conversation reaches Gemma | BLOCKED | Existing configurable provider reused; authenticated connection shown. Exact loaded model override saved with User assistance. Live verification returned “Configuration saved, but model verification failed: URI could not reach a usable model.” Gemma remains loaded in LM Studio; no Active Brain change or Gemma Chat inference claimed. No silent provider substitution. |
| Camera Control UI reflects actual state | NOT IMPLEMENTED | No misleading recording controls or fabricated state added. |
| Existing functionality regression | IMPLEMENTED — AWAITING USER TEST | Available component suite and Windows build pass; full hardware regression and canonical camera loop cannot pass with stopped prerequisites. |

## Models, devices and timing

Wake uses installed Windows SAPI, not an LLM. Initial SAPI dictation failed
the User's real instruction trial and was replaced only at the post-wake
transcription seam. Downloaded public MIT
`Systran/faster-whisper-base.en`, revision
`3d3d5dee26484f91867d81cb899cfcf72b96be6c`, 147,769,510 bytes.
Local manifest records source, revision and SHA-256 values. Isolated
`.venv_voice` dependencies pin PyAV 18.1.0 for faster-whisper compatibility.
Transcription runs CPU INT8, four threads, local files only.

Microphone: Windows default Sennheiser Profile input. Camera 1 exposes an RTSP
microphone stream, but camera-microphone ingestion is NOT IMPLEMENTED. C210
speaker two-way audio is unavailable through the supported RTSP/ONVIF path;
no proprietary speaker integration was added. PC speech output is explicitly
`Speakers (High Definition Audio Device)`, confirmed audible by the User.

Observed live transcription receipts: model load 292–362 ms, transcription
485–500 ms, captured audio 3.8–7.6 s. Capture also waits approximately 1.4 s
of quiet to delimit the instruction. Latest synthetic office-order fixture:
exact text, model load 348 ms, transcription 800 ms, actual Python peak working
set 340,692,992 bytes. Synthetic timing is not real wake-to-answer latency.

Prior live existing-Qwen office draft displayed 11.3 s response time; a prior
general request took 46.5 s. These observations do not establish Gemma speed.
LM Studio Gemma `google/gemma-4-26b-a4b-qat` is already installed and loaded;
latest local inventory shows 15.63 GB, context 6,144, parallel 2. It was not
downloaded by this work. Ollama had no loaded model on this resumed check.

Earlier idle listener measurement: 158.9 MB RAM, 0.078125 CPU seconds over
5 seconds (about 1.56% of one core; 0.065% across 24 logical CPUs). GPU impact
was not measured reliably. Dual-camera resource testing did not run.

## Checks and bounded repairs

Earlier full Flutter suite: 218 passing; later navigation test passed separately.
Latest combined provider/voice event/navigation run: 12 passing. Earlier targeted
voice/harness run: 11 passing. Windows release build passed. Analyzer had only
the disclosed pre-existing provider `value` deprecation, no new errors.
Latest combined Python control-lease, muted-capture and Windows reader-lock
tests: 3 passing. Dependency `pip check` passed. Silent synthetic fixture
produced no command.

On resume, live status showed the listener had exited with “Cannot create a
file when that file already exists.” Status replacement collided with a UI
reader. Bounded local repair replaces atomically and retries only transient
I/O failures, at most ten times, 20 ms apart. A real Windows reader-lock
regression test then passed: held file for 120 ms, verified next wake event,
and parsed 100 subsequent publications. This is a known-root-cause local
fix, not a new architecture. The listener was restarted and manual speech
was confirmed audible by the User. No automatic restart loop was added.

The LM Studio model override was saved, but no selectable model appeared.
Source inspection established that endpoint/model saving omitted verification,
while encrypted-key saving already performed it. Bounded UI repair reuses
`verifyProvider` after successful configuration storage, preserving the
configuration when verification fails and showing the actual failure. Widget
regressions cover verification invocation and no false success on failure.
No key extraction, authentication bypass or backend architecture change.
The final 39.3-second Windows release build passed. Targeted Dart analysis
found only the same pre-existing `value` deprecation; `git diff --check` passed
after preserving LF endings. Running the repaired Save Overrides in the real
app failed model verification with the message recorded above. Stop the Gemma
integration attempt here; do not escalate into a protected legacy-backend
rewrite or silently select another model. Canonical Gemma latency is unknown.

## Exact acceptance steps

1. Leave URI open and signed in. Use the voice launcher when starting fresh;
   launching it while a non-voice URI instance is already open only focuses it.
2. Say “Oii URI” while minimized. Confirm URI restores Chat and audibly says
   “Yes Chetan.” Then speak an arbitrary instruction and pause.
3. Confirm exact instruction text, actual selected provider/model, a grounded
   response and measured latency. Repeat with several different instructions.
4. Test Mute, logged-out state and Windows lock: none should send commands.
   Closed-app wake remains unavailable.
5. Enable Camera Account/RTSP for Camera 2 and supply its credentials only
   through a secure camera configuration path. Do not paste passwords in Chat.
6. Free sufficient D: space before recording implementation resumes. Only then
   qualify independent recording controls, simulated cleanup, both streams and
   resource use. Do not delete live recordings as test data.

Final User acceptance and independent review are outstanding. Preserve this
partial work and stop affected camera/storage work until prerequisites change.
