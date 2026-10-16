"""OD-R1 (2026-10-16): folders the owner adds (any drive), explicit, folder-scoped, remembered, revocable."""
import os
import subprocess

import pytest
from openpyxl import Workbook

from uri_office.errors import OfficeError
from uri_office.grants import Grants, check_folder_shape
from uri_office.service import Office


def book(path):
    wb = Workbook()
    wb.active["A1"] = 1
    wb.save(path)
    return path


@pytest.mark.parametrize("raw", ["D:\\", "D:", "d:/", "C:\\Windows\\System32", "C:\\Program Files\\App",
                                 "\\\\server\\share", "D:\\a\\..\\b", "relative\\folder", "D:\\con\\x", ""])
def test_folder_shape_refusals(raw, monkeypatch):
    monkeypatch.setenv("SystemRoot", "C:\\Windows")
    monkeypatch.setenv("ProgramFiles", "C:\\Program Files")
    with pytest.raises(OfficeError):
        check_folder_shape(raw, "nt")


def test_folder_shape_accepts_a_folder_on_another_drive():
    assert check_folder_shape("D:\\Work\\Budgets\\", "nt") == "D:\\Work\\Budgets"


def test_an_added_folder_allows_files_there_and_survives_a_restart(tmp_path):
    home, other = tmp_path / "home", tmp_path / "other"
    home.mkdir()
    other.mkdir()
    f = book(other / "b.xlsx")
    store = tmp_path / "state" / "folders.json"
    store.parent.mkdir()
    g = Grants([home], folders_file=store)
    with pytest.raises(OfficeError) as e:
        g.grant_open(str(f))
    assert e.value.code == "PATH_REFUSED"
    assert g.add_folder(str(other))["added"] is True
    assert g.grant_open(str(f)).path == f
    g2 = Grants([home], folders_file=store)                 # restart: remembered
    assert [x["path"] for x in g2.folders() if x["kind"] == "added"] == [str(other)]
    assert g2.grant_open(str(f))


def test_removing_is_refused_while_a_file_is_open_then_revokes(tmp_path):
    home, other = tmp_path / "home", tmp_path / "other"
    home.mkdir()
    other.mkdir()
    f = book(other / "b.xlsx")
    g = Grants([home], folders_file=tmp_path / "folders.json")
    g.add_folder(str(other))
    gr = g.grant_open(str(f))
    with pytest.raises(OfficeError) as e:
        g.remove_folder(str(other))
    assert e.value.code == "FOLDER_IN_USE"
    g.revoke(gr.grant_id)                                  # the file was closed
    assert g.remove_folder(str(other))["removed"] is True
    with pytest.raises(OfficeError):
        g.grant_open(str(f))
    with pytest.raises(OfficeError) as e:                  # the default folder cannot be removed
        g.remove_folder(str(home))
    assert e.value.code == "FOLDER_NOT_ADDED"


def test_a_folder_inside_an_allowed_one_is_already_allowed_and_a_parent_replaces_children(tmp_path):
    home = tmp_path / "home"
    (home / "sub").mkdir(parents=True)
    a, b = tmp_path / "x" / "a", tmp_path / "x" / "b"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    g = Grants([home], folders_file=tmp_path / "folders.json")
    assert g.add_folder(str(home / "sub"))["already_allowed"] is True
    g.add_folder(str(a))
    g.add_folder(str(b))
    g.add_folder(str(tmp_path / "x"))
    assert [x["path"] for x in g.folders() if x["kind"] == "added"] == [str(tmp_path / "x")]


@pytest.mark.skipif(os.name != "nt", reason="directory junctions are Windows-only")
def test_a_junction_is_not_followed(tmp_path):
    target, link = tmp_path / "target", tmp_path / "link"
    target.mkdir()
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    g = Grants([tmp_path / "nowhere"], folders_file=tmp_path / "folders.json")
    with pytest.raises(OfficeError) as e:
        g.add_folder(str(link))
    assert "junction" in e.value.detail


def test_a_damaged_list_grants_nothing_extra(tmp_path):
    store = tmp_path / "folders.json"
    store.write_text("{not json", encoding="utf-8")
    g = Grants([tmp_path / "home"], folders_file=store)
    assert [x for x in g.folders() if x["kind"] == "added"] == []


def test_service_folders_routes_and_enforcement(tmp_path):
    home, other = tmp_path / "home", tmp_path / "other"
    home.mkdir()
    other.mkdir()
    f = book(other / "b.xlsx")
    o = Office(tmp_path / "state", allowed_roots=[home])
    with pytest.raises(OfficeError):
        o.open_local(str(f))
    o.grants.add_folder(str(other))
    wid = o.open_local(str(f))["workbook_id"]
    with pytest.raises(OfficeError) as e:
        o.grants.remove_folder(str(other))
    assert e.value.code == "FOLDER_IN_USE"
    o.close(wid)
    assert o.grants.remove_folder(str(other))["removed"] is True
    assert (tmp_path / "state" / "folders.json").exists()
