# Harness desktop completion — migration

2026-10-03. Direct User implementation authorization; provisional, no freeze.
Basis: [evidence](../research/HARNESS_DESKTOP_COMPLETION_ROOT_CAUSE_AUDIT.md)
and [architecture](../architecture/HARNESS_DESKTOP_COMPLETION_CANONICAL_ARCHITECTURE.md).

1. Add registry and blocked Antigravity adapter alongside the existing seam.
2. Add selected-provider controller, atomic per-user checkpoints, polling,
   cancellation and explicit recovery. Preserve legacy preparation/approval API.
3. Extend the existing real-app test panel with management dialog, provider
   selection, preparation/approval, status, receipt and recovery controls.
4. Add opt-in one-click launcher using persisted separate Core state and flagged
   desktop binary. No production registration or installed server replacement.
5. Run focused auth/selection/denial/checkpoint/quota/cancel tests plus M37/M38,
   Flutter tests/analysis and Windows build. Launch the actual application and
   use Flutter driver for real native controls and rendered screenshots.
6. Attempt one fresh Claude repair; preserve quota failure as BLOCKED if present.
   Antigravity repair stays BLOCKED pending adversarial containment qualification.
7. Separate Codex self-review and report; no independent audit/commit/push.

Rollback: stop provisional launcher and use normal app without
URI_DESKTOP_HARNESS_TEST. Existing composition, Core and M38 remain preserved.
No migration of installed credentials, Brain settings, original documents.
