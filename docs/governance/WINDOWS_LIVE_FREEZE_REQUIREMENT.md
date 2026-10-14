# Mandatory live qualification before freeze

Owner instruction, 2026-10-14; applies to this restoration and subsequent URI
development milestones. This additive policy does not change historical
accepted/frozen component identities or authorize canonical integration.

No successful intended-environment live end-to-end qualification means no
freeze. Unit tests, mocks, simulation, dashboard status and code audits cannot
substitute for actual user-facing execution.

The evidence-backed ladder is Planned → Implemented → Tested → Live Qualified
→ Independently Accepted → Frozen. Freeze requires complete declared scope,
passing mandatory regressions/security/authority/frozen/provenance gates, real
intended-profile UI workflows, measured responsiveness and resource safety,
independent ACCEPT for the exact candidate commit/tree, and a reproducible
qualification/freeze receipt. A required failed or blocked live gate means
BLOCKED / NOT FROZEN. List unimplemented features separately; do not silently
remove them from scope or present them as passing tests.

Reviewers do not implement their own candidate. New reproducible findings may
enter an isolated repair/test/review cycle; repeated blocking conditions follow
the established stopping rule. Canonical integration and production cutover
retain their separate authorization gates.
