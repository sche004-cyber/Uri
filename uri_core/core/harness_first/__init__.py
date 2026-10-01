"""Harness-first turn handling (EXPERIMENTAL, PROVISIONAL, default off).

URI inspects a turn deterministically before any model call. Only a bounded,
safe residue is handed to a local Edge specialist; everything else continues
down the existing /ask chain unchanged. Enabled only when URI_HARNESS_FIRST=1.
See docs/plans/HARNESS_FIRST_EDGE_ARCHITECTURE_MAP.md.
"""
