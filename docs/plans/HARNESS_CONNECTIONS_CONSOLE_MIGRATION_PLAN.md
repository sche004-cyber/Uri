# Harness, Connections and Console migration
Stage 3, 2026-10-03. Basis: Stage 1 reconnaissance and Stage 2 architecture of the same prefix.

1. Preserve assigned checkout and create isolated worktree at 62d564c. Copy only named provisional dependencies, with an explicit provenance manifest.
2. Check native auth read-only; retain Claude selection unless User explicitly selects Codex. Do not retry quota automatically.
3. Reuse harness controller state above navigation. Add inherited UI access, replace global footer with Workspace-only task view. Add Connections Models/Plugins/Harnesses tabs preserving existing model and OAuth flows. Actual capability catalogue stays backend-owned.
4. Reuse DesktopHarnessTest as the provisional harness console, as clarified by the User amendment. Add read-only inspection from existing APIs; keep broader Console recovery BLOCKED, without a competing replacement. Do not consult or alter experience levels or work modes.
5. Run focused controller/auth/M37/M38 tests, Flutter regressions, analysis and Windows build. Use the actual UriApp Flutter-driver entry solely for desktop evidence, with native keyboard default. Record which scenarios are blocked separately.
6. Report implementation, unit checks, desktop checks, provider checks and audit/release separately. No commit/push/freeze/installed production replacement.

Rollback: use unchanged normal installed app. Remove candidate UI access wiring to return to copied provisional seam. No production account migration or original-file write-back.

General task acceptance remains a dependency gate until capsule/acceptance boundaries and executable verification containment are reviewed. The User explicitly selected Codex and authorized the named frozen-extension proposal in this session. Native containment is still unavailable in both probed Windows modes; approval does not remove qualification or independent review. No frozen source was changed pending that prerequisite.
