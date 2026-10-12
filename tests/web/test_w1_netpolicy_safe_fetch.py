"""W1-AC1..AC5: egress policy and SafeFetcher (no real network: fake resolver + httpx.MockTransport)."""
import httpx
import pytest

from uri_web import netpolicy as NP
from uri_web import records as R
from uri_web.safe_fetch import CancelFlag, SafeFetcher

PUBLIC = "93.184.216.34"


@pytest.mark.parametrize("addr", [
    "127.0.0.1", "127.1.2.3", "10.0.0.1", "172.16.5.4", "172.31.255.255", "192.168.1.1", "100.64.0.1",
    "100.127.255.254", "169.254.169.254", "169.254.1.1", "0.0.0.0", "0.1.2.3", "224.0.0.1", "239.255.255.250",
    "240.0.0.1", "255.255.255.255", "192.0.0.8", "192.0.2.1", "198.18.0.1", "198.51.100.7", "203.0.113.9",
    "::1", "::", "fc00::1", "fd12:3456::1", "fe80::1", "fe80::1%eth0", "ff02::1", "2001:db8::1",
    "::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254", "64:ff9b::7f00:1", "64:ff9b::a00:1",
    "64:ff9b:1::a9fe:a9fe", "2002:7f00:1::", "2002:c0a8:101::1", "2001:0:4136:e378:8000:63bf:3fff:fdd2",
    "not-an-ip",
])
def test_non_public_addresses_refused(addr):
    with pytest.raises(NP.EgressRefused):
        NP.check_address(addr)


@pytest.mark.parametrize("addr", [PUBLIC, "8.8.8.8", "1.1.1.1", "2606:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"])
def test_public_addresses_allowed(addr):
    NP.check_address(addr)


@pytest.mark.parametrize("url,code", [
    ("file:///etc/passwd", "SCHEME_REFUSED"), ("ftp://example.com/x", "SCHEME_REFUSED"),
    ("gopher://example.com/", "SCHEME_REFUSED"), ("javascript:alert(1)", "SCHEME_REFUSED"),
    ("data:text/html,hi", "SCHEME_REFUSED"), ("http://user:pw@example.com/", "USERINFO_REFUSED"),
    ("http://example.com@127.0.0.1/", "USERINFO_REFUSED"), ("http://example.com:8080/", "PORT_REFUSED"),
    ("http://example.com:22/", "PORT_REFUSED"), ("http://127.0.0.1/", "ADDRESS_NOT_PUBLIC"),
    ("http://[::1]/", "ADDRESS_NOT_PUBLIC"), ("http://[::ffff:127.0.0.1]/", "ADDRESS_NOT_PUBLIC"),
    ("http://169.254.169.254/latest/meta-data/", "ADDRESS_NOT_PUBLIC"), ("http://localhost/", "HOST_LOCAL_NAME"),
    ("http://foo.localhost/", "HOST_LOCAL_NAME"), ("http://printer.local/", "HOST_LOCAL_NAME"),
    ("http://metadata.google.internal/", "HOST_LOCAL_NAME"), ("http://2130706433/", "HOST_NUMERIC_AMBIGUOUS"),
    ("http://0x7f.0.0.1/", "HOST_NUMERIC_AMBIGUOUS"), ("http://127.1/", "HOST_NUMERIC_AMBIGUOUS"),
    ("http://017700000001/", "HOST_NUMERIC_AMBIGUOUS"), ("http:///x", "HOST_MISSING"),
    ("http://exa mple.com/", "URL_INVALID"), ("http://example.com\\@evil/", "URL_INVALID"),
    ("http://" + "a" * 2100 + ".com/", "URL_INVALID"), ("", "URL_INVALID"),
])
def test_url_refusals(url, code):
    with pytest.raises(NP.EgressRefused) as e:
        NP.check_url(url)
    assert e.value.code == code


def test_url_accepts_plain_public_https():
    t = NP.check_url("https://Example.COM/a?b=1")
    assert (t.scheme, t.host, t.port, t.is_literal) == ("https", "example.com", 443, False)


# ---- SafeFetcher ---------------------------------------------------------------------------------------------------

def mk(routes, dns, **kw):
    seen = []

    def handler(req):
        seen.append({"url": str(req.url), "host": req.headers.get("host"), "sni": req.extensions.get("sni_hostname"),
                     "cookie": req.headers.get("cookie"), "auth": req.headers.get("authorization"),
                     "ua": req.headers.get("user-agent")})
        key = (req.headers.get("host"), req.url.path)
        if req.url.path == "/robots.txt" and key not in routes:
            return httpx.Response(404)
        fn = routes.get(key)
        return fn(req) if callable(fn) else (fn or httpx.Response(404))

    def resolver(host, port):
        v = dns[host]
        if isinstance(v, list) and v and callable(v[0]):
            return v.pop(0)()
        return list(v) if isinstance(v, list) else v()
    return SafeFetcher(resolver=resolver, transport=httpx.MockTransport(handler), **kw), seen


def html(body, **h):
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8", **h}, text=body)


def test_connection_is_pinned_to_the_validated_address_with_host_and_sni():
    f, seen = mk({("good.test", "/a"): html("<p>ok</p>")}, {"good.test": [PUBLIC]})
    r = f.fetch("https://good.test/a")
    assert r.ok and r.record.connected_address == PUBLIC
    page = [s for s in seen if s["url"].endswith("/a")][0]
    assert page["url"] == f"https://{PUBLIC}/a" and page["host"] == "good.test" and page["sni"] == "good.test"
    assert page["cookie"] is None and page["auth"] is None and page["ua"].startswith("URI-WebIntelligence")


def test_any_private_answer_refuses_the_hop():
    f, seen = mk({}, {"mixed.test": [PUBLIC, "10.0.0.7"]})
    r = f.fetch("https://mixed.test/")
    assert r.record.fetch_status == R.REFUSED and r.record.refusal_code == "ADDRESS_NOT_PUBLIC"
    assert seen == []                     # no connection at all (robots included)


def test_dns_rebinding_second_answer_is_never_used():
    answers = [lambda: [PUBLIC], lambda: ["127.0.0.1"]]   # robots hop resolves public; page hop would rebind
    f, seen = mk({("rb.test", "/x"): html("<p>x</p>")}, {"rb.test": answers})
    r = f.fetch("https://rb.test/x")
    # The robots hop used the public answer; the page hop got the private answer and was refused before connecting.
    assert r.record.fetch_status == R.REFUSED
    assert all(PUBLIC in s["url"] for s in seen)


def test_redirect_to_private_address_refused_at_the_hop():
    f, seen = mk({("pub.test", "/r"): httpx.Response(302, headers={"location": "http://internal.test/secret"})},
                 {"pub.test": [PUBLIC], "internal.test": ["192.168.0.10"]})
    r = f.fetch("https://pub.test/r")
    assert r.record.fetch_status == R.REFUSED and r.record.redirect_chain[0]["status"] == 302
    assert not any("192.168" in s["url"] for s in seen)


def test_redirect_to_literal_loopback_and_bad_scheme_refused():
    for loc, code in (("http://127.0.0.1:80/admin", "ADDRESS_NOT_PUBLIC"), ("file:///c:/windows/win.ini", "SCHEME_REFUSED"),
                      ("http://[::1]/", "ADDRESS_NOT_PUBLIC"), ("http://localhost/", "HOST_LOCAL_NAME")):
        f, _ = mk({("pub.test", "/r"): httpx.Response(301, headers={"location": loc})}, {"pub.test": [PUBLIC]})
        r = f.fetch("https://pub.test/r", robots=False)
        assert (r.record.fetch_status, r.record.refusal_code) == (R.REFUSED, code)


def test_redirect_limit():
    routes = {("loop.test", f"/{i}"): httpx.Response(302, headers={"location": f"/{i + 1}"}) for i in range(10)}
    f, _ = mk(routes, {"loop.test": [PUBLIC]}, max_redirects=3)
    r = f.fetch("https://loop.test/0", robots=False)
    assert r.record.fetch_status == R.TOO_MANY_REDIRECTS and len(r.record.redirect_chain) == 4


def test_relative_redirect_followed_and_recorded():
    f, _ = mk({("a.test", "/old"): httpx.Response(301, headers={"location": "/new"}),
               ("a.test", "/new"): html("<p>moved</p>")}, {"a.test": [PUBLIC]})
    r = f.fetch("https://a.test/old", robots=False)
    assert r.ok and r.record.final_url == "https://a.test/new" and r.record.redirect_chain[0]["url"].endswith("/old")


def test_byte_cap_declared_and_streamed():
    f, _ = mk({("big.test", "/d"): httpx.Response(200, headers={"content-type": "text/html", "content-length": "999999"},
                                                    text="x"),
               ("big.test", "/s"): html("y" * 5000)}, {"big.test": [PUBLIC]}, max_bytes=1000)
    assert f.fetch("https://big.test/d", robots=False).record.fetch_status == R.TOO_LARGE
    assert f.fetch("https://big.test/s", robots=False).record.fetch_status == R.TOO_LARGE


def test_content_type_allow_list():
    f, _ = mk({("t.test", "/exe"): httpx.Response(200, headers={"content-type": "application/octet-stream"}, content=b"MZ"),
               ("t.test", "/pdf"): httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")},
              {"t.test": [PUBLIC]})
    for p in ("/exe", "/pdf"):
        r = f.fetch("https://t.test" + p, robots=False)
        assert r.record.fetch_status == R.UNSUPPORTED_CONTENT_TYPE and r.text == "" and r.record.sha256


def test_timeout_and_unreachable_and_cancel():
    def boom(req):
        raise httpx.ConnectTimeout("t", request=req)

    def down(req):
        raise httpx.ConnectError("refused", request=req)
    f, _ = mk({("x.test", "/t"): boom, ("x.test", "/u"): down, ("x.test", "/c"): html("<p>c</p>")}, {"x.test": [PUBLIC]})
    assert f.fetch("https://x.test/t", robots=False).record.fetch_status == R.TIMED_OUT
    assert f.fetch("https://x.test/u", robots=False).record.fetch_status == R.UNREACHABLE
    c = CancelFlag()
    c.cancel()
    assert f.fetch("https://x.test/c", robots=False, cancel=c).record.fetch_status == R.CANCELLED


def test_total_deadline():
    t = [0.0]

    def clock():
        t[0] += 30.0
        return t[0]
    f, _ = mk({("s.test", "/"): html("<p>slow</p>")}, {"s.test": [PUBLIC]}, clock=clock, total_timeout=20)
    assert f.fetch("https://s.test/", robots=False).record.fetch_status == R.TIMED_OUT


def test_robots_disallow_and_record():
    robots = httpx.Response(200, headers={"content-type": "text/plain"}, text="User-agent: *\nDisallow: /private\n")
    f, seen = mk({("r.test", "/robots.txt"): robots, ("r.test", "/private/x"): html("<p>no</p>"),
                  ("r.test", "/public"): html("<p>yes</p>")}, {"r.test": [PUBLIC]})
    d = f.fetch("https://r.test/private/x")
    assert d.record.fetch_status == R.ROBOTS_DISALLOWED and d.record.robots_decision == "DISALLOWED"
    assert not any(s["url"].endswith("/private/x") for s in seen)
    ok = f.fetch("https://r.test/public")
    assert ok.ok and ok.record.robots_decision == "ALLOWED"


def test_record_fields_and_untrusted_trust_is_fixed():
    f, _ = mk({("g.test", "/"): html("<p>hello</p>")}, {"g.test": [PUBLIC]})
    r = f.fetch("https://g.test/", robots=False)
    d = r.record.to_dict()
    for k in ("requested_url", "final_url", "redirect_chain", "retrieved_at", "http_status", "content_type", "bytes",
              "sha256", "connected_address", "egress", "robots_decision", "trust"):
        assert k in d
    assert d["trust"] == R.UNTRUSTED and d["sha256"] and d["bytes"] == len("<p>hello</p>")
    with pytest.raises(ValueError):
        R.SourceRecord(requested_url="x", trust="TRUSTED")


def test_dns_failure_is_refused_in_direct_mode():
    def resolver(h, p):
        raise OSError("nx")
    f = SafeFetcher(resolver=resolver, transport=httpx.MockTransport(lambda r: html("x")))
    r = f.fetch("https://nx.test/", robots=False)
    assert (r.record.fetch_status, r.record.refusal_code) == (R.REFUSED, "DNS_FAILED")


def test_proxy_mode_requires_explicit_proxy_and_is_recorded():
    with pytest.raises(ValueError):
        SafeFetcher(egress="proxy")
    f = SafeFetcher(egress="proxy", transport=httpx.MockTransport(lambda r: html("<p>p</p>")),
                    resolver=lambda h, p: (_ for _ in ()).throw(OSError()), proxy_unresolved_ok=("p.test",))
    r = f.fetch("https://p.test/", robots=False)
    assert r.ok and r.record.egress == "proxy" and r.record.connected_address is None
    # Not allow-listed and not locally resolvable: refused, even in proxy mode (interim review F6).
    assert f.fetch("https://other.test/", robots=False).record.refusal_code == "DNS_FAILED"
    # URL-level checks still apply in proxy mode.
    assert f.fetch("http://127.0.0.1/", robots=False).record.fetch_status == R.REFUSED
