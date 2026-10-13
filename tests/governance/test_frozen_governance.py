"""Security/governance rejection cases for the inactive exact-blob proposal."""
import subprocess
import zipfile
from pathlib import Path

import pytest
from scripts import ws_frozen_check as F


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@invalid")
    git(repo, "config", "core.autocrlf", "false")
    name, witness = "uri_core/app/server.py", "docs/authority.md"
    (repo / name).parent.mkdir(parents=True)
    (repo / name).write_bytes(b"frozen original\n")
    (repo / "uri_core/other.py").write_bytes(b"other original\n")
    (repo / "uri_core/outside_checkpoint.py").write_bytes(b"outside checkpoint original\n")
    (repo / ".gitignore").write_bytes(b"ignored_backdoor.py\n__pycache__/\n")
    (repo / "docs").mkdir()
    (repo / "docs/frozen.txt").write_bytes(b"original frozen document\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "original checkpoint")
    baseline = git(repo, "rev-parse", "HEAD")
    checkpoint = tmp_path / "checkpoint.zip"
    with zipfile.ZipFile(checkpoint, "w") as z:
        z.writestr(name, b"frozen original\n")
        z.writestr("uri_core/other.py", b"other original\n")
        z.writestr("docs/frozen.txt", b"original frozen document\n")
    (repo / name).write_bytes(b"approved security fix\n")
    (repo / witness).parent.mkdir(exist_ok=True)
    (repo / witness).write_bytes(b"owner D12 exact narrow exception\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "owner-approved security transition")
    anchor = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(F, "ZIP", checkpoint)
    monkeypatch.setattr(F, "ZIP_SHA", F.digest(checkpoint.read_bytes()))
    monkeypatch.setattr(F, "BASELINE", baseline)
    monkeypatch.setattr(F, "ANCHOR", anchor)
    monkeypatch.setattr(F, "PROVENANCE", {witness: F.digest((repo / witness).read_bytes())})
    monkeypatch.setattr(F, "APPROVED", {name: {"sha256": F.digest((repo / name).read_bytes()),
        "commits": [anchor], "provenance": [witness], "decisions": ["D12"]}})
    return repo, checkpoint, baseline, anchor, name, witness


def test_exact_blob_with_exact_provenance_and_ancestry_is_recognized(fixture):
    repo, _, _, _, name, _ = fixture
    result = F.check(repo)
    assert result["ok"] and set(result["recognized_exact_blobs"]) == {name}
    assert result["phase1_frozen"]["drift"] == [name]  # never erase original drift


@pytest.mark.parametrize("where", ["working", "staged", "committed"])
def test_unknown_or_altered_protected_blob_is_refused(fixture, where):
    repo, _, _, _, name, _ = fixture
    (repo / name).write_bytes(b"unapproved patch\n")
    if where != "working":
        git(repo, "add", name)
        if where == "committed": git(repo, "commit", "-qm", "unapproved")
        (repo / name).write_bytes(b"approved security fix\n")
    assert not F.check(repo)["ok"]


def test_rollback_to_original_checkpoint_cannot_remove_security_fix(fixture):
    repo, _, _, _, name, _ = fixture
    (repo / name).write_bytes(b"frozen original\n")
    result = F.check(repo)
    assert not result["ok"] and name in result["unapproved_protected_changes"]


@pytest.mark.parametrize("where", ["staged", "committed"])
def test_unknown_protected_index_or_head_change_cannot_hide_under_clean_worktree(fixture, where):
    repo, *_ = fixture
    p = repo / "uri_core/other.py"
    original = p.read_bytes()
    p.write_bytes(b"malicious persisted blob\n")
    git(repo, "add", str(p))
    if where == "committed": git(repo, "commit", "-qm", "malicious persisted change")
    p.write_bytes(original)
    assert not F.check(repo)["ok"]


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_protected_paths_cannot_be_hidden_from_git_worktree_diff(fixture, flag):
    repo, *_ = fixture
    name = "uri_core/outside_checkpoint.py"
    git(repo, "update-index", flag, name)
    (repo / name).write_bytes(b"hidden malicious working copy\n")
    assert not F.check(repo)["ok"]


@pytest.mark.parametrize("change", ["missing", "altered", "staged", "committed"])
def test_missing_or_altered_provenance_is_refused(fixture, change):
    repo, _, _, _, _, witness = fixture
    original = (repo / witness).read_bytes()
    if change == "missing": (repo / witness).unlink()
    else:
        (repo / witness).write_bytes(b"invented blanket approval\n")
        if change in ("staged", "committed"):
            git(repo, "add", witness)
            if change == "committed": git(repo, "commit", "-qm", "altered witness")
            (repo / witness).write_bytes(original)
    assert not F.check(repo)["ok"]


def test_matching_blob_without_approved_history_is_refused(fixture):
    repo, _, baseline, _, _, _ = fixture
    git(repo, "checkout", "--detach", baseline)
    (repo / "uri_core/app/server.py").write_bytes(b"approved security fix\n")
    assert not F.check(repo)["ok"]


def test_missing_provenance_commit_is_refused(fixture, monkeypatch):
    repo, *_ = fixture
    monkeypatch.setitem(F.APPROVED["uri_core/app/server.py"], "commits", ["0" * 40])
    assert not F.check(repo)["ok"]


@pytest.mark.parametrize("path", ["uri_core/other.py", "uri_core/unrelated.py", ".gitignore"])
def test_no_path_wide_or_unrelated_exception(fixture, path):
    repo, *_ = fixture
    (repo / path).write_bytes(b"unapproved unrelated file\n")
    assert not F.check(repo)["ok"]


@pytest.mark.parametrize("ignore", ["local", "global", "tracked"])
def test_ignored_untracked_protected_file_is_still_refused(fixture, ignore):
    repo, *_ = fixture
    name = "uri_core/ignored_backdoor.py"
    (repo / name).write_bytes(b"untracked hidden executable\n")
    if ignore == "local": (repo / ".git/info/exclude").write_text(name + "\n")
    elif ignore == "global":
        excludes = repo.parent / "global-excludes"
        excludes.write_text(name + "\n")
        git(repo, "config", "core.excludesFile", str(excludes))
    assert name not in git(repo, "ls-files", "--others", "--exclude-standard")
    assert not F.check(repo)["ok"]


def test_clean_filter_cannot_hide_raw_protected_bytes_outside_checkpoint(fixture):
    repo, _, baseline, *_ = fixture
    name = "uri_core/outside_checkpoint.py"
    (repo / ".gitattributes").write_text(name + " filter=mask\n")
    git(repo, "config", "filter.mask.clean", f"git show {baseline}:{name}")
    (repo / name).write_bytes(b"malicious raw working bytes\n")
    assert name not in git(repo, "diff", "--name-only", baseline)
    assert not F.check(repo)["ok"]


def test_protected_git_mode_change_is_refused(fixture):
    repo, _, _, _, name, _ = fixture
    git(repo, "update-index", "--chmod=+x", name)
    assert not F.check(repo)["ok"]


@pytest.mark.parametrize("where", ["staged", "committed"])
def test_provenance_git_mode_change_is_refused(fixture, where):
    repo, _, _, _, _, witness = fixture
    git(repo, "update-index", "--chmod=+x", witness)
    if where == "committed": git(repo, "commit", "-qm", "altered provenance metadata")
    assert not F.check(repo)["ok"]


@pytest.mark.parametrize("change", ["missing", "tampered"])
def test_checkpoint_remains_immutable_and_required(fixture, change):
    repo, checkpoint, *_ = fixture
    if change == "missing": checkpoint.unlink()
    else: checkpoint.write_bytes(b"new checkpoint")
    assert not F.check(repo)["ok"]


def test_checkpoint_verification_consumes_the_same_verified_byte_snapshot(fixture, monkeypatch):
    repo, checkpoint, *_ = fixture
    before = checkpoint.read_bytes()
    original_digest = F.digest
    swapped = False
    def swap_after_verified_read(data):
        nonlocal swapped
        if data == before and not swapped:
            swapped = True
            (repo / "docs/frozen.txt").write_bytes(b"malicious substituted frozen document\n")
            with zipfile.ZipFile(checkpoint, "w") as z:
                z.writestr("uri_core/app/server.py", b"frozen original\n")
                z.writestr("uri_core/other.py", b"other original\n")
                z.writestr("docs/frozen.txt", b"malicious substituted frozen document\n")
        return original_digest(data)
    monkeypatch.setattr(F, "digest", swap_after_verified_read)
    result = F.check(repo)
    assert swapped and not result["ok"]
    assert "docs/frozen.txt" in result["phase1_frozen"]["unapproved_drift"]


def test_git_failure_is_fail_closed(fixture):
    repo, *_ = fixture
    assert not F.check(repo / "uri_core")["ok"]


def test_protected_symbolic_link_is_refused(fixture):
    repo, _, _, _, name, _ = fixture
    destination = repo / "approved-copy"
    destination.write_bytes((repo / name).read_bytes())
    (repo / name).unlink()
    try: (repo / name).symlink_to(destination)
    except OSError: pytest.skip("platform does not permit fixture symlinks")
    assert not F.check(repo)["ok"]
