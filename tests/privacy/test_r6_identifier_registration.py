"""R6-01: custom audit identifiers must remain code names, never user values."""

import pytest

from uri_privacy import PrivacyGateway
from uri_privacy.audit import PrivacyAudit


@pytest.mark.parametrize("identifier", [
    "alice@example.com",
    "purpose-4111111111111111",
    "password-mango2026",
    "sha256-" + "ab" * 32,
])
@pytest.mark.parametrize("field", ["requesters", "purposes"])
def test_gateway_rejects_content_shaped_custom_identifiers(field, identifier):
    audit = PrivacyAudit()
    with pytest.raises(ValueError, match="PRIVACY_IDENTIFIER_INVALID") as exc:
        PrivacyGateway(audit=audit, **{field: (identifier,)})
    assert identifier not in str(exc.value)
    assert identifier not in audit.requesters | audit.purposes
    assert audit.records == []


def test_direct_audit_trust_cannot_register_sensitive_identifiers():
    audit = PrivacyAudit()
    original = audit.requesters, audit.purposes
    with pytest.raises(ValueError, match="PRIVACY_IDENTIFIER_INVALID"):
        audit.trust({"uri_web.search.tavily", "alice@example.com"}, {"web_research"})
    assert (audit.requesters, audit.purposes) == original


def test_safe_custom_identifiers_remain_usable():
    gateway = PrivacyGateway(requesters=("test.component",), purposes=("test_purpose.v2",))
    result = gateway.prepare("ordinary text", requester="test.component", purpose="test_purpose.v2",
                             destination="WEB_SEARCH")
    assert result.text == "ordinary text"
    assert gateway.audit.records[-1]["requester"] == "test.component"
    assert gateway.audit.records[-1]["purpose"] == "test_purpose.v2"
