# Live voice: independent audit record

Codex CLI (`codex exec`, model gpt-6-sol, reasoning medium, read-only sandbox) on a fresh
`core.autocrlf=false` clone (`C:\Users\cheta\Development\clv`). Codex wrote none of this code. Every
finding is a claim; each was checked against the code before repair, and each repair has a test that
fails on the code before the repair (shown by swapping the pre-repair files back in and re-running).

## Round 1 (candidate `3631c11`): REJECT

Thread `01a120b7-dbab-7c63-9dd6-8bbcb3542c35`.

| ID | Severity | Finding (Codex) | Checked | Repair | Test (fails before / passes after) |
|---|---|---|---|---|---|
| R1-1 | HIGH | Ctrl+Space released (or Esc) while the voice process was still starting: the microphone opened afterwards with the key up | confirmed: `pressTalk` awaited `ensureStarted` and then opened unconditionally; `cancel` had no capture id | press generation token; release/cancel during start-up abandons the press | `R1-1: a press released while the service starts never opens the microphone` |
| R1-2 | HIGH | Voice process death left the controller in listening/transcribing, so every later press was refused | confirmed: `_lost` reset only the presentation session | the controller watches service status; on loss it clears the capture, the reply tracking and the stage and shows a notice; the next press restarts the process | `R1-2: the service dying mid-capture resets the interaction; the next press restarts it` |
| R1-3 | MEDIUM | 4 s speech watchdog could fire in a gap between sentences ("Voice signal lost") | confirmed in principle (no event while waiting for the next sentence) | while an utterance is open and its next sentence is not ready, the process reports the silence it is playing (level 0 every 250 ms) | `test_r1_3_a_gap_between_sentences_reports_silence` |
| R1-4 | MEDIUM | a failed sentence reported the utterance ended but later sentences of it still played | confirmed | an utterance whose sentence fails drops its remaining sentences; forgotten after its last | `test_r1_4_a_failed_sentence_drops_the_rest_of_its_utterance` |
| R1-5 | MEDIUM | Settings said an unplugged chosen microphone falls back to the default; the process refused instead | confirmed | the process falls back to the Windows default and warns (`MIC_FALLBACK`, soft notice) | `test_r1_5_unplugged_choice_falls_back_to_the_default_with_a_warning`; `R1-5: a fallback microphone is a soft notice` |
| R1-6 | LOW | length bound ended capture without a notice | confirmed | `MAX_LENGTH` notice; stage moves to transcribing | `R1-6: the length bound ends the capture with a notice and transcribes` |
| R1-7 | LOW | latency recorded at queueing, not at first audio | confirmed | measured at `speak.started` (first audio of the reply) | `R1-7: latency is measured to the first reply audio, not to queueing` |

Correction recorded during repair: the first version of the R1-3 test also passed on the pre-repair
code (a clip's final empty block reports one zero level); it was tightened to require the repeated
silence reports only the repair produces.

## Round 2 (candidate `d6709df`): REJECT

Thread `01a12113-e8be-7620-979d-2e2ab6d9084c`. Codex confirmed R1-1, R1-3, R1-5, R1-6 repaired with
exercising tests; found R1-2 and R1-7 incomplete (R2-1, R2-2). No speech path to `decide`, `confirm`,
`abandon` or `selectBrain`; reducer, companion priority, `voice_engine.ps1` verbs and preference JSON unchanged.

| ID | Severity | Finding (Codex) | Checked | Repair | Test (fails before / passes after) |
|---|---|---|---|---|---|
| R2-1 | HIGH | service death while `send` awaited: the reply was still tracked against the dead service | confirmed | a service epoch, bumped on loss, is checked after the await | `R2-1: the service dying while the turn is sent leaves nothing to speak` |
| R2-2 | MEDIUM | `speak.started` emitted before the speakers opened, so first-audio latency could be recorded with no audio | confirmed | the stream is started first; the announcement follows; `with stream:` replaced by an explicit close (PortAudio refuses a second start) | `test_r2_2_and_r2_5_speaker_open_failure_announces_nothing_and_forgets_final` |
| R2-3 | MEDIUM | a hung engine bridge blocked shutdown (lock held across a blocking read) | confirmed | the bridge answer is bounded (20 s, then the bridge is ended); `close()` no longer takes the render lock | `test_r2_3_a_hung_engine_is_ended_not_waited_for` |
| R2-4 | MEDIUM | the 600-character cap did not bound a long first sentence or the fallback text | confirmed | both are clipped at a word boundary | `R2-4: the spoken cap also holds for a long first sentence` |
| R2-5 | LOW | a failed final piece left its id in `failed` forever | confirmed | only non-final failures are remembered | same test as R2-2 |

Also fixed between rounds from live evidence (not Codex findings): Stop button hold did nothing (live run 6),
recogniser hallucinations on room noise, native-import deadlock in the service (thread dump), unbounded decoding
(54 CPU-seconds worst case). Correction recorded: an earlier note attributed the slow model load to a Brain loading
from the same disk; the thread dump showed the import deadlock instead.

## History rewrite (privacy), 2026-10-09 20:25 IST

The owner reported that another person in the household was using the microphone during the afternoon. The
recogniser-comparison recordings (`docs/voice/live/evidence/stt/*.wav`, 48 files, room microphone) could therefore
contain household speech. Before anything was pushed, the unpushed branch was rewritten to remove those files from
every commit (`git filter-branch --index-filter`, range `b02ed4f..HEAD`). The recordings are kept only on the
owner's PC (`C:\Users\cheta\Development\uri-voice-evidence-private\stt\`); their SHA-256 sums are committed
(`evidence/stt/RECORDINGS_SHA256SUMS`) so the published WER tables stay tied to exact audio. Transcripts in the
evidence are the recogniser's output for the test sentences plus a few short fragments ("Yeah.", "Thank you.",
"All right."), nothing identifying.

Commit identities changed by the rewrite (the Codex rounds above reviewed the old identities; the code is identical):

| Before | After | Commit |
|---|---|---|
| `5e5d862` | `5e5d862` | live voice implementation (no WAVs; unchanged) |
| `838c22f` | `9bd96c8` | live-run findings (the commit that had added the WAVs) |
| `3631c11` | `2c59aca` | user vocabulary (Codex round 1 candidate) |
| `526f838` | `3bb4af3` | round 1 repairs |
| `1f17ad2` | `9053a73` | Stop while URI speaks |
| `b92070f` | `180482d` | noise guard, model state |
| `e737542` | `26759d2` | import deadlock, bounded decoding |
| `d6709df` | `79e8221` | manual mode (Codex round 2 candidate) |
| `f44f014` | `49daf8d` | round 2 repairs |
| `460de05` | `6e3a068` | manual sessions wait for the Brain; recording hashes |

## Round 3 (candidate `c230c0b`): REJECT

Thread `01a1212b-9ba2-7e40-a3c0-c7ee2f6c5785`. Codex confirmed the R2-1, R2-2, R2-3 and R2-5 repairs and that no
protected path (Core, supervisor, Operational Intelligence, scripts, model_lab, root `.gitignore`) changed.

| ID | Severity | Finding (Codex) | Checked | Repair | Test / evidence |
|---|---|---|---|---|---|
| R3-1 | HIGH | an output stream built but failing to start was never closed | confirmed | closed on the failure path | `test_r3_1_a_stream_that_fails_to_start_is_closed` (fails before) |
| R3-2 | HIGH | `close()` raced bridge creation; a bridge could be started after shutdown | confirmed | creation and shutdown share `bridge_lock` and a `closing` flag | `test_r3_2_no_engine_bridge_after_close_and_close_ends_a_busy_one` (fails before) |
| R3-3 | MEDIUM | the clip plus ellipsis could be 601 characters | confirmed | the ellipsis is inside the cap | `R3-3: clipped text never exceeds the cap` (fails before); R2-4 test tightened to `<= 40` |
| R3-4 | HIGH | report said run 7 "all passed"; D1 was misheard and D4 reached no card | confirmed (my overstatement) | report: D1 unmet, D4 incomplete | report section 3 |
| R3-5 | HIGH | AC-7 and AC-13 marked met/VERIFIED without the specified live evidence | confirmed | both "partly met", with what is NOT VERIFIED | report section 1 |
| R3-6 | MEDIUM | gate counts and some measurements had no committed files | confirmed | gate logs at `88e2dd7` in `evidence/gates/`; `service_startup.json`; two unsaved figures labelled as such | report sections 4, 6, 7 |
| R3-7 | MEDIUM | "speaking only while reply audio plays" stronger than the timeline | confirmed: the early `speaking` is OI's text-streaming state (source `URI`), 167 ms before audio in run 7 | claim qualified; limitation 11 | report AC-8 |
