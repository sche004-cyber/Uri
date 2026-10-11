"""AC12 correction history (per workbook, consent, view/delete, retention, no cell values) and AC8 Google links."""
import json
import time

import pytest

from uri_office import google as G
from uri_office import history as Hm
from uri_office.errors import OfficeError
from uri_office.history import History, workbook_key

A = workbook_key("local", r"c:\data\a.xlsx")
B = workbook_key("local", r"c:\data\b.xlsx")
EV = {"kind": "uri_change_rejected", "sheet": "Pay", "cell": "C4", "change_id": "abc"}


def test_nothing_recorded_without_consent(tmp_path):
    h = History(tmp_path)
    assert h.record(A, 1, EV) is None
    assert h.view(A) == {"consented": False, "rows": []}
    assert not (tmp_path / "history" / A).exists()


def test_rows_store_what_and_why_never_values(tmp_path):
    h = History(tmp_path)
    h.set_consent(A, True)
    row = h.record(A, 3, dict(EV, value=95000, before={"v": 95000}, after={"v": 0}), reason="wrong column")
    assert set(row) == set(Hm.FIELDS)
    raw = (tmp_path / "history" / A / "rows.jsonl").read_text(encoding="utf-8")
    assert "95000" not in raw and "before" not in raw and "after" not in raw
    assert json.loads(raw)["reason"] == "wrong column"


def test_history_is_per_workbook(tmp_path):
    h = History(tmp_path)
    h.set_consent(A, True)
    h.record(A, 1, EV)
    assert h.view(B) == {"consented": False, "rows": []}
    assert h.recent(B) == []
    h.set_consent(B, True)
    assert h.recent(B) == [] and len(h.recent(A)) == 1


def test_view_delete_one_and_delete_all(tmp_path):
    h = History(tmp_path)
    h.set_consent(A, True)
    r1 = h.record(A, 1, EV)
    h.record(A, 2, dict(EV, kind="uri_change_edited_by_user"))
    h.delete(A, r1["id"])
    assert [r["kind"] for r in h.view(A)["rows"]] == ["uri_change_edited_by_user"]
    with pytest.raises(OfficeError):
        h.delete(A, r1["id"])
    h.delete_all(A)
    assert h.view(A) == {"consented": False, "rows": []}
    assert not (tmp_path / "history" / A).exists()


def test_turning_consent_off_deletes_everything(tmp_path):
    h = History(tmp_path)
    h.set_consent(A, True)
    h.record(A, 1, EV)
    h.set_consent(A, False)
    assert not (tmp_path / "history" / A).exists()


def test_retention_cap_rows_and_age(tmp_path, monkeypatch):
    h = History(tmp_path)
    h.set_consent(A, True)
    monkeypatch.setattr(Hm, "MAX_ROWS", 5)
    for i in range(8):
        h.record(A, i, EV)
    assert [r["version"] for r in h.view(A)["rows"]] == [3, 4, 5, 6, 7]
    old = time.time() - Hm.MAX_AGE_S - 10
    monkeypatch.setattr(Hm.time, "time", lambda: old)
    h2 = History(tmp_path / "x")
    h2.set_consent(A, True)
    h2.record(A, 1, EV)
    monkeypatch.undo()
    h2.record(A, 2, EV)
    assert [r["version"] for r in h2.view(A)["rows"]] == [2]


def test_bad_key_and_kind_refused(tmp_path):
    h = History(tmp_path)
    with pytest.raises(OfficeError):
        h.view("../../etc")
    h.set_consent(A, True)
    with pytest.raises(OfficeError):
        h.record(A, 1, {"kind": "anything"})


def test_graphify_pointer_shape_is_not_wired():
    assert History.pointer(A) == {"registry": "office_corrections", "lookup_key": A}


# ---- AC8 Google links --------------------------------------------------------------------------------------------
ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-ab"


@pytest.mark.parametrize("url", [f"https://docs.google.com/spreadsheets/d/{ID}",
                                 f"https://docs.google.com/spreadsheets/d/{ID}/edit#gid=0",
                                 f"https://docs.google.com/spreadsheets/d/{ID}/edit?usp=sharing",
                                 f"  https://docs.google.com/spreadsheets/d/{ID}/  "])
def test_sheet_links_give_only_the_id(url):
    assert G.parse_link(url) == ID


@pytest.mark.parametrize("url", [
    f"http://docs.google.com/spreadsheets/d/{ID}",                      # not https
    f"https://docs.google.com.evil.example/spreadsheets/d/{ID}",       # look-alike host
    f"https://evil.example/?u=https://docs.google.com/spreadsheets/d/{ID}",
    f"https://docs.google.com/document/d/{ID}",                         # a Doc, not a Sheet
    f"https://drive.google.com/file/d/{ID}",
    f"https://user@docs.google.com/spreadsheets/d/{ID}",
    "https://docs.google.com/spreadsheets/d/short",
    f"https://docs.google.com/spreadsheets/d/{ID}/edit space",
    "file:///C:/x.xlsx", "", None, 123])
def test_other_links_refused(url):
    with pytest.raises(OfficeError) as e:
        G.parse_link(url)
    assert e.value.code == "NOT_A_SHEETS_LINK"


class _Exec:
    def __init__(self, v):
        self.v = v

    def execute(self):
        return self.v


class FakeDrive:
    def __init__(self, mime):
        self.mime, self.calls = mime, []

    def files(self):
        return self

    def get(self, **kw):
        self.calls.append(kw)
        return _Exec({"id": kw["fileId"], "name": "Budget", "mimeType": self.mime})


def test_non_sheet_file_refused_before_content_read(tmp_path):
    drive = FakeDrive("application/vnd.google-apps.document")
    gs = G.GoogleSheets(tmp_path, None, services=lambda: (None, drive, set()))
    with pytest.raises(OfficeError) as e:
        gs.check_sheet(ID)
    assert e.value.code == "NOT_A_GOOGLE_SHEET"
    assert drive.calls == [{"fileId": ID, "fields": "id,name,mimeType", "supportsAllDrives": True}]


def test_in_place_write_needs_the_owner_gated_permission(tmp_path):
    gs = G.GoogleSheets(tmp_path, None, services=lambda: (None, None, {"https://www.googleapis.com/auth/drive.file"}))
    with pytest.raises(OfficeError) as e:
        gs.apply(ID, {"edits": [{"sheet": "S", "cell": "A1", "before": {}, "after": {"v": 1}}], "struct_ops": []})
    assert e.value.code == "PERMISSION_NOT_GRANTED"
    assert gs.status() == {"connected": True, "can_edit_existing": False, "missing_permission": G.SHEETS_SCOPE}


def test_not_connected_without_token(tmp_path):
    assert G.GoogleSheets(tmp_path, None).status() == {"connected": False, "code": "GOOGLE_NOT_CONNECTED"}
