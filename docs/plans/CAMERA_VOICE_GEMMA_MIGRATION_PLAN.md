# Camera, voice and Gemma bounded migration — 2026-10-04

Stage 3 references [evidence](../research/CAMERA_VOICE_GEMMA_ROOT_CAUSE_AUDIT.md)
and [design](../architecture/CAMERA_VOICE_GEMMA_CANONICAL_ARCHITECTURE.md).
Direct User implementation instruction supplies task authority. No independent
plan audit, milestone VERIFIED, commit or release is claimed.

1. Preserve unrelated changes and all recordings. Stop storage/recording work
   until a 700 GB allocation plus configurable safety margin is feasible and
   ownership is established. Do not silently reduce caps.
2. Reuse installed Windows speech; add opt-in desktop adapter and minimal
   existing Chat navigation hook. Preserve keyboard conversation, login,
   approvals and harness choice. No Core/Edge edits.
3. Use existing Chat pattern from design_library/chat/README.md: standalone
   workspace, inline status/control strip; no new conversation architecture.
4. Validate freshness/auth/busy gates with component tests; build Windows
   application; test actual microphone initialization and synthesis separately.
   Speech performance awaits real human wake and second-instruction trials.
5. Launch through existing one-click launcher if operational. Do not repair
   protected legacy deployment or change security policy to force success.
6. Configure Gemma via existing provider UI once the user supplies a valid
   LM Studio token securely. Test office-order drafting via canonical Chat.

Rollback: omit voice enablement; new voice files are unused. Existing app and
provider behavior remain default. Stop the owned listener before rollback.
Acceptance: muted/timeout/error states truthful; no old transcript replay,
no logged-out/busy dispatch, wake focuses existing Chat, real spoken next
instruction passes through canonical ask and its ordinary approval boundary.
Unit success does not satisfy hardware or canonical-loop acceptance.
