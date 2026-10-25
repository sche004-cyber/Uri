"""Test wiring: a gateway that trusts the test suite's own requester and purpose names (production wiring registers
its names in uri_privacy.policy.KNOWN_REQUESTERS or passes them to PrivacyGateway the same way)."""
from uri_privacy import PrivacyGateway

TEST_REQUESTERS = frozenset({"test.component", "t", "r", "m", "live", "outsider", "alice", "bob", "owner"})
TEST_PURPOSES = frozenset({"test", "p", "m", "live", "other", "web_research"})


def TGateway(**kw):
    import inspect
    if "requesters" in inspect.signature(PrivacyGateway).parameters:   # pre-registry commits: plain gateway, so a
        kw.setdefault("requesters", TEST_REQUESTERS)                 # regression test fails on its own assertion
        kw.setdefault("purposes", TEST_PURPOSES)
    return PrivacyGateway(**kw)
