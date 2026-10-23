"""FCV-11: the guarded rollback inspects a checkpoint first, refuses known-vulnerable security files by default and
applies only the owner-authorized security transitions on explicit secure recovery."""
import hashlib
from pathlib import Path
import uuid
import zipfile

import pytest

from scripts import fcv_guarded_rollback as G
from scripts import phase1_offline_rollback as R

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "work/c1/checkpoints/final-closure-20261005-phase1.zip"
pytestmark = pytest.mark.skipif(not FROZEN.is_file(), reason="frozen checkpoint fixture not installed: run scripts/fcv_install_phase1_fixtures.py (FCV-09)")
FROZEN_SHA = "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7"
SERVER, FETCH = "uri_core/app/server.py", "uri_core/tools/fetch_url.py"


def fresh():
    return ROOT / "work/c1" / ("rollback_" + uuid.uuid4().hex)


def derived(mutate):
    with zipfile.ZipFile(FROZEN) as z:
        members = [[i.filename, z.read(i)] for i in z.infolist()]
    out = ROOT / "work/c1/checkpoints" / ("negative_" + uuid.uuid4().hex + ".zip")
    with zipfile.ZipFile(out, "w") as a:
        for n, d in mutate(members):
            a.writestr(n, d)
    return out, hashlib.sha256(out.read_bytes()).hexdigest()


def replace(path, data):
    return lambda m: [x for x in m if x[0] != path] + [[path, data]]


def test_the_exact_checkpoint_is_inspected_as_vulnerable_without_writing():
    before = set((ROOT / "work/c1").iterdir())
    report = G.inspect(FROZEN, FROZEN_SHA)
    assert report["safe"] is False and report["unsafe"] == [SERVER, FETCH]
    assert report["security_files"][SERVER]["state"] == "VULNERABLE"
    assert report["security_files"][FETCH]["origin"] == "e8e3b65 base"
    assert set((ROOT / "work/c1").iterdir()) == before


def test_default_rollback_refuses_before_writing():
    dest = fresh()
    with pytest.raises(G.RollbackRefused, match="UNSAFE_ROLLBACK_REFUSED"):
        G.rollback(FROZEN, FROZEN_SHA, dest)
    assert not dest.exists()


def test_cli_default_warns_and_names_the_secure_procedure(capsys):
    before = set((ROOT / "work/c1").iterdir())
    assert G.main(["--archive", str(FROZEN), "--sha256", FROZEN_SHA]) == 2
    err = capsys.readouterr().err
    assert "URI ROLLBACK REFUSED" in err and "SSRF-1" in err and "GRAPHIFY-LEAK-1" in err
    assert "--secure-recovery" in err and "Nothing was written" in err
    assert set((ROOT / "work/c1").iterdir()) == before


def test_cli_inspect_exit_code_marks_an_unsafe_checkpoint():
    assert G.main(["--archive", str(FROZEN), "--sha256", FROZEN_SHA, "--inspect"]) == 3


def test_secure_recovery_restores_every_file_with_the_authorized_security_versions():
    dest = fresh()
    out = G.rollback(FROZEN, FROZEN_SHA, dest, secure_recovery=True)
    assert out["rollback"]["status"] == "OFFLINE_SOURCE_OVERLAY_RECOVERY_PASSED"
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == FROZEN_SHA          # checkpoint never modified
    for path, spec in G.SECURITY_FILES.items():
        assert hashlib.sha256((dest / path).read_bytes()).hexdigest() == spec["secure"]
        assert out["security_transitions"][path]["after_sha256"] == spec["secure"]
    with zipfile.ZipFile(FROZEN) as z:
        for n in z.namelist():
            if n not in R.CHECKPOINT_METADATA and n not in G.SECURITY_FILES and n not in G.SUPPORT_FILES:
                assert (dest / n).read_bytes() == z.read(n), n
    assert (dest / "secure-recovery-evidence.json").is_file() and not out["inspection"]["safe"]


def test_secure_recovery_only_for_the_checkpoint_the_owner_record_names():
    z, sha = derived(lambda m: m + [["docs/extra.md", b"x\n"]])
    dest = fresh()
    with pytest.raises(G.RollbackRefused, match="SECURE_RECOVERY_NOT_AUTHORIZED"):
        G.rollback(z, sha, dest, secure_recovery=True)
    assert not dest.exists()


@pytest.mark.parametrize("field,value", [("AUTHORITY_DECISION", "OTHER"), ("SECURITY_PATCH_SHA256", "0" * 64)])
def test_a_changed_authority_or_patch_pin_refuses_secure_recovery(monkeypatch, field, value):
    monkeypatch.setattr(G, field, value)
    dest = fresh()
    with pytest.raises(G.RollbackRefused):
        G.rollback(FROZEN, FROZEN_SHA, dest, secure_recovery=True)
    assert not dest.exists()


def test_a_changed_patch_file_refuses_secure_recovery(monkeypatch, tmp_path):
    bad = tmp_path / "p.patch"
    bad.write_bytes((ROOT / G.SECURITY_PATCH).read_bytes() + b"\n")
    monkeypatch.setattr(G, "SECURITY_PATCH", str(bad))        # absolute, so ROOT / SECURITY_PATCH is this file
    with pytest.raises(G.RollbackRefused, match="SECURITY_PATCH_CHANGED"):
        G._secure_bytes(G._restored_security_files(FROZEN.resolve()))


def test_an_unrecognised_security_file_is_refused_even_with_secure_recovery():
    z, sha = derived(replace(SERVER, b"# not a known version\n"))
    assert G.inspect(z, sha)["security_files"][SERVER]["state"] == "UNKNOWN"
    for secure in (False, True):
        dest = fresh()
        with pytest.raises(G.RollbackRefused):
            G.rollback(z, sha, dest, secure_recovery=secure)
        assert not dest.exists()


def test_a_checkpoint_that_already_holds_the_secure_versions_restores_by_default():
    secure = {p: (ROOT / p).read_bytes() for p in G.SECURITY_FILES}
    assert all(hashlib.sha256(d).hexdigest() == G.SECURITY_FILES[p]["secure"] for p, d in secure.items())
    z, sha = derived(lambda m: replace(FETCH, secure[FETCH])(replace(SERVER, secure[SERVER])(m)))
    dest = fresh()
    out = G.rollback(z, sha, dest)
    assert out["inspection"]["safe"] and out["security_transitions"] == {}
    assert (dest / FETCH).read_bytes() == secure[FETCH]


# ------------------------------------------------------------------ D08 (OPEN-06): the secured tree imports its fetch tool

def test_d08_secure_recovery_tree_imports_the_secure_fetch_tool():
    import subprocess, sys
    dest = fresh()
    out = G.rollback(FROZEN, FROZEN_SHA, dest, secure_recovery=True)
    assert out["support_files"] == sorted(G.SUPPORT_FILES)
    for path, digest in G.SUPPORT_FILES.items():
        assert hashlib.sha256((dest / path).read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(FROZEN) as z:
        assert not any(n.startswith("uri_web/") for n in z.namelist())     # the checkpoint itself has no uri_web
    code = "import sys; sys.path.insert(0, '.'); import uri_core.tools.fetch_url as F; print(F.__file__)"
    r = subprocess.run([sys.executable, "-I", "-c", code], cwd=dest, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]
    assert str(dest.resolve()) in r.stdout.strip() or r.stdout.strip().startswith(".")
    import json
    ev = json.loads((dest / "secure-recovery-evidence.json").read_text(encoding="utf-8"))
    assert ev["support_files"]["files"] == G.SUPPORT_FILES


def test_d08_a_changed_support_pin_refuses_before_writing(monkeypatch):
    monkeypatch.setattr(G, "SUPPORT_FILES", {**G.SUPPORT_FILES, "uri_web/netpolicy.py": "0" * 64})
    dest = fresh()
    with pytest.raises(G.RollbackRefused, match="SUPPORT_FILES_UNAVAILABLE"):
        G.rollback(FROZEN, FROZEN_SHA, dest, secure_recovery=True)
    assert not dest.exists()


def test_d08_default_and_safe_rollbacks_are_unchanged():
    dest = fresh()
    with pytest.raises(G.RollbackRefused, match="UNSAFE_ROLLBACK_REFUSED"):
        G.rollback(FROZEN, FROZEN_SHA, dest)
    assert not dest.exists()
