"""Repairs after driver run M95-PRIVACY-r6 rounds R1..R5 (Codex) and owner decisions LDEC-007 / LDEC-008 (plan PC-13).
Synthetic values only."""
import json
import random
import string

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import vault
from uri_privacy.classify import CREDENTIAL, classify
from uri_web.search import REFUSED, TavilyProvider

from .helpers import TGateway

EXTERNAL = ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL")


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused:
        return True, ""


def wire(text):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})
    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture), privacy=TGateway()).search(text)
    return result, sent


# --- R5-01: split keys with a fixed body length need no digits ---------------------------------------------------------
FIXED = {"AKIA": (16, string.ascii_uppercase + string.digits), "ASIA": (16, string.ascii_uppercase),
         "AIza": (35, string.ascii_letters), "ghp_": (36, string.ascii_letters), "glpat-": (20, string.ascii_lowercase)}


def test_r5_01_fixed_length_split_keys_with_zero_or_one_digit_are_refused():
    rng = random.Random(5)
    bad = []
    for prefix, (n, alphabet) in FIXED.items():
        for digits in (0, 1):
            for _ in range(25):
                body = [rng.choice(alphabet.replace("0123456789", "") or alphabet) for _ in range(n)]
                body = [c for c in body if not c.isdigit()] + [str(rng.randint(0, 9)) for _ in range(digits)]
                body = (body + ["Q"] * n)[:n]
                for g in (4, 5):
                    key = prefix + " ".join("".join(body[i:i + g]) for i in range(0, n, g))
                    for tail in ("", " leaked", " Leaked today"):
                        for dest in EXTERNAL:
                            if not send(f"key {key}{tail}", dest)[0]:
                                bad.append((dest, key + tail))
    assert bad == [], bad[:5]


def test_r5_01_reviewer_reproductions_never_reach_the_wire():
    for q in ("AKIA ABCD EFGH IJKL MNO1", "ghp_" + " ".join(["abcd"] * 9)):
        result, sent = wire(q)
        assert result.status == REFUSED and sent == [], q


# --- R5-02 / R3-03: clean text leaves as written ------------------------------------------------------------------------
CLEAN_NON_ASCII = ["ｶﾀｶﾅ 検索", "ﻻ مرحبا",
                   "https://example.jp/ｶﾀｶﾅ/page", "ﬁle Ⅻ chapter", "a b",
                   "ＨＴＴＰ code 404", "café crème brûlée"]


@pytest.mark.parametrize("q", CLEAN_NON_ASCII)
def test_r5_02_clean_text_is_byte_identical_at_every_external_destination(q):
    for dest in ("EXTERNAL_AGENT", "EXTERNAL_MODEL"):
        assert send(q, dest) == (False, q), dest
    assert send(q, "WEB_SEARCH") == (False, q)
    result, sent = wire(q)
    assert sent == [" ".join(q.split())]


def test_r5_02_decomposed_accents_leave_unchanged():
    assert send("crème", "EXTERNAL_MODEL") == (False, "crème")


@pytest.mark.parametrize("q", ["card ４１１１ １１１１ １１１１ １１１１",
                               "ｐａｓｓｗｏｒｄ: Mango#2026!",
                               "mail ａ＠ｂ．ｃｏ today"])
def test_r5_02_compatibility_forms_that_hide_values_are_still_caught(q):
    for dest in EXTERNAL:
        refused, out = send(q, dest)
        assert refused or ("１" not in out and "＠" not in out and "Mango" not in out), (dest, out)


# --- R3-02 repair revised: the scope tag does not expose the scope id ---------------------------------------------------
def test_scope_tag_is_keyed_and_does_not_encode_the_scope_id():
    sid = "TASK-20261023-0123abcd"
    exact = "".join(chr(97 + (b >> 4)) + chr(97 + (b & 15)) for b in sid.encode("ascii"))
    out = TGateway().prepare("mail alice@example.in", requester="t", destination="EXTERNAL_MODEL", purpose="p",
                             scope=sid).text
    tag = vault.TOKEN.search(out).group(2)
    assert tag and len(tag) == 32 and tag not in exact and exact[:16] not in out
    assert vault.scope_tag(sid, b"k" * 32) != vault.scope_tag(sid, b"j" * 32)


def test_scope_tags_survive_a_persistent_restart(tmp_path):
    a = vault.PersistentVaultStore(tmp_path, key=b"\x01" * 32)
    s = a.open("S1", 600, requester="t")
    tok = s.token_for("CONTACT", "alice@example.in")
    a.save(s)
    b = vault.PersistentVaultStore(tmp_path, key=b"\x01" * 32)
    assert b.get("S1").restore(tok)[0] == "alice@example.in"


# --- LDEC-008: detector prefilters are necessary conditions -------------------------------------------------------------
def _corpus():
    from . import synth
    from .test_r6_review_repairs import LETTER_ONLY_CREDENTIALS, VALUE_BEFORE_LABEL_FORMS, VALUE_BEFORE_LABEL_WORDS
    texts = [t for _, t, _ in synth.positives()] + [t for _, t in synth.HARD_POSITIVES]
    texts += [t for _, t in synth.HELD_OUT_POSITIVES] + synth.BENIGN + synth.HARD_BENIGN + synth.NUMBER_BENIGN
    texts += LETTER_ONLY_CREDENTIALS + [f.format(value=v) for f in VALUE_BEFORE_LABEL_FORMS for v in VALUE_BEFORE_LABEL_WORDS]
    texts += ["P@ssword: Mango#2026!", "pa55word: x1y2z3", "pw Mango#2026", "PIN 4821", "cvc: 123", "one-time code 482913",
              "the PIN for the locker is 4821", "code 482913", "passport no A1234567", "acct no 12345678901",
              "a/c 123456789012", "OTP is 4 8 2 9 1 3", "flat 4B, MG road", "apt 12, 5th cross", "strictly confidential",
              "do not share", "AKIA TWII 6XUU IX2C IXU3", "ghp_" + "a" * 36, "glpat-" + "b" * 20, "sk-" + "aB" * 12]
    return texts


def test_hints_are_necessary():
    import uri_privacy.classify as C
    pairs = [(C._LABELLED, "labelled"), (C._PASSPORT, "passport"), (C._EMAIL, "@"), (C._SPACED_CODE, "spaced_code"),
             (C._KEY_SPLIT, "key_split"), (C._ACCOUNT, "account"), (C._STREET, "street"), (C._CONFIDENTIAL, "confidential")]
    hits = {h: 0 for _, h in pairs}
    for t in _corpus():
        f = C.fold(t)[0]
        for rx, h in pairs:
            if rx.search(f):
                hits[h] += 1
                assert (h == "@" and "@" in f) or (h != "@" and C._HINTS[h].search(f)), (h, t)
    assert all(hits.values()), hits                  # every pattern was exercised at least once
