# Runtime desktop completion — evidence audit

2026-10-25. Baseline fd4b9af63608e598a0a4c1d35b9485139e63a970.

The installed desktop already contains runtime profiles and the three-toggle UI. P2 (64K text) and P3 (32K GPU vision without draft) have recorded live journeys and 60-minute soaks. P1 is unqualified and stays refused. Earlier reports of pending research were stale; the integrated lineage includes c3fc8bbc and URI-CONTROLS-3.

Two local completion gaps: visionChoices chooses the first qualified catalog entry, which selects the heavier frozen profile instead of P3; ws_brain_host.main ignores the existing validated selection and run.sync_selection then replaces it at startup. No model, engine, permission, artifact pin or execution authority change is needed.

Live baseline: desktop fd4b9af6, actual host READY on c64k-visoff-mtpoff. UI exposes Thinking, Vision and URI Assist.
