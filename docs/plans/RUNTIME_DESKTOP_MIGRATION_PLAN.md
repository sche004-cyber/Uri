# Runtime desktop completion â€” plan and acceptance

USER_FACING: existing Vision toggle. INDIRECT: saved qualified profile at host startup. Owner request 2026-10-25: "Can you finish it in one go? You have full autonomy, only thing is it should reflect on the URI app on my desktop". This authorizes the scoped completion, local candidate commits, controlled integration and desktop deployment after review and checks. It supersedes OPEN-12 only for preferring the already qualified P3 when Vision is enabled. Security and frozen authority remain unchanged.

1. Add regression cases for P3 preference and persisted startup selection. Demonstrate failures on baseline.
2. Patch only the choice helper and host startup; run focused and surrounding suites and frozen check.
3. Independent exact-commit lifecycle audit; repair findings.
4. Build the candidate and use the real desktop app and production Brain. Preserve the previous installation and all user data. Confirm UI journeys and host restart.
5. Evidence-only qualification commit, final independent review, canonical ancestry/recheck and integration receipt; leave the desktop running on P2.

Acceptance:
- AC1: Vision On from P2 selects P3; same-context preference retained; P1 and unswitchable entries never selected. Frozen remains fallback.
- AC2: fresh host restores saved P2/P3, explicit profile wins, absent/corrupt/unqualified selection falls back to frozen with provenance; artifact/lease admission unchanged.
- AC3: tests/oi and tests/ws show no new regression; focused Flutter controls suite and release build pass; frozen check clean.
- AC4: actual desktop app can discover and operate Thinking/Vision; confirmation and progress truthful; P2 to P3 to P2 preserves an actual Brain conversation marker. Restart the host and confirm selected P2 is restored.
- AC5: existing data and previous build retained; desktop shortcut opens the reviewed build. No model substitution, new capture grants or qualification claims for P1/Assist capture.

Protected/deferred: frozen files, all model artifacts, engine, permissions, unrelated Office/Web/Writing work, new Assist capture, P1 and stress tests. Only scripts/ws_brain_host.py, uri_ui/lib/living/integration/brain_quick_controls.dart and their focused tests plus this milestone documentation/config/evidence may change.

The shrink-refusal regression now expects P3; the refusal coverage is unchanged.
