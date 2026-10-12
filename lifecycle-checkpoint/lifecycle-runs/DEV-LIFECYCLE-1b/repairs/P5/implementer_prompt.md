You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit dff1ea78527a639ee6b13f47b1f89a2f13e7b865.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on dff1ea78527a639ee6b13f47b1f89a2f13e7b865 and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: scripts/dev_workflow/lifecycle*.py, tests/dev_workflow/**, docs/dev_workflow/**, .claude/skills/**, .agents/skills/**, CLAUDE.md, AGENTS.md, SKILL.md.
Do not commit or push; the driver commits after checking your change. If a finding cannot be fixed within these
limits, do not work around it: report it as not repaired with the reason.

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)

Findings (from the reviewer, verbatim):
[
 {
  "id": "R6-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Reviewer executable identity is not anchored: any 'claude' earlier on PATH (e.g. planted in ~/.local/bin by an implementer or gate test) counts as the installed CLI and its scripted ACCEPT makes a real milestone VERIFIED",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py:86",
   "scripts/dev_workflow/lifecycle_providers.py:120",
   "scripts/dev_workflow/lifecycle_providers.py:125",
   "scripts/dev_workflow/lifecycle.py:312",
   "scripts/dev_workflow/lifecycle.py:404",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:33"
  ],
  "evidence": "binary_is_default compares realpath(which(argv[0])) with realpath(which('claude')), and argv[0] is which('claude') itself, so it is True for whatever 'claude' is first on PATH. binary_sha256 is recorded but never compared with a PLAN-anchored value, and control_state/control_drift cover only git files. Here PATH has /root/.local/bin before /opt/node22/bin. Probe 1 (/tmp/uri_review_R6/probe1): milestone W9-REAL-MILESTONE, reviewer {provider: claude_cli}, a fake 'claude' script printing an ACCEPT JSON first on PATH -> stage VERIFIED, round independent=True ('separate process, fresh session, clean checkout, integrity verified'), evidence_ok (True, []), verify() []. Probe 2 (/tmp/uri_review_R6/probe2): the real-position reviewer REJECTs R1; the command implementer repairs and copies an always-ACCEPT 'claude' into the earlier PATH dir; the driver commits the repair; R2 runs the planted binary (binary_realpath and binary_sha256 differ from R1, binary_is_default still True) -> ACCEPT -> VERIFIED, no TAMPER block, verify() []. The docs say the executable 'must be the installed claude/codex CLI (path and SHA-256 recorded)'; recording is not enforcement.",
  "suggested_fix": "Resolve the reviewer executable once at PLAN to an absolute realpath plus SHA-256 (from a configured, owner-acknowledged path or a trusted install dir, not the first match on PATH) and bind it in the PLAN control state. Launch that absolute path and before every round refuse the review (TAMPER) if the realpath or hash differs from the anchor. Treat a changed CLI as a control-state change that needs owner unblock. Add a regression test with a PATH-planted fake."
 },
 {
  "id": "R6-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "The independent reviewer starts in the candidate checkout and loads the candidate's CLAUDE.md, .claude settings and skills as authoritative project instructions, so implementer-authored text reaches the reviewer outside the driver-built prompt",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py:82",
   "scripts/dev_workflow/lifecycle_providers.py:135",
   "scripts/dev_workflow/lifecycle.py:863",
   "docs/dev_workflow/LIFECYCLE_PLAN_AND_ACCEPTANCE.md:30"
  ],
  "evidence": "build_argv runs 'claude -p' with cwd = the audit worktree at the candidate SHA and passes nothing that limits project setting or memory sources. In this R6 review the candidate's CLAUDE.md (changed in the review range) was injected into the reviewer's system context as project instructions that 'OVERRIDE any default behavior and you MUST follow them exactly', and the candidate's .claude/skills/uri-development-lifecycle was offered to the reviewer as a skill. An implementer repair (permitted_paths '**') can edit CLAUDE.md or add .claude/settings.json hooks such as Stop or SessionStart to steer later reviewers, for example by declaring a defect an 'accepted documented limitation', which the prompt itself makes non-blocking. Plan decision 3 says the reviewer prompt is built only from the config and earlier findings.",
  "suggested_fix": "Start the reviewer with project and local setting sources disabled (e.g. --setting-sources user, or an empty settings override) and without auto-loaded project memory where the CLI allows it. Otherwise refuse or flag a candidate that changes CLAUDE.md or .claude/ unless the owner authorises it (add them to protected_paths for repairs). State the residual channel in the plan."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
