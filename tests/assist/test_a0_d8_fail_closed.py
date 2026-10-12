"""Owner decision D8 (2026-10-11): Assist withholds field values by default (fail closed), in both layers.

A value is shared only for checkbox/radio state, search boxes and plainly named search/comment/message/subject/notes
fields. Every other value - including names no list anticipates - is withheld and masked in screenshots. Covers the
recurring R1-02 / R2-01 / R3-01 / R6-02 / R8-01 classes (unanticipated sensitive names)."""
import html
from collections import Counter

import pytest

from uri_assist import perception as PE
from uri_assist import redact as RD

from .test_a0_access_perception import dom_snapshot, stamp
from .test_a0_r1_review_regressions import _chromium

UNANTICIPATED = ["cv2", "CV2", "stripeapikey", "recovery_code", "aadhaarnumber", "fieldX7", "zz_value", "amount",
                 "dob", "accountHolder", "firstName", "email", "mobile", "company_code", "upiId", "vpa"]
SHARED = {"search": "hostel fees", "q": "exam dates", "comments": "please call after 5", "subject": "Fee query"}


@pytest.mark.parametrize("name", UNANTICIPATED)
def test_python_layer_withholds_any_unlisted_field(name):
    out = RD.redact_field({"type": "text", "name": name, "label": name, "value": "739-Secret"}, Counter())
    assert "value" not in out and out["has_value"] is True and out["sensitive"] is True
    assert out["withheld"] in ("sensitive", "not_shared")


@pytest.mark.parametrize("name, value", sorted(SHARED.items()))
def test_python_layer_shares_plainly_harmless_fields(name, value):
    out = RD.redact_field({"type": "text", "name": name, "label": name, "value": value}, Counter())
    assert out.get("withheld") is None and out["value"] == value


def test_python_layer_never_shares_a_sensitive_value_even_if_named_harmlessly():
    out = RD.redact_field({"type": "password", "name": "comments", "value": "Hunter2!"}, Counter())
    assert out["withheld"] == "sensitive" and "value" not in out


def test_withheld_values_are_located_for_screenshot_masking():
    snap = dom_snapshot(fields=[{"id": "x", "type": "text", "name": "cv2", "label": "CV2", "value": "739",
                                 "rect": {"x": 1, "y": 1, "w": 5, "h": 5}},
                                {"id": "y", "type": "text", "name": "zz", "label": "Other", "value": "v"}])
    obs = PE.normalise(snap, stamp())
    assert obs.unlocated_sensitive          # "zz" has a value and no rectangle: screenshots are refused
    snap["fields"][1]["rect"] = {"x": 9, "y": 9, "w": 5, "h": 5}
    assert not PE.normalise(snap, stamp()).unlocated_sensitive


def test_in_page_layer_withholds_unlisted_and_matches_python(tmp_path):
    rows = "".join(f'<label for="u{i}">{html.escape(n)}</label><input id="u{i}" name="{html.escape(n)}" value="739-S{i}">'
                   for i, n in enumerate(UNANTICIPATED))
    rows += "".join(f'<label for="s{i}">{n}</label><input id="s{i}" name="{n}" value="{html.escape(v)}">'
                    for i, (n, v) in enumerate(sorted(SHARED.items())))
    page = tmp_path / "d8.html"
    page.write_text(f"<!doctype html><html><body><form>{rows}</form></body></html>", encoding="utf-8")
    s = _chromium(str(page))["snapshot"]
    by_id = {f["id"]: f for f in s["fields"]}
    for i, n in enumerate(UNANTICIPATED):
        f = by_id[f"u{i}"]
        assert f["sensitive"] is True and f["value"] == "" and f["has_value"] is True, n
    for i, (n, v) in enumerate(sorted(SHARED.items())):
        assert by_id[f"s{i}"]["sensitive"] is False and by_id[f"s{i}"]["value"] == v, n
    assert all(f"739-S{i}" not in str(s) for i in range(len(UNANTICIPATED)))
    py = {f["id"]: f for f in PE.normalise(s, stamp()).fields}
    assert {k for k, f in by_id.items() if f["sensitive"]} == {k for k, f in py.items() if f.get("sensitive")}
    assert len(s["sensitive_rects"]) == len(UNANTICIPATED)
