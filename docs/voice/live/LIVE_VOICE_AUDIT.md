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
