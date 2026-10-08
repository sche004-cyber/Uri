# Bounded layout/recheck migration

1. Preserve the existing dirty repair and neighbouring reference changes.
2. Patch the actual PPTX renderer; add metric/geometry inspection.
3. Add one bounded composition-role review before storage, with at most one
   validated content correction. Reuse URI's principal, gate and FileStore.
4. Mock-test wrapped text, portrait images, dense-content failure, malformed
   review proposals, unavailable review, one correction and zero early writes.
5. Run existing presentation/composition/dispatch regressions before a harmless
   isolated real Brain test. Record added latency and review limitations.
6. Reopen the same normal desktop app only after those checks; request native
   visual feedback where automated slide rendering is unavailable.
7. Update Claude's review packet. Do not change frozen pins, commit or push.

The prior desktop structural qualification is superseded by the User's visual
overlap finding. Existing saved user documents are never overwritten. New
generation gets the repaired path; regenerating older files requires a new
user-authorized request. Broader DOCX/PDF/XLSX visual checking is deferred.
