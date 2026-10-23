"""Git control digest v2 (narrow port from the unintegrated reviewer-tiers branch 67d45317).

`git repack` (run by any session's auto-gc) calls `git update-server-info`, which rewrites `.git/info/refs` and
`.git/objects/info/packs`. Those files are transport metadata for dumb protocols and never change how git behaves
locally, but the v1 digest hashed every file under `.git/info/` and so stopped runs as TAMPER/EVIDENCE
(LIFECYCLE-V3-1 r1, r4, r6 and MILESTONE-MANAGER-d1, 2026-10-21/22). v2 leaves out the generated files and still
binds every other control file; runs bound with the v1 digest keep being compared with it until a clean run binds v2.

TEST ONLY: scripted reviewers (DEVTEST); "quota" makes the reviewer unavailable so the run stops early.
"""
from pathlib import Path

from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow.state_machine import WorkflowState as S
from tests.dev_workflow.test_lifecycle import config, g, make_fixture


def waiting(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt, reviewer="quota")
    assert L.run(cfg) == S.WAITING_FOR_MODEL
    return cfg, repo, wt


def info_dir(repo) -> Path:
    d = Path(repo) / ".git" / "info"
    d.mkdir(exist_ok=True)
    return d


def test_generated_info_files_are_not_drift_but_other_info_files_are(tmp_path):
    cfg, repo, wt = waiting(tmp_path)
    info = info_dir(repo)
    (info / "refs").write_text("abc\trefs/heads/x\n")    # what `git update-server-info` writes on repack
    (info / "packs").write_text("P pack-1.pack\n")
    assert L.control_drift(cfg, L.State(cfg)) is None
    (info / "exclude").write_text("*.secret\n")         # hides files from status: still control
    assert "GIT_CONTROL" in (L.control_drift(cfg, L.State(cfg)) or "")


def test_grafts_and_attributes_under_info_stay_bound(tmp_path):
    cfg, repo, wt = waiting(tmp_path)
    (info_dir(repo) / "attributes").write_text("*.py filter=evil\n")
    assert "GIT_CONTROL" in (L.control_drift(cfg, L.State(cfg)) or "")


def test_digest_v2_ignores_only_the_generated_files(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    d0, legacy0 = L.git_control_digest(repo), L.git_control_digest(repo, legacy=True)
    (info_dir(repo) / "refs").write_text("abc\trefs/heads/x\n")
    assert L.git_control_digest(repo) == d0
    assert L.git_control_digest(repo, legacy=True) != legacy0   # the legacy digest is unchanged in behaviour
    g(repo, "config", "core.fsmonitor", "/tmp/evil")
    assert L.git_control_digest(repo) != d0


def test_v2_checks_do_not_read_generated_info_files(tmp_path, monkeypatch):
    cfg, repo, wt = waiting(tmp_path)
    generated = info_dir(repo) / "refs"
    generated.write_text("abc\trefs/heads/x\n")
    expected = L.git_control_digest(repo)
    read_bytes = Path.read_bytes

    def unreadable_generated(self):
        if self == generated:
            raise PermissionError("generated info/refs is temporarily unreadable")
        return read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", unreadable_generated)
    assert L.git_control_digest(repo) == expected
    assert L.control_state(cfg)["git_control_v2"] == expected
    assert L.control_drift(cfg, L.State(cfg)) is None
    try:
        L.git_control_digest(repo, legacy=True)
    except PermissionError:
        pass
    else:
        raise AssertionError("legacy digest must still read generated info/refs")


def test_a_run_bound_with_the_legacy_digest_is_upgraded_only_when_clean(tmp_path):
    cfg, repo, wt = waiting(tmp_path)
    st = L.State(cfg)
    legacy = {k: v for k, v in L.control_anchor(st).items() if k != "git_control_v2"}
    legacy["git_control"] = L.git_control_digest(cfg["repo"], legacy=True)
    st.event("CONTROL_ANCHORED", control=legacy)                    # as a run planned before v2
    st = L.State(cfg)
    assert "git_control_v2" not in L.control_anchor(st) and L.control_drift(cfg, st) is None
    assert L.run(cfg) == S.WAITING_FOR_MODEL
    assert "git_control_v2" in L.control_anchor(L.State(cfg))       # bound because nothing had changed
    (info_dir(repo) / "refs").write_text("abc\trefs/heads/x\n")
    assert L.control_drift(cfg, L.State(cfg)) is None


def test_a_legacy_bound_run_with_drift_is_not_upgraded(tmp_path):
    cfg, repo, wt = waiting(tmp_path)
    st = L.State(cfg)
    legacy = {k: v for k, v in L.control_anchor(st).items() if k != "git_control_v2"}
    legacy["git_control"] = L.git_control_digest(cfg["repo"], legacy=True)
    st.event("CONTROL_ANCHORED", control=legacy)
    (info_dir(repo) / "refs").write_text("changed after the legacy plan\n")
    st = L.State(cfg)
    assert "GIT_CONTROL" in (L.control_drift(cfg, st) or "")       # compared exactly as before v2
    L.run(cfg)
    assert "git_control_v2" not in L.control_anchor(L.State(cfg))   # never re-bound over a drift
    assert L.State(cfg).stage == S.BLOCKED


# ---------------------------------------------------------------- G1-02 (fallback review FB1, LOW): one read

def test_both_digests_come_from_one_read_and_match_the_single_digests(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    (info_dir(repo) / "refs").write_text("abc\trefs/heads/x\n")
    d = L.git_control_digests(repo)
    assert d == {"legacy": L.git_control_digest(repo, legacy=True), "v2": L.git_control_digest(repo)}
    assert d["legacy"] != d["v2"]


def test_g1_02_upgrade_binds_the_state_it_compared_not_a_later_read(tmp_path, monkeypatch):
    cfg, repo, wt = waiting(tmp_path)
    st = L.State(cfg)
    legacy = {k: v for k, v in L.control_anchor(st).items() if k != "git_control_v2"}
    legacy["git_control"] = L.git_control_digest(cfg["repo"], legacy=True)
    st.event("CONTROL_ANCHORED", control=legacy)                    # a run planned before v2, clean now
    real = L.git_control_digests
    clean = real(cfg["repo"])
    reads = []

    def racing(repo_, *, include_legacy=True):
        # first read sees the clean state; every later read sees a control change that lands right after it
        reads.append(1)
        result = dict(clean) if len(reads) == 1 else {"legacy": "changed-legacy", "v2": "changed-v2"}
        return result if include_legacy else {"v2": result["v2"]}

    monkeypatch.setattr(L, "git_control_digests", racing)
    L.run(cfg)
    bound = L.control_anchor(L.State(cfg))
    assert bound.get("git_control_v2") == clean["v2"]               # never the value of the later read
    assert L.State(cfg).stage == S.BLOCKED                         # and the later change is still caught
