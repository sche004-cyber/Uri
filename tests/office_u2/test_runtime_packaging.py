"""B4/O2-RT-1: a materialized runtime carries URI Office and refuses a venv that lacks Office's declared modules."""
import sys
from pathlib import Path

import pytest

from scripts import oi_materialize_test_runtime as M

ROOT = Path(__file__).resolve().parents[2]


def test_office_paths_are_materialized():
    for p in ("uri_office", "uri_devices", "scripts/run_uri_office_service.py"):
        assert p in M.OI_PATHS and (ROOT / p).exists()
    for t in ("tests/office", "tests/office_u2", "tests/devices"):
        assert t in M.OI_PATHS and t in M.TEST_PATHS


def test_runtime_modules_are_declared_requirements():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    names = {"pypdf": "pypdf", "docx": "python-docx", "pptx": "python-pptx", "openpyxl": "openpyxl",
             "lxml": "python-docx"}  # lxml arrives as a dependency of python-docx and python-pptx
    for m in M.RUNTIME_MODULES:
        assert names[m] in req, m


def test_missing_modules_reports_what_the_interpreter_cannot_import(monkeypatch):
    monkeypatch.setattr(M, "venv_python", lambda venv: Path(sys.executable))
    assert M.missing_modules(Path("unused"), ("json", "uri_no_such_module_xyz")) == ["uri_no_such_module_xyz"]


def test_only_wheel_files_are_installed(tmp_path):
    bad = tmp_path / "pypdf.tar.gz"
    bad.write_text("x")
    with pytest.raises(SystemExit) as e:
        M.install_wheels(tmp_path, [str(bad)])
    assert str(e.value) == "WHEEL_REFUSED:pypdf.tar.gz"


def test_a_wheel_must_be_a_declared_requirement(tmp_path):
    """Codex review R1-3: an unrelated wheel is refused before anything is installed."""
    other = tmp_path / "evil_pkg-1.0-py3-none-any.whl"
    other.write_bytes(b"PK")
    with pytest.raises(SystemExit) as e:
        M.install_wheels(tmp_path, [str(other)], declared=M.declared_requirements())
    assert str(e.value) == "WHEEL_NOT_DECLARED:evil_pkg-1.0-py3-none-any.whl"


def test_declared_requirements_reads_names_only():
    names = M.declared_requirements()
    assert {"pypdf", "python-docx", "python-pptx", "openpyxl"} <= set(names)
    assert M._dist("Python_Docx") == "python-docx"


def test_a_wheel_version_outside_the_declared_specifier_is_refused(tmp_path):
    """Codex review R2-3: requirements.txt says pypdf>=5.0, so a pypdf 1.0 wheel is refused."""
    old = tmp_path / "pypdf-1.0-py3-none-any.whl"
    old.write_bytes(b"PK")
    with pytest.raises(SystemExit) as e:
        M.install_wheels(tmp_path, [str(old)], declared=M.declared_requirements())
    assert str(e.value) == "WHEEL_VERSION_NOT_DECLARED:pypdf-1.0-py3-none-any.whl"
    assert M._wheel_name_version("pypdf-6.19.0-1-py3-none-any.whl") == ("pypdf", "6.19.0")
    for bad in ("pypdf.whl", "pypdf-6.19.0.whl"):
        with pytest.raises(SystemExit):
            M._wheel_name_version(bad)


def test_a_prerelease_wheel_is_refused(tmp_path):
    """Codex review R3-1: pypdf>=5.0 does not opt into prereleases, so 6.0rc1 is refused."""
    rc = tmp_path / "pypdf-6.0rc1-py3-none-any.whl"
    rc.write_bytes(b"PK")
    with pytest.raises(SystemExit) as e:
        M.install_wheels(tmp_path, [str(rc)], declared=M.declared_requirements())
    assert str(e.value) == "WHEEL_VERSION_NOT_DECLARED:pypdf-6.0rc1-py3-none-any.whl"
