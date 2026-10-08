# Voice instruction transcription repair — 2026-10-04

Additive four-stage evidence/design/migration amendment; original evidence is
preserved. User's real trial: "It can hear Oii URI but cannot understand my
instructions". The visible live Chat also showed an unintended "Will you eat"
transcript answered by the existing qwen3.5:9b Brain. SAPI wake works in that
trial; SAPI dictation fails user acceptance. It is not VERIFIED.

Design: keep SAPI's small wake grammar and installed speech synthesis. Replace
only post-wake dictation with on-demand CPU INT8 faster-whisper base.en. Use
sounddevice's selected/default microphone; audio remains in memory, not saved.
Bound onset/end-of-speech and total recording time. Recheck mute/session/lock
controls during capture and after transcription. Never auto-fallback to failed
SAPI dictation. Main Brain/GPU/harness/canonical ask remain unchanged.

Migration: isolated `.venv_voice` dependencies, pinned model source/revision in
the model manifest, local-only cached inference, bounded child process, private
receipt file containing text/metrics, consume then remove receipt. Test silent
audio produces no command and cancellation closes microphone; then retry a
real user instruction. If the targeted alternative remains unreliable, STOP
voice command implementation and retain working wake input without claiming
instruction acceptance. Rollback uses keyboard Chat; do not restore failed
dictation silently. No broader backend repair authorized by this amendment.

Sources: [SYSTRAN faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[base.en model, MIT](https://huggingface.co/Systran/faster-whisper-base.en).
CPU INT8 is supported by the upstream runtime. Actual resource cost must be
measured on this PC; no upstream benchmark is substituted for local evidence.
