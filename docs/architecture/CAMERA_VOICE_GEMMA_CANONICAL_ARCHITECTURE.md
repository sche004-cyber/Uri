# Camera, voice and Gemma bounded design — 2026-10-04

Stage 2 design, derived from [Stage 1](../research/CAMERA_VOICE_GEMMA_ROOT_CAUSE_AUDIT.md).
No frozen Core, Edge or harness code is changed. This is a directly assigned
extension, not a reopening of an earlier numbered milestone.

Camera/storage work stops at the observed prerequisites. No new recorder,
cleanup or camera capability is enabled. Actual Camera 2 path and credentials
must be configured by its owner; camera mutations cannot claim success.

Voice is an opt-in Windows desktop input adapter. Reuse System.Speech offline
recognition and synthesis. Restricted wake grammar precedes unrestricted
dictation. Suspend recognition while speaking "Yes Chetan.". Use the Windows
default recording device (select it in Windows Sound settings), a bounded
command timeout, a local mutex, current-user ACLs and ephemeral IPC. No large
model or GPU used for recognition. Do not cross Windows lock/session boundaries.

Wake events restore/focus the existing window and select the existing Chat
workspace. A fresh transcript goes to existing authenticated AppState.ask();
capability discovery, reasoning, authorization, approvals, execution, result
feedback and grounded response remain owned by the existing URI architecture.
Never execute transcript text as shell code or fabricate camera handlers.
Unconfigured cameras remain unavailable capabilities. Voice cannot approve
pending actions or change the selected Brain/harness.

IPC carries only fresh events in a current-user directory. Reject events while
logged out or while a turn is busy; do not replay them after login. Mute prevents
further recognition. Show actual adapter status, failure and command-listening
state. An explicit manual listening test is distinguished from a spoken wake.
The adapter is owned by the running app; closed-app wake is not implemented in
this bounded slice. Investigate an independent listener only after the launch
and session path is qualified, without adding duplicate URI instances.

Gemma reuses the configurable OpenAI-compatible provider and existing provider
key UI. Keep auth on. No hardcoded default, replacement harness, implicit
fallback or inferred key. Successful provider inference and canonical UI
inference are separate acceptance checks; currently credential-blocked.
