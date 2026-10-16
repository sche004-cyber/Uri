"""AC7 path rule. Shape rules for BOTH platforms run on every OS (pure); filesystem rules run on the current OS."""
import os
import json
import subprocess
from pathlib import Path

import pytest

from uri_office.errors import OfficeError
from uri_office.grants import Grants, check_shape

WIN_OK = [r"C:\Users\me\Book.xlsx", "D:/data/book.XLSX", r"c:\a b\c.xlsx"]
WIN_BAD = {
    "relative": r"Book.xlsx",
    "drive_relative": r"C:Book.xlsx",
    "rooted_no_drive": r"\Users\me\Book.xlsx",
    "unc": r"\\server\share\Book.xlsx",
    "unc_forward": "//server/share/Book.xlsx",
    "device_ns": r"\\.\C:\Book.xlsx",
    "extended": r"\\?\C:\Book.xlsx",
    "dotdot": r"C:\Users\..\Book.xlsx",
    "dot": r"C:\Users\.\Book.xlsx",
    "ads": r"C:\Users\Book.xlsx:hidden",
    "reserved_con": r"C:\Users\CON\Book.xlsx",
    "reserved_file": r"C:\Users\nul.xlsx",
    "reserved_com": r"C:\COM1\Book.xlsx",
    "trailing_dot": r"C:\Users\me.\Book.xlsx",
    "trailing_space": "C:\\Users\\me \\Book.xlsx",
    "not_xlsx": r"C:\Users\Book.xlsm",
    "nul_byte": "C:\\Users\\Bo\x00ok.xlsx",
    "posix_style": "/home/me/Book.xlsx",
}
POSIX_OK = ["/home/me/Book.xlsx", "/tmp/a b/c.XLSX", "/media/usb/book.xlsx"]
POSIX_BAD = {
    "relative": "Book.xlsx",
    "dot_relative": "./Book.xlsx",
    "network": "//server/share/Book.xlsx",
    "dotdot": "/home/me/../Book.xlsx",
    "dot": "/home/./Book.xlsx",
    "dev": "/dev/sda.xlsx",
    "proc": "/proc/self/fd/3.xlsx",
    "sys": "/sys/kernel/x.xlsx",
    "run": "/run/user/1000/x.xlsx",
    "not_xlsx": "/home/me/Book.csv",
    "nul_byte": "/home/me/Bo\x00ok.xlsx",
    "windows_style": r"C:\Users\me\Book.xlsx",
}


@pytest.mark.parametrize("p", WIN_OK)
def test_windows_shape_accepts_absolute_drive_paths(p):
    assert check_shape(p, "nt") == p


@pytest.mark.parametrize("name", sorted(WIN_BAD))
def test_windows_shape_refuses(name):
    with pytest.raises(OfficeError) as e:
        check_shape(WIN_BAD[name], "nt")
    assert e.value.code == "PATH_REFUSED"


@pytest.mark.parametrize("p", POSIX_OK)
def test_posix_shape_accepts_absolute_paths(p):
    assert check_shape(p, "posix") == p


@pytest.mark.parametrize("name", sorted(POSIX_BAD))
def test_posix_shape_refuses(name):
    with pytest.raises(OfficeError) as e:
        check_shape(POSIX_BAD[name], "posix")
    assert e.value.code == "PATH_REFUSED"


@pytest.mark.parametrize("raw", [None, "", 5, "x" * 2000 + ".xlsx"])
def test_non_paths_refused_on_both(raw):
    for flavor in ("nt", "posix"):
        with pytest.raises(OfficeError):
            check_shape(raw, flavor)


# ---- filesystem rules on the current platform --------------------------------------------------------------------
def _book(d, name="book.xlsx"):
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(b"PK\x03\x04")
    return p


def test_open_inside_root(tmp_path):
    p = _book(tmp_path / "root")
    g = Grants([tmp_path / "root"]).grant_open(str(p))
    assert g.kind == "open" and g.path == p


def test_open_outside_root_refused(tmp_path):
    p = _book(tmp_path / "other")
    (tmp_path / "root").mkdir()
    with pytest.raises(OfficeError) as e:
        Grants([tmp_path / "root"]).grant_open(str(p))
    assert "outside" in e.value.detail


def test_sibling_prefix_is_not_inside(tmp_path):
    (tmp_path / "root").mkdir()
    p = _book(tmp_path / "root-evil")
    with pytest.raises(OfficeError):
        Grants([tmp_path / "root"]).grant_open(str(p))


def test_no_roots_refuses_everything(tmp_path):
    p = _book(tmp_path / "root")
    with pytest.raises(OfficeError) as e:
        Grants([]).grant_open(str(p))
    assert "no folders" in e.value.detail


def test_missing_root_is_ignored_and_fails_closed(tmp_path):
    p = _book(tmp_path / "root")
    with pytest.raises(OfficeError):
        Grants([tmp_path / "does-not-exist"]).grant_open(str(p))


def test_missing_file_and_directory_refused(tmp_path):
    root = tmp_path / "root"
    (root / "dir.xlsx").mkdir(parents=True)
    g = Grants([root])
    for p in (root / "missing.xlsx", root / "dir.xlsx"):
        with pytest.raises(OfficeError) as e:
            g.grant_open(str(p))
        assert e.value.code == "PATH_REFUSED"


def test_link_resolving_outside_root_refused(tmp_path):
    outside = _book(tmp_path / "outside")
    root = tmp_path / "root"
    root.mkdir()
    link = root / "link.xlsx"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        # Windows without the symlink privilege: use a directory junction, which needs none.
        import subprocess
        jdir = root / "jdir"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(jdir), str(outside.parent)], check=True, capture_output=True)
        link = jdir / outside.name
    with pytest.raises(OfficeError) as e:
        Grants([root]).grant_open(str(link))
    assert e.value.code == "PATH_REFUSED"


def test_save_as_inside_root_only(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "other").mkdir()
    g = Grants([root])
    assert g.grant_save_as(str(root / "new.xlsx")).kind == "save_as"
    with pytest.raises(OfficeError):
        g.grant_save_as(str(tmp_path / "other" / "new.xlsx"))
    with pytest.raises(OfficeError):
        g.grant_save_as(str(root / "nofolder" / "new.xlsx"))


def test_grant_kinds_are_not_interchangeable(tmp_path):
    p = _book(tmp_path / "root")
    g = Grants([tmp_path / "root"])
    gid = g.grant_open(str(p)).grant_id
    with pytest.raises(OfficeError) as e:
        g.get(gid, "save_as")
    assert e.value.code == "NO_GRANT"


@pytest.mark.parametrize("contents", ["[]", "null", '{"folders": null}'])
def test_damaged_folder_list_grants_no_added_roots(tmp_path, contents):
    folders_file = tmp_path / "folders.json"
    folders_file.write_text(contents, encoding="utf-8")
    grants = Grants([], folders_file)
    assert grants.folders() == []
    assert grants.roots == []


def _directory_link(link, target):
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)


def test_added_root_is_rechecked_after_its_realpath_changes(monkeypatch):
    grants = Grants([])
    added = str(Path.home())
    destination = str(Path.home().parent)
    grants.added = [added]
    realpath = os.path.realpath
    monkeypatch.setattr(os.path, "realpath", lambda p: destination if str(p) == added else realpath(p))
    assert grants.roots == []


@pytest.mark.parametrize("when", ["restored", "replaced"])
def test_added_folder_link_never_expands_allowed_roots(tmp_path, when):
    outside = _book(tmp_path / "outside")
    added = tmp_path / "chosen"
    folders_file = tmp_path / "folders.json"
    if when == "restored":
        _directory_link(added, outside.parent)
        folders_file.write_text(json.dumps({"folders": [str(added)]}), encoding="utf-8")
        grants = Grants([], folders_file)
    else:
        added.mkdir()
        grants = Grants([], folders_file)
        grants.add_folder(str(added))
        added.rmdir()
        _directory_link(added, outside.parent)
    assert os.path.normcase(os.path.abspath(str(outside.parent))) not in grants.roots
    with pytest.raises(OfficeError) as error:
        grants.grant_open(str(outside))
    assert error.value.code == "PATH_REFUSED"
    with pytest.raises(OfficeError) as error:
        grants.grant_save_as(str(outside.parent / "new.xlsx"))
    assert error.value.code == "PATH_REFUSED"
