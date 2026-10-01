"""Dynamic planning, slice 1 (PROVISIONAL, NOT FROZEN, offline only).

An untrusted semantic proposal is compiled deterministically against a hashed
capability snapshot, bound to hash-checked sources, run node by node in a
bounded workspace, and completed only by the existing URI verifier.

Plans: docs/architecture/DYNAMIC_PLANNING_CANONICAL_ARCHITECTURE.md (Stage 2)
and docs/plans/DYNAMIC_PLANNING_MIGRATION_PLAN.md (Stage 3). No existing
module imports this package, and it has no production entry point; the only
entry points are scripts/dynamic_planning_qualification.py and the tests.
"""
