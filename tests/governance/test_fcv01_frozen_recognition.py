"""FCV-01: the owner-authorized rollback amendment is recognized only as its exact blob, from its own anchor."""
import pytest

from scripts import ws_frozen_check as F
from tests.governance.test_frozen_governance import fixture, git  # noqa: F401  (fixture)

TOOL, RECORD = "scripts/phase1_offline_rollback.py", "docs/fcv01.md"


@pytest.fixture
def amended(fixture, monkeypatch):
    repo, checkpoint, baseline, anchor, name, witness = fixture
    # The frozen tool joins the checkpoint, then an exact amendment lands in a later commit with its record.
    import zipfile
    (repo / "scripts").mkdir()
    (repo / TOOL).write_bytes(b"frozen rollback\n")
    with zipfile.ZipFile(checkpoint, "a") as z:
        z.writestr(TOOL, b"frozen rollback\n")
    monkeypatch.setattr(F, "ZIP_SHA", F.digest(checkpoint.read_bytes()))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "frozen tool")
    monkeypatch.setattr(F, "BASELINE", git(repo, "rev-parse", "HEAD"))
    (repo / TOOL).write_bytes(b"amended rollback\n")
    (repo / RECORD).write_bytes(b"owner FCV-01 decision\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "owner-authorized amendment")
    commit = git(repo, "rev-parse", "HEAD")
    monkeypatch.setitem(F.PROVENANCE, RECORD, F.digest(b"owner FCV-01 decision\n"))
    monkeypatch.setitem(F.APPROVED, TOOL, {"sha256": F.digest(b"amended rollback\n"), "decisions": ["FCV-01"],
                                          "commits": [commit], "provenance": [RECORD], "anchor": commit})
    return repo


def test_exact_amendment_from_its_own_anchor_is_recognized(amended):
    out = F.check(amended)
    assert out["ok"], out
    assert TOOL in out["recognized_exact_blobs"]


@pytest.mark.parametrize("data", [b"frozen rollback\n", b"amended rollback plus more\n"])
def test_reverting_or_changing_the_amendment_is_refused(amended, data):
    (amended / TOOL).write_bytes(data)
    git(amended, "commit", "-qam", "change")
    assert not F.check(amended)["ok"]


def test_amendment_without_its_record_is_refused(amended):
    (amended / RECORD).write_bytes(b"edited record\n")
    git(amended, "commit", "-qam", "edit record")
    assert not F.check(amended)["ok"]


def test_amendment_bytes_before_their_anchor_are_not_authority(amended, monkeypatch):
    # Same bytes, but the approval names a commit this tree does not descend from: still unapproved drift.
    monkeypatch.setitem(F.APPROVED[TOOL], "anchor", F.APPROVED["uri_core/app/server.py"]["commits"][0])
    monkeypatch.setitem(F.APPROVED[TOOL], "commits", ["0" * 40])
    assert not F.check(amended)["ok"]
