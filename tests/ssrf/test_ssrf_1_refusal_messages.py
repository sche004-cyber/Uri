"""SSRF-1 repair R1-01: a REFUSED fetch must report the real reason, not always "private or local network".

On f44f70a5 FetchUrlTool mapped every REFUSED record (DNS failure, port refusal, invalid URL, userinfo ...) to
"URI will not fetch that address (private or local network)." Only address-class refusals may say that; an
unresolvable host is "URI could not reach that URL." as it was before SSRF-1. The refusal_code stays, and the
message never names the address.

Self-contained: a fake resolver and httpx.MockTransport stand in for DNS and the wire; no network, no fixture files.
"""
import json
import socket

import httpx
import pytest

from uri_core.tools import fetch_url as FU
from uri_web.safe_fetch import SafeFetcher

PUBLIC = "93.184.215.14"
PRIVATE_WORDS = "private or local"


def tool_with(resolver, seen):
    def wire(request):
        seen.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<p>secret</p>")
    types = {m: "document" for m in FU._EXTENSION_BY_CONTENT_TYPE}
    types[""] = "html"
    f = SafeFetcher(resolver=resolver, transport=httpx.MockTransport(wire), honour_robots=False,
                    max_bytes=FU._MAX_BYTES, total_timeout=15.0, extra_types=types)
    return FU.FetchUrlTool(fetcher=f)


def public_resolver(host, port):
    return [PUBLIC]


def gaierror_resolver(host, port):
    raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")


def run(tool, url):
    out = tool.execute(request_text=f"please read {url}")
    assert out["status"] == "unavailable" and out.get("refusal_code"), out
    return out


def test_dns_failure_is_could_not_reach_not_private():
    seen = []
    out = run(tool_with(gaierror_resolver, seen), "http://typo-domain-xyz.com/")
    assert out["refusal_code"] == "DNS_FAILED"
    assert out["message"] == "URI could not reach that URL.", out
    assert PRIVATE_WORDS not in out["message"]
    assert not seen


def test_dns_empty_answer_is_could_not_reach_not_private():
    seen = []
    out = run(tool_with(lambda h, p: [], seen), "http://empty-answer.example/")
    assert out["refusal_code"] == "DNS_EMPTY"
    assert out["message"] == "URI could not reach that URL.", out
    assert not seen


def test_port_refusal_names_the_port_rule_not_private():
    seen = []
    out = run(tool_with(public_resolver, seen), "https://example.com:8443/x")
    assert out["refusal_code"] == "PORT_REFUSED"
    assert PRIVATE_WORDS not in out["message"], out
    assert "port" in out["message"].lower()
    assert not seen


def test_userinfo_refusal_is_not_called_private():
    seen = []
    out = run(tool_with(public_resolver, seen), "http://user:pw@example.com/")
    assert out["refusal_code"] == "USERINFO_REFUSED"
    assert PRIVATE_WORDS not in out["message"], out
    assert "password" in out["message"].lower()
    assert "pw" not in json.dumps({k: v for k, v in out.items() if k != "url"})
    assert not seen


def test_redirect_to_non_http_scheme_is_not_called_private():
    seen = []

    def wire(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "ftp://example.com/file"})
    f = SafeFetcher(resolver=public_resolver, transport=httpx.MockTransport(wire), honour_robots=False,
                    max_bytes=FU._MAX_BYTES, total_timeout=15.0)
    out = run(FU.FetchUrlTool(fetcher=f), "http://example.com/start")
    assert out["refusal_code"] == "SCHEME_REFUSED"
    assert PRIVATE_WORDS not in out["message"], out
    assert "http" in out["message"].lower()


@pytest.mark.parametrize("url,answers", [
    ("http://127.0.0.1/", None),
    ("http://169.254.169.254/latest/meta-data/", None),
    ("http://localhost/", None),
    ("http://2130706433/", None),
    ("http://rebind.example/", ["10.0.0.5"]),
])
def test_address_class_refusals_still_say_private_without_the_address(url, answers):
    seen = []
    out = run(tool_with(lambda h, p: answers or [PUBLIC], seen), url)
    assert PRIVATE_WORDS in out["message"], out
    for leak in ("127.0.0.1", "169.254", "10.0.0.5", "2130706433"):
        assert leak not in out["message"]
    assert not seen
