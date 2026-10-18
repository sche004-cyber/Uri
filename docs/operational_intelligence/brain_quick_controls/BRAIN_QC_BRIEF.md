# BRAIN QUICK CONTROLS - session brief (BRAIN-QC-20261018)

Owner-approved milestone (2026-10-18). Methodology: ODRD (Outcome-Driven Research & Discovery): prioritize verified
outcomes, reuse proven work, investigate root causes, minimize complexity, independently validate.

Owner decisions (2026-10-18, quoted): "Use milestone/runtime-profiles-integ-20261017 (f3d5eb29) as the development
base instead of 348677b7. Reuse its existing Context/Vision switching, worker preservation, and conversation
continuity. Investigate the existing implementation before modifying it. Avoid duplicate development. Maintain an
isolated worktree and independently qualify the exact candidate. This approval does NOT authorize integration of
runtime-profiles or Quick Controls into canonical."

Context: URI repo (Flutter uri_ui + Python backend: uri_operational_intelligence, scripts/ws_brain_host.py), Windows 11
owner PC, one 16 GB AMD GPU shared through a machine-wide lease. Canonical is 348677b7; runtime-profiles candidate
f3d5eb29 (unintegrated) adds resource-aware Runtime v1 profiles. Owner wants autonomous research/review/repair without
owner participation in routine reviews, and separate approval before any integration/freeze/deploy. Follow CLAUDE.md
Verification-First and Evidence Integrity rules. This file is untracked; move it under docs/ if you keep it.

0. Worktree: THIS folder `D:\uri-dev\uri-brain-quick-controls`, branch `milestone/brain-quick-controls-20261018`,
   created at f3d5eb29 (verify `git rev-parse HEAD`). Do not modify branch milestone/runtime-profiles-integ-20261017
   or worktree D:\uri-dev\uri-runtime-profiles-integ (owned by session "URI RUNTIME - VRAM OPTIMIZATION",
   local_717ef8ce). If that branch gains new commits, coordinate before rebasing.
1. Requirements: search prior plans/docs for quick controls / thinking / vision / context; read
   docs/operational_intelligence/RUNTIME_PROFILES_UI_CONTRACT.md (Thinking = per turn via depth; Vision and Context =
   reload with fit check). Qualified profiles so far: 64K main-only and 32K+vision; 64K+vision UNQUALIFIED (crash and
   demotion findings) - must not be offered as available. Write acceptance criteria first.
2. Investigate the runtime-profiles implementation (ws_brain_host.py --profile ctx,vision,mtp;
   control/oi/brain_profile.json ProfileFollower; runtime_profile_selection.py; brain_health profile naming; evidence
   sw4/sw5) before designing. Reuse; do not duplicate.
3. Implement intuitive Thinking, Vision and Context controls in the UI V2 surface: accurate capability/readiness
   reporting (never show a mode active before the runtime confirms; unqualified combos disabled with reason), safe
   resource transitions (fit check, no VRAM oversubscription), preservation of session context, conversation history
   and worker state across switches (prove it live).
4. Frozen components unchanged (Runtime v1 frozen config; UI V2 freeze 7893aaed only additive minimal edits); prove
   with diffs and scripts/ws_frozen_check.py.
5. Overlap: parallel Ember V2.1 milestone (branch milestone/ember-v21-integ-20261018 @6bdaf86e, worktree
   D:\uri-dev\uri-ember-v21-integ, run by the owner's main session) touches uri_ui companion files, oi_sources.dart,
   companion_sources.dart, living_app.dart, companion_gallery.dart, pubspec.yaml (Ember assets). Keep shared-file
   edits minimal; list your touched UI files in your report.
6. GPU: serialize via uri_operational_intelligence.gpu_lease (status/census/run). Never stop another holder. The Ember
   live run uses the lease from about 10:05 IST 2026-10-18 for roughly an hour. Brain tests only with
   Qwen3.6-35B-A3B MoE.
7. Review: Codex when available (quota blocked until 2026-10-22 per prior evidence; one probe, no retries), else
   evidence-qualified independent subagent review (read-only, exact commit). Repair and re-review routine findings
   autonomously. Subagent acceptance is not owner approval.
8. Qualification: pytest for touched Python, flutter analyze, full flutter test, Windows release build, live switching
   (Thinking per turn; Vision on/off; Context 32K<->64K) with conversation continuity, readiness truthfulness, UX
   screenshots, performance (tok/s, VRAM, switch time), regressions.
9. Evidence-backed qualification receipt in-repo (only COMPLETED_WITH_RESULT counts). Commit locally.

Do NOT integrate, freeze, tag accepted/*, push, deploy, or change frozen paths. Escalate only unresolved material
risks, policy exceptions, owner-authority decisions, integration authorization. Report final readiness with exact
commits.
