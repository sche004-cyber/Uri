"""Repository-root pytest settings for whole-repository collection (PH1-GATE-2, AP-32 / OPEN-24).

`docs/` holds records and evidence, not tests, and must never be imported by pytest:
- `docs/evidence/` keeps deliberately colliding `test_same.py` fixtures (Phase 2 OQ review rounds 4-5);
- `docs/ui_v2/tools/patch_detached_geometry.py` and `patch_motion_pause.py` (formerly `test_*.py`, renamed in
  3c7a799b) are one-off patch scripts that rewrite `uri_ui` source files when imported.
"""

collect_ignore_glob = ["docs/*"]
