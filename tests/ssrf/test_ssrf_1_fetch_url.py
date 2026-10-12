"""SSRF-1 (owner decision D2): uri_core/tools/fetch_url.py must never reach a private, local or metadata address.

Before the repair, FetchUrlTool called requests.get(url, stream=True) with default redirect following and no address
checks. Each test here fails on the pre-repair commit 03f0bf2c and passes after it. No real network: a fake resolver and
httpx.MockTransport stand in for DNS and the wire; `requests` is patched to fail if anything still calls it.

Self-contained: no fixture files; everything is built here.
"""
import io
import json

import httpx
import pytest
import requests

from uri_core.tools import fetch_url as FU
from uri_web.safe_fetch import SafeFetcher

PUBLIC = "93.184.215.14"


@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    """S-AC4: nothing in the tool may use `requests` for the network hop."""
    calls = []

    def boom(*a, **k):
        calls.append((a, k))
        raise AssertionError("requests must not be used by fetch_url")
    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setattr(requests.Session, "request", boom)
    monkeypatch.setattr(requests.Session, "send", boom)
    return calls


def tool_with(handler, answers=None, seen=None):
    answers = answers or {}

    def resolver(host, port):
        if seen is not None:
            seen.append(("dns", host))
        return answers.get(host, [PUBLIC])

    def wire(request):
        if seen is not None:   # the pinned connection goes to the checked IP; the name is in the Host header
            seen.append(("http", request.headers.get("host", "").split(":")[0], str(request.url)))
        return handler(request)
    types = {m: "document" for m in FU._EXTENSION_BY_CONTENT_TYPE}
    types[""] = "html"
    f = SafeFetcher(resolver=resolver, transport=httpx.MockTransport(wire), honour_robots=False,
                    max_bytes=FU._MAX_BYTES, total_timeout=15.0, extra_types=types)
    return FU.FetchUrlTool(fetcher=f), f


def html(body, status=200, ctype="text/html; charset=utf-8"):
    return httpx.Response(status, headers={"content-type": ctype}, content=body.encode())


# ---- S-AC1: refused before any connection --------------------------------------------------------------------------
INTERNAL = ("http://127.0.0.1/", "http://127.1.2.3:80/admin", "http://localhost/", "http://api.localhost/",
            "http://[::1]/", "http://10.0.0.5/", "http://172.16.3.4/", "http://192.168.1.1/router",
            "http://100.64.0.1/", "http://169.254.169.254/latest/meta-data/", "http://0.0.0.0/",
            "http://224.0.0.1/", "http://[::ffff:127.0.0.1]/", "http://2130706433/", "http://0x7f.1/",
            "http://0177.0.0.1/", "http://user:pw@example.com/", "http://example.com:8080/", "http://[fe80::1]/",
            "http://[fc00::1]/", "http://[64:ff9b::a00:1]/")


@pytest.mark.parametrize("url", INTERNAL)
def test_s_ac1_internal_targets_are_refused_with_no_connection(url):
    seen = []
    tool, f = tool_with(lambda r: html("<p>secret</p>"), seen=seen)
    out = tool.execute(request_text=f"please read {url} now")
    assert out["status"] == "unavailable" and out.get("refusal_code"), (url, out)
    assert "secret" not in json.dumps(out)
    assert not [s for s in seen if s[0] == "http"], (url, seen)


@pytest.mark.parametrize("url", ("http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/",
                                 "http://192.168.1.1/"))
def test_s_ac1_production_tool_refuses_literal_internal_addresses(url):
    out = FU.FetchUrlTool().execute(request_text=f"open {url}")
    assert out["status"] == "unavailable" and out.get("refusal_code"), out
    assert "127.0.0.1" not in out["message"] and "169.254" not in out["message"]


# ---- S-AC2: redirects re-checked at every hop -----------------------------------------------------------------------
@pytest.mark.parametrize("code", (301, 302, 303, 307, 308))
@pytest.mark.parametrize("target", ("http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data/",
                                    "http://10.1.2.3/", "http://localhost:80/"))
def test_s_ac2_a_public_redirect_to_an_internal_target_is_refused(code, target):
    seen = []

    def handler(r):
        if r.headers.get("host", "").split(":")[0] == "public.example":
            return httpx.Response(code, headers={"location": target})
        return html("<p>INTERNAL-SECRET</p>")
    tool, f = tool_with(handler, seen=seen)
    out = tool.execute(request_text="read http://public.example/start")
    assert out["status"] == "unavailable" and out.get("refusal_code"), out
    assert "INTERNAL-SECRET" not in json.dumps(out)
    assert [s[1] for s in seen if s[0] == "http"] == ["public.example"], seen


def test_s_ac2_more_than_five_redirects_are_not_followed():
    tool, f = tool_with(lambda r: httpx.Response(302, headers={"location": "http://public.example/again"}))
    out = tool.execute(request_text="read http://public.example/start")
    assert out["status"] == "unavailable" and out.get("error") == "TOO_MANY_REDIRECTS", out


# ---- S-AC3: DNS answers --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("answers", ([PUBLIC, "10.0.0.7"], ["127.0.0.1"], ["169.254.169.254"], ["::1"]))
def test_s_ac3_any_non_public_dns_answer_refuses_the_host(answers):
    seen = []
    tool, f = tool_with(lambda r: html("<p>SECRET</p>"), answers={"rebind.example": answers}, seen=seen)
    out = tool.execute(request_text="read http://rebind.example/")
    assert out["status"] == "unavailable" and out.get("refusal_code"), out
    assert not [s for s in seen if s[0] == "http"]


def test_s_ac3_the_connection_goes_to_the_checked_address_only():
    tool, f = tool_with(lambda r: html("<p>hello world</p>"), answers={"site.example": [PUBLIC]})
    out = tool.execute(request_text="read http://site.example/page")
    assert out["status"] == "success" and "hello world" in out["text"]
    assert f.connections == [("site.example", PUBLIC)]


# ---- S-AC5: ordinary behaviour kept --------------------------------------------------------------------------------
def test_s_ac5_public_html_text_and_truncation():
    tool, _ = tool_with(lambda r: html("<html><head><script>x()</script></head><body><p>" + "word " * 3000 + "</p></body></html>"))
    out = tool.execute(request_text="read https://public.example/page.")
    assert out["status"] == "success" and out["url"] == "https://public.example/page"
    assert out["truncated"] is True and len(out["text"]) == 8000 and "x()" not in out["text"]


def test_s_ac5_empty_page_http_error_unsupported_and_oversize():
    tool, _ = tool_with(lambda r: html("<html><body>   </body></html>"))
    assert tool.execute(request_text="read http://public.example/")["status"] == "empty"
    tool, _ = tool_with(lambda r: html("nope", status=404))
    out = tool.execute(request_text="read http://public.example/")
    assert out["status"] == "unavailable" and "HTTP 404" in out["message"]
    tool, _ = tool_with(lambda r: httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG"))
    out = tool.execute(request_text="read http://public.example/x.png")
    assert out["status"] == "unsupported" and "image/png" in out["message"]
    big = b"a" * (FU._MAX_BYTES + 10)
    tool, _ = tool_with(lambda r: httpx.Response(200, headers={"content-type": "text/plain"}, content=big))
    out = tool.execute(request_text="read http://public.example/big.txt")
    assert out["status"] == "unavailable" and "MB" in out["message"]


def test_s_ac5_documents_are_still_read():
    import docx as python_docx
    d = python_docx.Document()
    d.add_paragraph("Budget minutes 2026")
    buf = io.BytesIO()
    d.save(buf)
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    tool, _ = tool_with(lambda r: httpx.Response(200, headers={"content-type": docx}, content=buf.getvalue()))
    out = tool.execute(request_text="read http://public.example/minutes.docx")
    assert out["url"] == "http://public.example/minutes.docx" and out["content_type"] == docx
    assert "Budget minutes 2026" in json.dumps(out)
    tool, _ = tool_with(lambda r: httpx.Response(200, headers={"content-type": "text/csv"}, content=b"a,b\n1,2\n"))
    out = tool.execute(request_text="read http://public.example/data.csv")
    assert out["content_type"] == "text/csv" and "1" in json.dumps(out)


def test_s_ac5_no_url_and_non_http_scheme_unchanged():
    assert FU.FetchUrlTool().execute(request_text="what can you do")["status"] == "input_required"
    assert FU.FetchUrlTool().execute(request_text="open ftp://example.com/file")["status"] == "input_required"


# ---- S-AC6: W1 unchanged by default ---------------------------------------------------------------------------------
def test_s_ac6_safe_fetcher_default_still_refuses_documents():
    f = SafeFetcher(resolver=lambda h, p: [PUBLIC], honour_robots=False,
                    transport=httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": "application/pdf"},
                                                                         content=b"%PDF-1.4")))
    res = f.fetch("http://public.example/a.pdf")
    assert res.record.fetch_status == "UNSUPPORTED_CONTENT_TYPE" and res.body == b""
