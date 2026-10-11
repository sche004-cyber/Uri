---
name: uri-development-lifecycle
description: Pointer for non-Claude agents. URI development milestones are driven by the uri-development-lifecycle skill; the canonical text is .claude/skills/uri-development-lifecycle/SKILL.md and the engine is scripts/dev_workflow/lifecycle.py.
---

Read `.claude/skills/uri-development-lifecycle/SKILL.md`. Codex may act as reviewer (`"provider": "codex_cli"`) or
implementer when installed; it is never required. Not a runtime skill: never add it to
`uri_workspace/skill_registry.json`.
