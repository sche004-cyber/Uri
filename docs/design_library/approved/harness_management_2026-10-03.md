# Harness management structure

Direct User assignment: add harness management to the existing desktop, preserve
Companion/Workspace/Intelligence and separate Brain configuration.
Adapt `providers/README.md` provider-list/status pattern (Tabler
`preview/pages/settings.astro`, shadcn blocks select/badge references): one row
per harness, live status plus explicit qualification and blocked reason,
details below, refresh action. Accessible from the existing opt-in application
panel. Use current theme tokens; no new navigation system or fabricated metrics.
Backend: `desktop_harness/registry.py`, `controller.py`, authenticated routes.
