"""URI privacy gateway (M95): deterministic, local-first control of personal data before it leaves URI.

Plan and acceptance criteria: `docs/privacy/00_PLAN_AND_ACCEPTANCE_CRITERIA.md`.

    classify   risk-aware detection (reuses the Assist redaction rules for credentials)
    policy     category x destination actions (`m95.policy.v1`)
    vault      per-scope opaque references; optional encrypted persistence (DPAPI-protected key)
    grants     scoped, expiring, revocable disclosure grants (relax sanitization only, never authorize a capability)
    audit      value-free, hash-chained privacy audit
    gateway    `prepare()` before egress, `restore()` for local output; fails closed
    keys       DPAPI-protected persistent secrets (D10)

No model is involved in any decision, so text inside the data cannot change what the gateway does.
"""
from .gateway import Egress, PrivacyGateway, PrivacyRefused, default_gateway  # noqa: F401
from .policy import Destination  # noqa: F401
