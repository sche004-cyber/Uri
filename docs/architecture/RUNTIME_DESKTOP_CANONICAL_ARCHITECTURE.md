# Runtime desktop completion — bounded design

Reuse Runtime v1, the existing qualified catalog, ProfileFollower, selection validator, GPU lease and controlled reconfigure path.

Vision On prefers a switchable, qualified profile without MTP within the existing context preference; otherwise it falls back to the qualified existing choice. Turning vision off still selects P2. Do not change catalog order globally or add controls. Keep confirmations, context shrink checks and Assist vision locks.

At CLI host startup, an explicit --profile takes precedence. Otherwise read brain_profile.json in the report directory through runtime_profile_selection.select. Only frozen/P2/P3 can be restored; invalid or unqualified data resolves to frozen. Record startup selection provenance in the host report. No file means exactly the frozen configuration.

No new model, engine, dependency, permission, authority, automatic switch, P1 qualification or frozen-config edit.
