"""Category x destination policy `m95.policy.v1` (plan section 2.2). The table is the policy; code only reads it."""
from __future__ import annotations

from enum import Enum

from . import classify as C

POLICY_ID = "m95.policy.v1"


class Destination(str, Enum):
    LOCAL_BRAIN = "LOCAL_BRAIN"            # Runtime v1 on loopback
    LOCAL_TOOL = "LOCAL_TOOL"              # deterministic local code, local files
    WEB_SEARCH = "WEB_SEARCH"              # third-party search APIs (Tavily, Brave, SearXNG)
    EXTERNAL_MODEL = "EXTERNAL_MODEL"      # cloud model providers
    EXTERNAL_AGENT = "EXTERNAL_AGENT"      # vendor agent CLIs (Claude Code, Codex)
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"  # a service the user addressed directly (their own Google Drive, mail)
    LOG = "LOG"                            # logs, telemetry, diagnostics


LOCAL = frozenset({Destination.LOCAL_BRAIN, Destination.LOCAL_TOOL})

ALLOW, PSEUDONYMIZE, REDACT, REQUIRE_GRANT, REFUSE = "ALLOW", "PSEUDONYMIZE", "REDACT", "REQUIRE_GRANT", "REFUSE"
STRICTNESS = {ALLOW: 0, PSEUDONYMIZE: 1, REDACT: 2, REQUIRE_GRANT: 3, REFUSE: 4}

# A grant can turn these (category, destination) actions into ALLOW. Anything not listed cannot be granted.
_D = Destination
_EXT = (_D.EXTERNAL_MODEL, _D.EXTERNAL_AGENT)
_IDENT = (C.GOV_ID, C.FINANCIAL, C.SECRET_LIKE, C.LONG_NUMBER)
_PERSONAL = (C.CONTACT, C.ADDRESS, C.PERSON)

TABLE: dict = {}
GRANTABLE: set = set()


def _set(cats, dests, action, grantable=False):
    for c in cats:
        for d in dests:
            TABLE[(c, d)] = action
            if grantable:
                GRANTABLE.add((c, d))


_set(C.CATEGORIES, LOCAL, ALLOW)
_set(C.CATEGORIES, (_D.LOG,), REDACT)
_set((C.CONFIDENTIAL,), (_D.LOG,), ALLOW)
_set((C.CREDENTIAL,), (_D.WEB_SEARCH, _D.EXTERNAL_SERVICE) + _EXT, REFUSE)          # hard: never grantable
_set(_IDENT + _PERSONAL, (_D.WEB_SEARCH,), REDACT, grantable=True)
_set(_IDENT + _PERSONAL, _EXT, PSEUDONYMIZE, grantable=True)
_set(_IDENT, (_D.EXTERNAL_SERVICE,), REQUIRE_GRANT, grantable=True)
_set(_PERSONAL, (_D.EXTERNAL_SERVICE,), ALLOW)
_set((C.CONFIDENTIAL,), (_D.WEB_SEARCH, _D.EXTERNAL_SERVICE), ALLOW)
_set((C.CONFIDENTIAL,), _EXT, REQUIRE_GRANT, grantable=True)


def action(category: str, destination) -> str:
    """The table action; anything missing (an unknown category or destination) is REFUSE."""
    try:
        dest = Destination(destination)
    except ValueError:
        return REFUSE
    return TABLE.get((category, dest), REFUSE)


def grantable(category: str, destination) -> bool:
    try:
        return (category, Destination(destination)) in GRANTABLE
    except ValueError:
        return False


# --- trusted identifiers (review R1-03 / R2-03) ------------------------------------------------------------------------
# Who may call the gateway, for which purpose. These are code constants of the wiring that calls prepare(), never
# caller content, so the audit can record them verbatim. An unregistered requester or purpose is refused: a value
# passed by mistake in one of these fields (an e-mail, a hash, a passport number) never reaches the audit or the
# grant store. Wiring code that adds a consumer registers it here (or passes it to PrivacyGateway(requesters=...)).
KNOWN_REQUESTERS = frozenset({
    "uri_web.research",
    "uri_web.search.tavily", "uri_web.search.brave", "uri_web.search.searxng",
    "uri_scheduler.festival_gif.v1",
    "uri_worker.external_harness",
})
KNOWN_PURPOSES = frozenset({"web_research", "scheduled_creative", "external_harness_turn", "restore"})
