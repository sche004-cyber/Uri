---
name: uri-development-lifecycle
description: Pointer for non-Claude agents. URI development milestones are driven by the uri-development-lifecycle skill; the canonical text is .claude/skills/uri-development-lifecycle/SKILL.md and the engine is scripts/dev_workflow/lifecycle.py.
---

Read `.claude/skills/uri-development-lifecycle/SKILL.md`. Codex is the preferred reviewer (`"provider": "codex_cli"`,
owner directive 2026-10-15); when it is unavailable a separate Claude process reviews instead. Codex may also act as
implementer. User-facing work also needs the live Windows UI qualification described there. Not a runtime skill: never add it to
`uri_workspace/skill_registry.json`.
