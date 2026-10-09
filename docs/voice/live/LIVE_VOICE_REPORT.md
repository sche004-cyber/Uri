# Live voice, Brain coexistence and companion activation: phase report

Date: 2026-10-09. Branch `phase/live-voice` (worktree `C:\Users\cheta\Development\uri-live-voice`), based on the
canonical tip `b02ed4f`. Plan and acceptance criteria: `LIVE_VOICE_PLAN.md` (written first). Independent review:
`LIVE_VOICE_AUDIT.md`. Not integrated yet (section 9). No deployment, launcher change or cutover.

Status words: IMPLEMENTED (code exists and is tested), VERIFIED (shown on the real system with the real
microphone, worker and Brain), ACCEPTED (independent review accepted), NOT VERIFIED (missing evidence, stated why).

## 0. Summary

URI now listens and speaks. Holding the microphone button (or Ctrl+Space) captures the real microphone, a local
recogniser on the CPU produces live partial and final transcripts, the final transcript goes to URI exactly as typed
text does (local commands first, then Core and Operational Intelligence, then the Brain), and the answer is spoken
sentence by sentence through the user's chosen Windows voice while the selected companion shows listening,
transcribing/thinking and speaking from the real events. This ran end to end on this PC with the Sennheiser
microphone, the integrated worker and Runtime v1 (section 3).

What is not done: drafting by voice waits for the Text Intelligence draft desk to reach canonical (it is not in this
build; voice dictation is kept in the composer with a notice); the talker in every automated run was a Windows voice
played through the speakers, because the owner's own-voice session could not take place (the owner is away for some
weeks); the start-order problem with Runtime v1 is explained and measured but not solved (it belongs to the Runtime
v1 memory budget, section 6).

## 1. Acceptance criteria and results

| ID | Criterion (plan section 3) | Result | State | Evidence |
|---|---|---|---|---|
| AC-1 | Microphone list, choice, default, specific denied/missing messages | met | IMPLEMENTED, VERIFIED (list, default, real device); denied path tested only | `voice_input_settings.dart`; tests `MIC_DENIED`, `MIC_FALLBACK`; live status `inputs: [Microphone (Sennheiser Profile)]`, privacy `allowed` |
| AC-2 | Push-to-talk on the real microphone; live level; partials; final after release | met | VERIFIED | e2e runs 3, 6, 7: `listen.level` 1 267 user blocks (run 3), partials ("...of Sikkim and what is it known?") on screen (`e2e_run7_uifirst/B1_listening.png`) |
| AC-3 | WER measured on real-microphone audio; base.en accepted at WER <= 10 % | met (strict 7.26 % after the fixes, 3.94 % format-normalised) | VERIFIED for a synthetic talker; NOT VERIFIED for a human talker | section 2 |
| AC-4 | Latency, CPU, RSS, VRAM | measured | VERIFIED | section 4 |
| AC-5 | Cancel, failure, empty speech, length bound end cleanly; no orphan process | met | VERIFIED (cancel, empty) / tested (failure, length bound, process death) | runs 3, 6, 7 (D2, D3); 26 service tests, 37 controller tests; no orphan worker or voice process after the app was killed (checked 20:22) |
| AC-6 | Conversation end to end through Core/OI/Brain, spoken | met | VERIFIED | run 7 B1: "What is the capital of Sikkim and what is it known for?" -> Brain answer -> spoken; first reply audio 738 ms after the final transcript |
| AC-7 | Speech never authorises | met | IMPLEMENTED, tested; VERIFIED in part | no code path from speech to `decide`/`confirm`/`abandon`/`selectBrain` (Codex r2 confirmed); live: spoken "Yes, approve it." became an ordinary turn and Core refused ("I cannot safely act on that request"). The approval card itself was not reached live: Core refused the spoken "Remember that..." request ("I could not build this request from your own words"), so the spoken pointer to the card is test-verified only |
| AC-8 | Companion states follow real activity | met | VERIFIED | event timelines: listening at capture, "You are speaking" on onset, thinking "Transcribing" after release, thinking during the turn, speaking only while reply audio plays, idle after; screenshots |
| AC-9 | Interruption within 300 ms; no capture during playback | met | VERIFIED | run 7 B2: tap on Stop -> `speak.ended interrupted` 4 ms after the press; the process refuses speech while the microphone is open (tested) |
| AC-10 | Voice, volume, rate, pitch, speak-replies, microphone, mode | met | IMPLEMENTED, tested; voice/rate/pitch/volume reach the engine (test) | `live_voice_test.dart` "speak sends the user voice..." |
| AC-11 | Minimised window | met | VERIFIED | run 7 B3: reply kept playing to the end while minimised; frame clock suspended (`frame_clock_hidden: true`) |
| AC-12 | Drafting mode working or shown unavailable with the reason | shown unavailable | NOT IMPLEMENTED (by design until TI lands) | run 3 R1: notice `DRAFTING_UNAVAILABLE`, words kept in the composer |
| AC-13 | Brain coexistence measured; voice adds no GPU memory; Adaptive once under a live Brain | met | VERIFIED | section 6 |
| AC-14 | Regression gates | met on the phase branch | VERIFIED | section 7 |
| AC-15 | Independent Codex review | rounds 1-2 REJECT, repaired; round 3 pending at the time of writing | in progress | `LIVE_VOICE_AUDIT.md` |
| AC-16 | Integration with receipt, fast-forward, fresh clone | not yet | pending | section 9 |

## 2. Recognition engine: research and selection

Candidates. Researched: faster-whisper (CTranslate2), whisper.cpp, Moonshine, Vosk, Windows System.Speech dictation,
Windows.Media.SpeechRecognition. Published comparisons are vendor or aggregator numbers on different test sets, so
they were not used for the decision. Nothing new was downloaded: faster-whisper base.en (MIT, revision `3d3d5de`,
145 MB, hash-pinned manifest) and its runtime were already on this PC from the owner-run 2026-10-04 repair, which had
chosen it after System.Speech dictation failed the owner's own trial.

Measured here (`rnd/voice/live/stt_compare.py`, `evidence/stt/stt_compare.json`): 24 office and conversation
sentences, two Windows voices, played through the speakers and captured by the real microphone; 45 usable recordings
(3 excluded by a stated rule: the speaker level fell about 15x during the last three). The recordings stay on the
owner's PC (privacy, `LIVE_VOICE_AUDIT.md`); their hashes are committed.

| Engine | Strict WER | Format-normalised WER | Exact sentences | CPU time per ~5 s clip |
|---|---|---|---|---|
| faster-whisper base.en int8, beam 5 + VAD (URI final pass, before name bias) | 7.47 % | 4.15 % | 28 / 45 | 0.6 s wall |
| same, beam 1 (URI partial pass) | 6.85 % | 3.53 % | 28 / 45 | 0.6 s wall |
| System.Speech dictation (12 of the recordings) | 38.19 % | 31.94 % | 1 / 12 | — |
| Windows.Media.SpeechRecognition | not measurable on recordings (microphone input only) | | | |
| whisper.cpp, Moonshine, Vosk, larger Whisper models | not installed (no download in this phase) | | | |

Format normalisation (stated in the script): "October 15" = "15 October", "30th" = "30", "5,000 rupees" = "Rs 5,000",
"programme" = "program". Remaining errors were almost all local names (Gangtok, Siliguri, Tshering Bhutia, Dussehra).

Decision: base.en on the CPU. It meets the plan's bar (WER <= 10 %), is already pinned, uses no GPU, and its
remaining errors respond to vocabulary bias:

| Bias (`vocab_probe.json`) | Strict WER | Format-normalised |
|---|---|---|
| none | 7.47 % | 4.15 % |
| assistant name "URI" (always on) | 7.26 % | 3.94 % |
| name + a user vocabulary of the local names | 4.36 % | 1.04 % (optimistic: the vocabulary came from the test sentences) |

The vocabulary is a setting ("Words URI should recognise"). The name bias raised "URI" recognition from 0/6 to 4/6
(`evidence/name_bias`), but the short command "URI, dashboard." was still misheard in 1 of 3 live runs.

Later changes and their measured effect on the same 45 recordings: the noise guard dropped 0 speech segments; bounded
decoding left WER unchanged (7.26 % / 3.94 %) while cutting the worst noise decode from 54 to 2.3 CPU-seconds.

## 3. Live demonstration (real app, real microphone, real worker; talker = Windows voice through the speakers)

Runs (all events, screenshots and per-process GPU samples under `evidence/`):

| Run | Order | Result | Notes |
|---|---|---|---|
| 1 | Brain stopped | failed at D1 | "URI" heard as "You are I" -> name bias added |
| 2 | Brain stopped | failed at D2 | two composers mounted in a mode change -> keyboard handled by the newest only |
| 3 | Brain stopped | passed | found: 1.5 s of room noise transcribed "." and sent -> fixed |
| 4 | Brain host refused (GPU contention) | passed without Brain | led to the owner's override decision (section 6) |
| 5 | Brain first | failed at start-up (composer did not appear in 90 s) | cause not established; run 6 with the same setup started normally |
| 6 | Brain first | failed at B2 | a held Stop did nothing -> fixed; also the measured VRAM demotion (section 6) |
| 7 | UI first | **all passed** | D1-D4, B1-B3 |

Run 7 transcript of what URI did: "URI Dashboard" -> missed in this run ("You are I dashboard"), sent as a turn;
silence -> "No speech was heard", nothing sent; Esc during "Send the monthly report to the director" -> microphone
closed, nothing sent; "Remember that the laboratory is closed on Friday afternoon." -> Core declined; "Yes, approve
it." -> an ordinary turn, Core declined, nothing approved; "What is the capital of Sikkim and what is it known for?"
-> answered by the Brain (136.8 tok/s) and spoken; "Tell me five ways to reduce paper use in a government office." ->
spoken, then silenced by a tap on Stop in 4 ms; "Give me a two-sentence tip for writing a clear office note." ->
spoken while the window was minimised.

Own-voice session: prepared (manual mode of the live driver) and started at 20:10, but the owner was away; NOT VERIFIED
with a human talker.

## 4. Latency and resources

| Measure | Value | Source |
|---|---|---|
| Release -> final transcript | 463-957 ms (median about 550 ms) for 4-6 s utterances; one 1 514 ms | runs 3, 6, 7 |
| Recogniser time for the final pass | 455-757 ms | same |
| Final transcript -> first reply audio | 738 ms (healthy Brain), 964 ms (demoted Brain) | run 7 B1, run 6 B1 |
| Sentence render (warm engine bridge) | 280-350 ms; first PowerShell start about 1.2 s (done at service start) | `serve` test |
| Model load | about 0.5 s (after the deadlock fix, 5 of 5 cold starts) | thread dump + 5 runs |
| Voice process memory | 159 MB idle with the model loaded; about 195 MB after use; engine bridge 78-93 MB | `voice_footprint.json` |
| Voice process CPU | idle 0.0 s per 10 s; open microphone without speech 0.09 s per 10 s; speech: partial re-decodes of at most the last 6 s plus the final pass | `idle.py` measurement; footprint |
| Voice process GPU | none: CPU int8; never present in the per-process GPU samples (threshold 32 MiB) | `coexist/gpu_residency.csv` |

## 5. Speech output and voice packs

URI's replies use the existing catalogue (System.Speech: Microsoft David/Zira Desktop; OneCore: David, Zira, Mark) with
the measured rate, pitch and volume controls. Each sentence is rendered by the persistent `voice_engine.ps1 serve`
bridge and played by the voice process, which measures the level of the audio it plays (the speaking waveform follows
that). Markdown is not read aloud (code, tables, link targets, emphasis marks); replies are capped at 600 characters
at a sentence or word boundary, then "The rest of the answer is on screen."

Limits: no word-by-word timing (the transcript of the spoken sentence is shown whole); no speaking styles (none of
the installed voices offers them; still shown unavailable); one output device (the Windows default).

Researched, not installed: Windows 11 Narrator natural voices (usable from SAPI only through a third-party adapter
that its author calls a hack and that can break with Windows updates); Piper (offline neural, CPU, tens to hundreds of
MB per voice; Windows packaging needs checking); Kokoro-82M ONNX (about 86-330 MB, slow on CPU per its wrappers).
Recommendation for an owner decision: a Piper voice is the most plausible offline upgrade; it needs a download and a
measured CPU real-time factor next to the Brain first.

## 6. Brain and companion coexistence

All runs used the machine-wide GPU lease through the Brain host; another thread's lease was never pre-empted (A2UI's
and TI's regression chains were waited for; the lease was handed to TI at 19:39:56 and returned at 20:04:28).
Starting Runtime v1 with a URI window, Chrome and the desktop open was refused by the host's fit check ("needs 15.3 GB,
14.2 GB free"); the owner authorised `--override-contention` for this phase's tests only and closed Chrome.

| Order | Brain at load | Decode alone / with URI open / after URI closed | Per-process residency of llama-server |
|---|---|---|---|
| Brain first (run 5) | 160 tok/s | 159-161 / 156-157 / — | 15 556 MiB device-local, 1 121 MiB non-local, unchanged when URI opened (adapter peak 16 164 of 16 368 MiB) |
| Brain first (run 6) | (same instance) | — / 70.6 in a voice turn / **94** | at 19:26:24, 7 s after the URI window opened (URI 80 -> 329 MiB, adapter 16 311 MiB), device-local fell to 14 865 MiB and non-local rose to 1 811 MiB: **+678 MiB demoted to system memory**, persisting after URI closed |
| UI first (run 7) | 153.9 tok/s | — / 136.8 in a voice turn, 144-148 under 85 s of continuous generation with the companion at 144 FPS / 155-160 | non-local 1 730 MiB from the start; no change during use |
| UI first (owner session) | 156.6, then 158 tok/s | — | same placement |

What this distinguishes:
- **VRAM oversubscription and demotion: confirmed and measured** (not inferred, as in the companion phase): the
  Brain-first slowdown happens when the adapter fills and the driver moves part of the Brain to system memory; it
  persists for the server's life. It depends on margin, not only on order: run 5 did not demote, run 6 did.
- UI first: the driver places about 1.7 GB in system memory at load, but in the placement it chooses the Brain stays
  fast (154-160 tok/s) — consistent with the companion phase's finding, now with residency data.
- CPU offloading of layers: not seen (the server's argv and placement are unchanged; non-local growth is the driver's
  demotion).
- Model reload: none during any run (one server process per run, constant pid).
- Flutter rendering cost: about 9 % of decode speed while the companion animates at 144 FPS (160 -> 145 tok/s).
- Other threads: Chrome (0.6 GB) alone was enough to fail the fit check; other sessions' GPU work was serialised by
  the lease.
- Voice: no GPU memory, so voice cannot cause the demotion.

Interim policy recommendation (owner decision): start the URI window before the Brain, as the working-system launcher
already does, and keep the host's fit check. A durable fix belongs to Runtime v1's memory budget (the Adaptive Runtime
R1 options: vision on CPU / no MTP, smaller suballocation blocks); this phase changed nothing in Runtime v1.

Adaptive frame rate (one focused check, `evidence/adaptive`): Lunar, Adaptive, 148 s, with the Brain generating
continuously for 85 s: 144.7 FPS, raster p99 2.4 ms, 1 frame over 16.7 ms; the cap never stepped down because the
healthy Brain did not stress the renderer. The back-off logic therefore remains verified by its tests, not observed live.

## 7. Tests and gates (phase branch)

| Gate | Result |
|---|---|
| `flutter test` (all of `uri_ui`) | 468 passed, 3 skipped after the round 2 repairs (canonical b02ed4f: 431 passed, 3 skipped) |
| `test/living/live_voice_test.dart` | 37 passed |
| `tool/voice/test_uri_voice_service.py` (voice runtime) | 26 passed |
| `flutter analyze` (lib, test/living, integration_test) | only one pre-existing info outside this phase (`providers_screen.dart:730`) |
| Live end-to-end (opt-in `integration_test/live_voice_e2e_test.dart`) | run 7 passed (section 3) |
| Python chain / frozen checks | no Python file of the runtime changed (only `uri_ui/`, `docs/`, `rnd/`); run at integration |

Every repair from review or live evidence has a test that fails on the code before the repair (shown by swapping the
old file back in).

## 8. Remaining limitations

1. No own-voice (human) verification; all automated talkers were synthetic voices through the speakers.
2. Drafting by voice waits for the TI draft desk on canonical.
3. Short commands with the assistant's name are sometimes misheard ("URI, dashboard." 2 of 3 live runs right).
4. A turn that ended in error leaves OI's companion state at `error`, which outranks `listening` (accepted priority
   contract); while it lasts, the orb does not show listening (the waveform and red button still do). Owner decision.
5. Start order with Runtime v1 (section 6) is a Runtime v1 memory-budget problem; not solved here.
6. Recogniser languages: English only (the architecture takes another model or `language` per request).
7. Noise guard thresholds come from 36 noise clips and 45 synthetic-voice recordings; a real human voice may score
   differently (the safe direction: words dropped, "No speech was heard").
8. Run 5's start-up failure (composer not shown in 90 s) is unexplained.
9. Microphone denial was tested, not produced on the real system (changing the Windows privacy switch is the owner's).

## 9. Integration

Pending at the time of writing: Codex round 3, then merge with the current canonical tip (now including A2UI; TI is
about to land), combined gates, integration review, receipt, fast-forward and fresh-clone check.
