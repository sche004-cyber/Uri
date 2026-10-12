"""URI Phase 2A: Durable Task Supervisor.

A clean extension around the frozen Phase-1 Core. Nothing in `uri_core` imports this package.
The ledger (SQLite) is the only authority over task state; executors are workers and evidence
sources. Governing invariant: durable intent before effect, durable evidence after effect,
and uncertainty is represented, never guessed.
"""
SCHEMA_VERSION = 1
