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


@pytest.mark.parametrize("name", ["program/sitecustomize.py", "program/evil.pth", "program/extra.dll"])
def test_launch_check_refuses_a_file_added_after_verification(tree, tmp_path, name):
    """Review round 1, finding 5: a file dropped into program/ after start-up is refused at the next launch."""
    root, pin = tree
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    ei.verify_full()
    ei.launch_check()
    (root / "eng" / name).write_text("x")
    with pytest.raises(OfficeError) as e:
        ei.launch_check()
    assert e.value.code == "ENGINE_INTEGRITY"


def test_launch_check_rehashes_python_code(tree, tmp_path):
    root, pin0 = tree
    (root / "eng" / "program" / "uno.py").write_text("import x\n")
    entries = {rel: {"sha256": E.sha256_file(p), "size": p.stat().st_size}
               for rel, p in E._walk(root / "eng") if rel != "setup.msi"}
    pin = {**pin0, "manifest_root_sha256": E.manifest_root(entries), "manifest_files": len(entries)}
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state2", pin)
    ei.verify_full()
    p = root / "eng" / "program" / "uno.py"
    st = p.stat()
    p.write_text("import y\n")
    import os
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(OfficeError):
        ei.launch_check()


def test_signer_problems_rules():
    """Plan F11 signer check: only Valid files from an allowed signer, or the pinned unsigned files, pass."""
    from uri_office import engines as EN
    pin = {"signers_allowed": ["CN=The Document Foundation"], "unsigned_allowed": ["program/a.dll"]}
    ok = [{"path": "program/soffice.bin", "status": "Valid", "signer": "CN=The Document Foundation"},
          {"path": "program/a.dll", "status": "NotSigned", "signer": None}]
    assert EN.signer_problems(ok, pin) == []
    bad = [{"path": "program/b.dll", "status": "NotSigned", "signer": None},                 # newly unsigned
           {"path": "program/c.dll", "status": "Valid", "signer": "CN=Someone Else"},        # foreign signer
           {"path": "program/d.dll", "status": "HashMismatch", "signer": "CN=The Document Foundation"}]
    assert [b.split(":")[0] for b in EN.signer_problems(bad, pin)] == ["program/b.dll", "program/c.dll", "program/d.dll"]


def test_pinned_signers_are_recorded_for_libreoffice():
    from uri_office import engines as EN
    lo = EN.pins()["libreoffice"]
    assert "CN=The Document Foundation, O=The Document Foundation, L=Berlin, S=Berlin, C=DE" in lo["signers_allowed"]
    assert lo["signed_files"] >= 200 and all(p.startswith("program/") for p in lo["unsigned_allowed"])


def test_a_check_that_cannot_finish_leaves_the_engine_unavailable_not_checking(tree, tmp_path, monkeypatch):
    """Real-app run 2026-10-15 (R5-2): a MemoryError while hashing killed the start-up check and left the engine in
    'verifying' for the rest of the session. Now it ends 'unavailable' with ENGINE_CHECK_FAILED and can run again."""
    root, pin = tree
    ei = E.EngineIntegrity("libreoffice", tmp_path / "state", pin)
    real = E.sha256_file

    def boom(p):
        raise MemoryError()
    monkeypatch.setattr(E, "sha256_file", boom)
    with pytest.raises(OfficeError) as e:
        ei.verify_full()
    assert e.value.code == "ENGINE_CHECK_FAILED"
    assert ei.status()["state"] == "unavailable" and ei.status()["reason"] == "ENGINE_CHECK_FAILED"
    monkeypatch.setattr(E, "sha256_file", real)
    assert ei.verify_full()["ok"] and ei.status()["state"] == "ready"


def test_startup_check_records_an_unexpected_failure():
    from uri_office import engine_hub as H

    class FakeIntegrity:
        state, reason = "verifying", None

        class store:
            @staticmethod
            def exists():
                return False

        def verify_full(self):
            raise MemoryError()

    hub = H.EngineHub.__new__(H.EngineHub)
    hub.lo = type("LO", (), {"integrity": FakeIntegrity()})()
    hub._startup_check()
    assert (hub.lo.integrity.state, hub.lo.integrity.reason) == ("unavailable", "ENGINE_CHECK_FAILED")
