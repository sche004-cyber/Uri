"""Output tamper refusals are structural fixtures, not live runtime evidence."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts import oi_materialize_test_runtime as M
from scripts import ws_materialized_verify as V

ROOT = Path(__file__).resolve().parents[2]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_actual_committed_source_authority_and_exact_patch():
    files, frozen = V.source_authority(ROOT)
    assert frozen["ok"] and V.PATCH_PATH in files
    assert V.digest(V.raw(ROOT, V.PATCH_PATH)) == V.PATCH_SHA256


@pytest.fixture
def output(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-q")
    git(source, "config", "user.name", "Fixture")
    git(source, "config", "user.email", "fixture@invalid")
    git(source, "config", "core.autocrlf", "false")
    for name in list(V.BEFORE) + list(V.F.PROVENANCE):
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, p)
    (source / "overlay.txt").write_text("")
    (source / "worker.py").write_text("# pinned fixture worker\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "fixture")
    head = git(source, "rev-parse", "HEAD")
    runtime = tmp_path / "runtime"
    subprocess.run(["git", "clone", "-q", "--shared", str(source), str(runtime)], check=True)
    monkeypatch.setattr(M, "BASE", head)
    monkeypatch.setattr(M, "OVERLAY_COMMIT", head)
    monkeypatch.setattr(M, "OVERLAY_LIST", "overlay.txt")
    monkeypatch.setattr(M, "OI_PATHS", [])
    monkeypatch.setattr(M, "REPLACED_PATHS", [])
    monkeypatch.setattr(V, "ACCEPTED_SOURCE", head)
    # Only skip the production ancestry/source authority for this tiny structural fixture.
    # The unmocked source authority is exercised separately above and by actual materialization.
    monkeypatch.setattr(V, "source_authority", lambda p: (V.tree(p, "HEAD"), {"ok": True}))
    receipt = dict(candidate_source=str(source), candidate_head=head,
                   candidate_tree=git(source, "rev-parse", "HEAD^{tree}"),
                   head=head, overlay_commit=head, security_patch_sha256=V.PATCH_SHA256,
                   oi_tests_included=True)
    (runtime / "OI_MATERIALIZATION_RECEIPT.json").write_text(json.dumps(receipt))
    assert V.verify(source, runtime)["ok"]
    return source, runtime, receipt


@pytest.mark.parametrize("path", ["uri_core/app/server.py", "uri_core/tools/fetch_url.py",
                                  "worker.py", "docs/ssrf/SSRF_1_PLAN_AND_ACCEPTANCE.md"])
def test_changed_content_refused(output, path):
    source, runtime, _ = output
    (runtime / path).write_text("altered\n")
    result = V.verify(source, runtime)
    assert not result["ok"] and "OUTPUT_CHANGED" in result["error"]


@pytest.mark.parametrize("path", ["uri_core/backdoor.py", "unexpected_worker.py", "docs/forged_approval.md"])
def test_unknown_output_refused_even_if_ignored(output, path):
    source, runtime, _ = output
    p = runtime / path
    p.parent.mkdir(exist_ok=True)
    p.write_text("unknown\n")
    git(runtime, "config", "core.excludesFile", str(runtime.parent / "ignore"))
    (runtime.parent / "ignore").write_text(path + "\n")
    result = V.verify(source, runtime)
    assert not result["ok"] and "UNKNOWN_OUTPUT" in result["error"]


@pytest.mark.parametrize("field", ["candidate_source", "candidate_head", "candidate_tree", "head",
                                   "overlay_commit", "security_patch_sha256", "oi_tests_included"])
def test_receipt_cannot_authorize_substitution(output, field):
    source, runtime, receipt = output
    receipt[field] = "substituted"
    (runtime / "OI_MATERIALIZATION_RECEIPT.json").write_text(json.dumps(receipt))
    assert not V.verify(source, runtime)["ok"]


def test_missing_provenance_refused(output):
    source, runtime, _ = output
    (runtime / "docs/ssrf/SSRF_1_PLAN_AND_ACCEPTANCE.md").unlink()
    assert not V.verify(source, runtime)["ok"]


def test_altered_index_execution_mode_refused(output):
    source, runtime, _ = output
    git(runtime, "update-index", "--chmod=+x", "worker.py")
    result = V.verify(source, runtime)
    assert not result["ok"] and result["error"] == "RUNTIME_INDEX_CHANGED"


def test_hidden_index_flag_refused(output):
    source, runtime, _ = output
    git(runtime, "update-index", "--assume-unchanged", "worker.py")
    assert V.verify(source, runtime)["error"] == "HIDDEN_INDEX_FLAGS"


def test_wrong_runtime_head_refused(output):
    source, runtime, _ = output
    git(runtime, "config", "user.name", "Fixture")
    git(runtime, "config", "user.email", "fixture@invalid")
    git(runtime, "commit", "--allow-empty", "-qm", "wrong identity")
    assert V.verify(source, runtime)["error"] == "HISTORICAL_HEAD_CHANGED"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/escape", "dir\\escape"])
def test_unsafe_paths_refused(tmp_path, name):
    with pytest.raises(V.VerificationError):
        V.raw(tmp_path, name)


def test_reconciliation_refuses_unknown_before_bytes(output):
    source, runtime, _ = output
    with pytest.raises(V.VerificationError, match="TRANSITION_BEFORE_CHANGED"):
        V.reconcile(source, runtime)
