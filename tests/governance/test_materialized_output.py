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
    subprocess.run(["git", "-c", "core.autocrlf=false", "clone", "-q", "--shared", str(source), str(runtime)], check=True)
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
                   security_transitions={p: {"before_sha256": before,
                                              "after_sha256": V.F.APPROVED[p]["sha256"]}
                                         for p, before in V.BEFORE.items()},
                   oi_tests_included=True)
    (runtime / "OI_MATERIALIZATION_RECEIPT.json").write_text(json.dumps(receipt))
    verified = V.verify(source, runtime)
    assert verified["ok"], verified
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
                                   "overlay_commit", "security_patch_sha256", "security_transitions", "oi_tests_included"])
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


def test_original_checkpoint_behavior_without_receipt(tmp_path):
    assert V.verified_transitions(tmp_path) == set()


def test_original_checkpoint_behavior_with_historical_receipt(tmp_path):
    (tmp_path / "OI_MATERIALIZATION_RECEIPT.json").write_text("{}")
    assert V.verified_transitions(tmp_path) == set()


def test_authorized_transition_gate_requires_full_output_proof(output):
    source, runtime, _ = output
    assert V.verified_transitions(runtime) == set(V.BEFORE)
    (runtime / "worker.py").write_text("changed source\n")
    with pytest.raises(V.VerificationError, match="MATERIALIZED_GATE_REFUSED"):
        V.verified_transitions(runtime)


def test_inherited_paths_pin_exact_accepted_bytes_even_without_receipt(tmp_path):
    name = "uri_assist/onscreen.py"
    p = tmp_path / name
    p.parent.mkdir()
    shutil.copy2(ROOT / name, p)
    assert V.verified_transitions(tmp_path) == set()
    p.write_text("altered inherited implementation\n")
    with pytest.raises(V.VerificationError, match="INHERITED_SCOPE_BLOB_CHANGED"):
        V.verified_transitions(tmp_path)


def test_every_inherited_scope_pin_matches_immutable_accepted_git_blob():
    assert len(V.INHERITED_SCOPE_BLOBS) == 81
    for name, expected in V.INHERITED_SCOPE_BLOBS.items():
        data = subprocess.check_output(["git", "-C", str(ROOT), "show", V.ACCEPTED_SOURCE + ":" + name])
        assert V.digest(data) == expected


def test_canonical_lineage_pins_exact_canonical_bytes():
    """FCV-20261014: a canonical-descended candidate keeps canonical's exact inherited bytes."""
    for name, expected in V.CANONICAL_SCOPE_BLOBS.items():
        p = subprocess.run(["git", "-C", str(ROOT), "show", V.CANONICAL_SOURCE + ":" + name], capture_output=True)
        assert (V.digest(p.stdout) if p.returncode == 0 else None) == expected
    assert set(V.CANONICAL_SCOPE_BLOBS) <= set(V.INHERITED_SCOPE_BLOBS)
    assert subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", V.CANONICAL_SOURCE,
                           V.ACCEPTED_SOURCE]).returncode == 0


def test_canonical_lineage_refuses_other_inherited_bytes(tmp_path):
    name = "uri_assist/onscreen.py"
    p = tmp_path / name
    p.parent.mkdir()
    canonical = subprocess.check_output(["git", "-C", str(ROOT), "show", V.CANONICAL_SOURCE + ":" + name])
    accepted = subprocess.check_output(["git", "-C", str(ROOT), "show", V.ACCEPTED_SOURCE + ":" + name])
    p.write_bytes(canonical)
    V.verify_inherited_scope(tmp_path, anchor=V.CANONICAL_SOURCE)
    V.verify_inherited_scope(tmp_path)
    with pytest.raises(V.VerificationError, match="INHERITED_SCOPE_BLOB_CHANGED"):
        V.verify_inherited_scope(tmp_path, anchor=V.ACCEPTED_SOURCE)
    p.write_bytes(accepted)
    with pytest.raises(V.VerificationError, match="INHERITED_SCOPE_BLOB_CHANGED"):
        V.verify_inherited_scope(tmp_path, anchor=V.CANONICAL_SOURCE)
    p.write_text("altered inherited implementation\n")
    with pytest.raises(V.VerificationError, match="INHERITED_SCOPE_BLOB_CHANGED"):
        V.verify_inherited_scope(tmp_path)
    absent_on_canonical = tmp_path / "tests/assist/test_subpixel_render.py"
    absent_on_canonical.parent.mkdir(parents=True)
    absent_on_canonical.write_bytes(subprocess.check_output(
        ["git", "-C", str(ROOT), "show", V.ACCEPTED_SOURCE + ":tests/assist/test_subpixel_render.py"]))
    with pytest.raises(V.VerificationError, match="INHERITED_SCOPE_BLOB_CHANGED"):
        V.verify_inherited_scope(tmp_path, anchor=V.CANONICAL_SOURCE)


def test_source_outside_accepted_lineage_is_refused(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "-C", str(source), "init", "-q"], check=True)
    (source / "x").write_text("x\n")
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=F", "-c", "user.email=f@invalid", "commit", "-qm", "x"],
                   check=True)
    with pytest.raises(V.VerificationError, match="GIT_REFUSED|SOURCE_NOT_ACCEPTED_LINEAGE"):
        V.accepted_anchor(source)


def test_materializer_always_reconciles_and_verifies_security_transitions():
    """FCV-03: canonical's materializer restored pre-security server.py/fetch_url.py. The builder must apply the
    authorized transition and refuse its own output unless full verification passes; neither call may be optional."""
    import ast
    tree_ = ast.parse((ROOT / "scripts/oi_materialize_test_runtime.py").read_text(encoding="utf-8"))
    main = next(n for n in tree_.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "V"]
    names = [c.func.attr for c in calls]
    assert names.count("source_authority") == 1 and names.count("reconcile") == 1 and names.count("verify") == 1
    for c in calls:   # top-level statements of main(): not inside an if/try that could skip them
        parent = next(s for s in main.body if any(x is c for x in ast.walk(s)))
        assert not isinstance(parent, (ast.If, ast.Try, ast.For, ast.While)), c.func.attr
    exits = [n for n in ast.walk(main) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "exit"
             and n.args and isinstance(n.args[0], ast.BinOp)]
    assert any("MATERIALIZED_OUTPUT_REFUSED" in ast.unparse(e) for e in exits)
    assert V.BEFORE.keys() == M_APPROVED_KEYS


M_APPROVED_KEYS = {"uri_core/app/server.py", "uri_core/tools/fetch_url.py"}


def test_gate_generated_bytecode_beside_expected_source_is_not_unknown_output(output):
    """FCV-R chain: the accepted gates run Python with -I (bytecode on); their .pyc beside an expected source and
    pytest's root cache are generated artifacts. Anything else stays UNKNOWN_OUTPUT."""
    source, runtime, _ = output
    cache = runtime / "__pycache__"
    cache.mkdir()
    (cache / "worker.cpython-313.pyc").write_bytes(b"bytecode")
    (cache / "worker.cpython-313-pytest-9.1.1.pyc").write_bytes(b"bytecode")
    (runtime / ".pytest_cache/v/cache").mkdir(parents=True)
    (runtime / ".pytest_cache/v/cache/lastfailed").write_text("{}")
    result = V.verify(source, runtime)
    assert result["ok"], result
    assert result["generated_files_ignored"] == 3


@pytest.mark.parametrize("rel", ["__pycache__/unknown.cpython-313.pyc", "__pycache__/worker.py", "worker.cpython-313.pyc",
                                 ".pytest_cache/evil.py", "sub/__pycache__/worker.cpython-313.pyc"])
def test_other_generated_looking_files_are_still_refused(output, rel):
    source, runtime, _ = output
    p = runtime / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    result = V.verify(source, runtime)
    assert not result["ok"] and "UNKNOWN_OUTPUT" in result["error"]
