"""FCV-01 (owner-authorized 2026-10-14): the offline rollback rehearses the exact frozen checkpoint."""
import hashlib
import io
import json
from pathlib import Path
import uuid
import zipfile

import pytest

from scripts import phase1_offline_rollback as R

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "work/c1/checkpoints/final-closure-20261005-phase1.zip"
pytestmark = pytest.mark.skipif(not FROZEN.is_file(), reason="frozen checkpoint fixture not installed: run scripts/fcv_install_phase1_fixtures.py (FCV-09)")
FROZEN_SHA = "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7"


def derived(mutate):
    members = []
    with zipfile.ZipFile(FROZEN) as z:
        for i in z.infolist():
            members.append([i.filename, z.read(i)])
    members = mutate(members)
    out = ROOT / "work/c1/checkpoints" / ("negative_hyg1_" + uuid.uuid4().hex + ".zip")   # HYG-1 tag
    with zipfile.ZipFile(out, "w") as a:
        for n, d in members:
            a.writestr(n, d)
    return out, hashlib.sha256(out.read_bytes()).hexdigest(), ROOT / "work/c1" / ("negative_restore_hyg1_" + uuid.uuid4().hex)


def test_exact_frozen_checkpoint_rehearses_and_restores_every_frozen_file():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == FROZEN_SHA
    dest = ROOT / "work/c1" / ("rollback_hyg1_" + uuid.uuid4().hex)
    ev = R.rehearse(FROZEN, FROZEN_SHA, dest)
    assert ev["status"] == "OFFLINE_SOURCE_OVERLAY_RECOVERY_PASSED" and ev["archive_sha256"] == FROZEN_SHA
    with zipfile.ZipFile(FROZEN) as z:
        names = [n for n in z.namelist() if n not in R.CHECKPOINT_METADATA]
        assert len(names) == 121
        for n in names:
            assert (dest / n).read_bytes() == z.read(n), n
        meta = {n: hashlib.sha256(z.read(n)).hexdigest() for n in R.CHECKPOINT_METADATA}
    assert ev["checkpoint_metadata"] == dict(sorted(meta.items()))
    assert not any((dest / n).exists() for n in R.CHECKPOINT_METADATA)   # provenance, not restored source
    assert ev["application_started"] is False and ev["production_cutover"] is False


@pytest.mark.parametrize("extra", ["uri_ui/lib/main.dart", "uri_ui/lib/services/other.dart", "uri_core/x.dart",
                                   "uri_ui/lib/services/PAIRED_RUNTIME.dart", "docs/GIT_HEAD.txt", "GIT_LOG.txt",
                                   "git_head.txt", "uri_ui/pubspec.yaml"])
def test_only_exact_frozen_ui_and_metadata_names_are_recognized(extra):
    z, sha, dest = derived(lambda m: m + [[extra, b"x = 1\n"]])
    with pytest.raises(ValueError):
        R.rehearse(z, sha, dest)
    assert not dest.exists()


@pytest.mark.parametrize("mutate", [
    lambda m: [x for x in m if x[0] != "GIT_DIFF.patch"],                                   # partial metadata
    lambda m: [[n, b"0" * 40 + b"\n" if n == "GIT_HEAD.txt" else d] for n, d in m],         # wrong base commit
    lambda m: [[n, d.rstrip(b"\n") if n == "GIT_HEAD.txt" else d] for n, d in m],           # non-exact bytes
])
def test_checkpoint_metadata_must_be_complete_and_name_the_accepted_base(mutate):
    z, sha, dest = derived(mutate)
    with pytest.raises(ValueError, match="CHECKPOINT_METADATA_INVALID"):
        R.rehearse(z, sha, dest)
    assert not dest.exists()


def test_tampered_frozen_member_with_original_hash_is_refused_before_writing():
    z, _, dest = derived(lambda m: [[n, d + b"# tamper\n" if n == "uri_core/app/server.py" else d] for n, d in m])
    with pytest.raises(ValueError, match="CHECKPOINT_HASH"):
        R.rehearse(z, FROZEN_SHA, dest)
    assert not dest.exists()


def test_failed_rehearsal_never_writes_success_evidence():
    z, sha, dest = derived(lambda m: [[n, b"def broken(:\n" if n == "uri_core/app/server.py" else d] for n, d in m])
    with pytest.raises(SyntaxError):
        R.rehearse(z, sha, dest)
    assert not (dest / "rollback-evidence.json").exists()
