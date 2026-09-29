"""M39 Office demonstrator vertical (PROVISIONAL, NOT FROZEN).

A composition layer only: this package imports `uri_v1.memory`, `uri_v1.edge`,
`uri_v1.execution`, and read-only from frozen `uri_v1.turn` /
`uri_v1.reference_clarification` / `uri_v1.results` / `uri_v1.evaluation`.
Never `uri_core`, `uri_ui`, or a network client library. No model/LLM call
anywhere in this package's own logic (deterministic parsing only).

See docs/plans/M39_OFFICE_DEMONSTRATOR_PLAN.md for the governing plan.
"""
