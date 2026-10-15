"""AC-O2-6 and AC-O2-19: engine pin, manifest checks, worker script pins and run copies (fake engine tree)."""
import json
import os

import pytest

from uri_office import engines as E
from uri_office.errors import OfficeError


def make_tree(root):
    prog = root / "eng" / "program"
    prog.mkdir(parents=True)
    (prog / "soffice.bin").write_bytes(b"BIN")
    (prog / "soffice.com").write_bytes(b"COM")
    (prog / "lib.dll").write_bytes(b"DLL")
    (root / "eng" / "share").mkdir()
    (root / "eng" / "share" / "conf.xcd").write_text("x")
    (root / "eng" / "setup.msi").write_bytes(b"MSI")     # excluded like the admin-image MSI
    entries = {}
    for rel, p in E._walk(root / "eng"):
        if rel != "setup.msi":
            entries[rel] = {"sha256": E.sha256_file(p), "size": p.stat().st_size}
    return {"dir": "eng", "version": "t", "soffice_bin_sha256": E.sha256_file(prog / "soffice.bin"),
            "manifest_root_sha256": E.manifest_root(entries), "manifest_files": len(entries),
            "installer_name": "setup.msi"}


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.setenv("URI_ENGINES_ROOT", str(tmp_path))
    return tmp_path, make_tree(tmp_path)


def test_full_verify_then_fast_and_launch_checks(tree, tmp_path):
    root, pin = tree
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    with pytest.raises(OfficeError) as e:
        ei.launch_check()
    assert e.value.code == "ENGINE_UNAVAILABLE"                  # never run before it is verified
    assert ei.verify_full()["ok"]
    ei.fast_check()
    ei.launch_check()
    assert ei.status()["state"] == "ready"


@pytest.mark.parametrize("rel", ["program/lib.dll", "program/soffice.bin", "share/conf.xcd"])
def test_one_changed_byte_is_refused(tree, tmp_path, rel):
    root, pin = tree
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    ei.verify_full()
    p = root / "eng" / rel
    data = bytearray(p.read_bytes())
    data[0] ^= 1
    p.write_bytes(bytes(data))
    with pytest.raises(OfficeError) as e:
        ei.verify_full()
    assert e.value.code == "ENGINE_INTEGRITY" and ei.status()["state"] == "unavailable"


def test_launch_check_catches_same_size_same_mtime_swap(tree, tmp_path):
    root, pin = tree
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    ei.verify_full()
    p = root / "eng" / "program" / "lib.dll"
    st = p.stat()
    p.write_bytes(b"EVL")
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    ei.fast_check()                                              # list, size and time look unchanged
    with pytest.raises(OfficeError) as e:
        ei.launch_check()                                        # the hash catches it
    assert e.value.code == "ENGINE_INTEGRITY"


def test_added_or_missing_file_fails_fast_check(tree, tmp_path):
    root, pin = tree
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    ei.verify_full()
    (root / "eng" / "program" / "extra.dll").write_bytes(b"X")
    with pytest.raises(OfficeError):
        ei.fast_check()


def test_tampered_stored_manifest_is_refused(tree, tmp_path):
    root, pin = tree
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    ei.verify_full()
    data = json.loads(ei.store.read_text())
    data["files"]["program/lib.dll"]["sha256"] = "0" * 64
    ei.store.write_text(json.dumps(data))
    fresh = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    with pytest.raises(OfficeError) as e:
        fresh.launch_check()
    assert e.value.code == "ENGINE_INTEGRITY"


def test_missing_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("URI_ENGINES_ROOT", str(tmp_path))
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", {"dir": "none", "manifest_root_sha256": "x",
                                                                "manifest_files": 1, "soffice_bin_sha256": "x"})
    with pytest.raises(OfficeError) as e:
        ei.verify_full()
    assert e.value.code == "ENGINE_MISSING"


def test_worker_pins_match_the_scripts():
    assert E.pins()["workers"] == E.worker_hashes(), "run: python -m uri_office.engines pin-workers"


def test_run_copy_is_exact_and_refuses_a_changed_script(tmp_path, monkeypatch):
    p = E.run_copy("pdf_text.py", tmp_path)
    assert p.parent == tmp_path / "run" and p.read_bytes() == (E.WORKERS_DIR / "pdf_text.py").read_bytes()
    monkeypatch.setattr(E, "pins", lambda: {"workers": {"pdf_text.py": "0" * 64}})
    with pytest.raises(OfficeError) as e:
        E.run_copy("pdf_text.py", tmp_path)
    assert e.value.code == "WORKER_INTEGRITY"
    with pytest.raises(OfficeError):
        E.run_copy("not_a_worker.py", tmp_path)
