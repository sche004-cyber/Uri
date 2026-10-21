# Successor driver (UI-CONTROLS-TYPO-20261018)

`qc_driver.dart` in this folder is kept as integrated at canonical `ec2fab54`: it is the evidence of the BRAIN-QC and closure runs (its sha256 is recorded
in each run's `native-execution.json`). It drives the earlier menu chips (tap `qc-context`, then `qc-context-64K`).

From milestone UI-CONTROLS-TYPO-20261018 on, the controls are push-to-enable: `qc-thinking`, `qc-vision` and `qc-draft`
are toggles (one tap acts), `qc-context` is a selection whose segments `qc-context-32K` / `qc-context-64K` are tapped
directly, the Thinking menu is `qc-thinking-menu`, and `qc-mismatch` / `qc-notice` / `qc-switching` are unchanged.
The current live driver is `docs/ui/controls_typography_20261018/evidence/live_harness/ui_driver.dart`; use it (or
adapt it) for any new live run of the Quick Controls.
