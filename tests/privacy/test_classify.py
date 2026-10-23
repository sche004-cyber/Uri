"""AC-1: risk-aware classification on synthetic data (tests/privacy/synth.py). Thresholds from the plan."""
from collections import Counter

import pytest

from uri_privacy.classify import CREDENTIAL, FINANCIAL, GOV_ID, CONTACT, ADDRESS, PERSON, classify, iban_ok, verhoeff

from . import synth


def _recall(items):
    hit, n = Counter(), Counter()
    for cat, text, *_ in items:
        n[cat] += 1
        hit[cat] += cat in classify(text).categories()
    return {c: hit[c] / n[c] for c in n}


def test_recall_core_corpus_meets_thresholds():
    r = _recall(synth.positives())
    for cat in (CREDENTIAL, GOV_ID, FINANCIAL):
        assert r[cat] >= 0.98, (cat, r[cat])
    assert r[CONTACT] >= 0.95


def test_recall_hard_and_held_out_sets():
    items = [(c, t) for c, t in synth.HARD_POSITIVES + synth.HELD_OUT_POSITIVES]
    misses = [(c, t) for c, t in items if c not in classify(t).categories()]
    # Documented limitation: an e-mail written out in words ("x dot y at z dot in") is not detected.
    assert misses == [("CONTACT", "asha dot rao at example dot in")]


def test_false_positive_rate_on_benign_text():
    benign = synth.BENIGN + synth.HARD_BENIGN + synth.HELD_OUT_BENIGN
    fps = [t for t in benign if classify(t).categories()]
    assert len(fps) / len(benign) <= 0.02, fps
    # Documented LOW-tier false friend: the word "confidential" in an unrelated sense.
    assert fps == ["The confidential interval is 95% (statistics)."]


@pytest.mark.parametrize("text", [
    "Asha Rao and Ravi Iyer reviewed the draft.",          # ordinary names are not sensitive by default
    "IMEI 490154203237518 is on the box",                  # Luhn-valid device id
    "commit 9f3a1c2b7d4e5f60718293a4b5c6d7e8f9012345",    # hash named as such
    "Order 234567890123 shipped",                          # 12 digits without Aadhaar context
    "error code: 404", "the zip code field is required",
])
def test_ordinary_text_is_not_flagged(text):
    assert not classify(text).categories()


def test_postal_code_is_an_address_not_a_credential():
    assert classify("zip code 560011").categories() == {ADDRESS: 1}
    assert classify("status code 482913").categories() == {}


def test_protected_terms_mark_people_the_user_protects():
    c = classify("Ask Meera Nair about the lease", protected_terms=["Meera Nair"])
    assert c.categories() == {PERSON: 1}
    assert not classify("Ask Meera Nair about the lease").categories()


def test_checksums():
    assert verhoeff("2363") and not verhoeff("2364")
    assert iban_ok("GB82 WEST 1234 5698 7654 32") and not iban_ok("GB83 WEST 1234 5698 7654 32")


def test_assist_credential_rules_are_reused():
    # The URL-credential and API-key rules come from uri_assist.redact (one credential detector in URI).
    assert classify("https://u:hunter22@host.test/x").credential_kinds
    assert classify("sk-abcdefghijklmnopqrstuvwx").credential_kinds["api_key"] == 1


def test_postal_and_street_addresses():
    assert ADDRESS in classify("Flat 12, 4th Cross Road, Indiranagar").categories()
    assert ADDRESS in classify("Kochi, Ernakulam - 682001").categories()


def test_non_text_input_is_rejected():
    with pytest.raises(TypeError):
        classify(b"bytes")
