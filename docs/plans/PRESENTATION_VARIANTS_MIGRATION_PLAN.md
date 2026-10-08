# Presentation variants: integration and validation plan

2026-10-03. Direct User scope: repair `uri-m37-m39-integration`.
References: [evidence](../research/PRESENTATION_VARIANTS_ROOT_CAUSE_AUDIT.md),
[design](../architecture/PRESENTATION_VARIANTS_CANONICAL_ARCHITECTURE.md).

1. Preserve the pre-existing dirty tree; take code-only baseline snapshots of
   the overlapping schema and allowlist documentation. Do not migrate `_V1`
   implementation, credentials, account stores or provider configuration.
2. Validate and render variant outputs inside existing `generate_document`;
   forward them via its already declared-input canonical approval path. Expose
   the new content field in the native schema; no execution-boundary change.
3. Add bounded session metadata to shared decision construction and the native
   prompt. Correct presentation/local-review guidance in the existing Brain
   prompts. Carry original subject and photo intent across short follow-ups.
4. Parse and display actual returned file references using existing UI chips.
5. Test mock composition, three distinct themes/files, one-file compatibility,
   invalid/oversized/authority-bearing variant proposals, image reuse/failure,
   partial storage failure, session/user isolation, canonical forwarding,
   metadata context and all file chips. Run existing document/canonical/UI tests.
6. Record frozen guard results separately: existing dirty changes and this new
   candidate can differ from accepted pins; do not weaken or re-pin the guards.
7. Run an isolated real Brain + Core qualification before deployment. Restart
   the running Core only through its existing launcher/configuration, preserving
   existing account/provider/external-store keys. Live native UI verification
   remains necessary; request manual actions if native driver control is absent.
8. Prepare evidence and exact touched paths for independent Claude review.
   Do not commit, push, freeze or declare independently VERIFIED.

Rollback uses the bounded code diff and pre-existing snapshots; generated
disposable test artifacts are separate from the original user's files. Never
replace an entire dirty file with HEAD merely to roll back this repair.
