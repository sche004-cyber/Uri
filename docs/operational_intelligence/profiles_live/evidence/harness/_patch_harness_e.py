"""One-off record (2026-10-18): after the merge of canonical 348677b7 the candidate head is f3d5eb29; runtime-e was
materialized from it and installation rp-e (port 18334) provisioned. The harness files were switched from runtime-d /
provision-d.json to runtime-e / provision-e.json with a plain text substitution (sed) in soak.py,
assist_vision_app.py, switch_live.py, live_session.py and go.sh. No other change."""
