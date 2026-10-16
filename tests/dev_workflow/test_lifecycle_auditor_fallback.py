"""Auditor fallback policy (owner clarification 2026-10-16): independent review is mandatory, a particular provider
never is. The driver tries the preferred reviewer with bounded attempts, then the next independent reviewer in
``reviewer_fallbacks``; acceptance rests on verified independence + the exact candidate SHA + the verdict, never on
the provider's name. With no reviewer left the run is BLOCKED (NO_REVIEWER): a review is never invented.

TEST ONLY: scripted reviewer processes (DEVTEST) stand in for Codex and Claude; the independence checks for a real
CLI reviewer are exercised on round records directly.
"""
import json

import pytest

from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow.state_machine import WorkflowState as S
from tests.dev_workflow.test_lifecycle import PY, WORKER, config, g, make_fixture, remote_tip


def rv(mode, provider="command"):
    return {"provider": provider, "argv": [PY, str(WORKER), "reviewer", mode], "counts_as_independent": True}


def chain_config(tmp, repo, wt, primary, fallbacks, *, max_attempts=2, **kw):
    """A DEVTEST config whose reviewer chain is ``primary`` then ``fallbacks`` (scripted reviewer modes)."""
    cfg = config(tmp, repo, wt, reviewer=primary, **kw)
    raw = json.loads((tmp / "cfg.json").read_text())
    raw["reviewer_fallbacks"] = [rv(m) for m in fallbacks]
    raw["reviewer_selection"] = {"max_attempts": max_attempts}
    (tmp / "cfg.json").write_text(json.dumps(raw))
    del cfg
    return L.load_config(tmp / "cfg.json")


def events(cfg, kind):
    return [e["data"] for e in L._chained_events(L.State(cfg)) if e["kind"] == kind]


def good_cli_round(provider="claude_cli", sid="claude-reviewer-1"):
    """A round record of a real CLI reviewer the driver verified on every surface."""
    return {"integrity": {"ok": True}, "reviewer_spec": {"provider": provider},
            "worker": {"provider": provider, "status": "COMPLETED", "binary_is_default": True,
                       "binary_anchor_ok": True, "config_isolated": True, "contained": True, "session_id": sid}}


# ---------------------------------------------------------------- selection

def test_preferred_reviewer_available_is_selected(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "check", ["always_reject"])
    assert L.run(cfg) == S.COMPLETE
    s = L.status(cfg)
    assert [r["reviewer_index"] for r in s["reviewers"]] == [0]
    assert s["reviewers"][0]["outcome"] == "ACCEPT" and s["reviewers"][0]["independent"] is True
    assert remote_tip(remote) == s["candidate"]


@pytest.mark.parametrize("mode,reason", [("quota", "QUOTA"), ("auth", "AUTH")])
def test_preferred_unavailable_falls_back_and_fallback_accept_satisfies_the_gate(tmp_path, mode, reason):
    repo, wt, base, remote = make_fixture(tmp_path)               # defective: the fallback must REJECT, then ACCEPT
    cfg = chain_config(tmp_path, repo, wt, mode, ["check"])
    assert L.run(cfg) == S.COMPLETE
    s = L.status(cfg)
    first = s["reviewers"][0]
    assert first["reviewer_index"] == 0 and first["outcome"] == "UNAVAILABLE" and first["verdict"] is None
    st = L.State(cfg)
    assert st.d["rounds"][0]["worker"]["unavailable_reason"] == reason
    # an unavailable provider is not retried at once; after each independent result the preferred one is tried
    # first again (Codex preferred whenever it is available)
    assert [(r["reviewer_index"], r["outcome"]) for r in s["reviewers"]] ==         [(0, "UNAVAILABLE"), (1, "REJECT"), (0, "UNAVAILABLE"), (1, "ACCEPT")]
    # candidate change requires re-review: the REJECT was on the old SHA, the ACCEPT on the repaired one
    assert s["reviewers"][1]["candidate"] != s["candidate"] == s["reviewers"][3]["candidate"]
    assert L.accepted_review(cfg, st, s["reviewers"][1]["candidate"]) is None
    assert L.accepted_review(cfg, st, s["candidate"])["reviewer_index"] == 1
    assert [e["index"] for e in events(cfg, "REVIEWER_SELECTED")] == [0, 1, 0, 1]
    assert remote_tip(remote) == s["candidate"] and not L.verify(cfg)


def test_mid_review_disconnect_is_retried_within_the_bound(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "disconnect_once", ["always_reject"])
    assert L.run(cfg) == S.COMPLETE
    s = L.status(cfg)
    assert [(r["reviewer_index"], r["outcome"]) for r in s["reviewers"]] == [(0, "FAILURE"), (0, "ACCEPT")]
    assert L.attempt_counts(cfg, L.State(cfg)) == {}             # reset once an independent result exists
    assert events(cfg, "REVIEWER_ATTEMPT_FAILED")[0]["outcome"] == "FAILURE"


def test_sha_mismatch_never_accepts_and_moves_on(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "wrong_sha", ["check"])
    assert L.run(cfg) == S.COMPLETE
    s = L.status(cfg)
    assert [r["outcome"] for r in s["reviewers"]] == ["SHA_MISMATCH", "SHA_MISMATCH", "ACCEPT"]
    assert s["reviewers"][-1]["reviewer_index"] == 1
    assert all(r["verdict"] is None for r in s["reviewers"][:2])


# ---------------------------------------------------------------- no reviewer: BLOCKED, never invented

def test_no_reviewer_available_blocks_and_restart_preserves_the_state(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "disconnect", ["auth"])
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "NO_REVIEWER" and "command" in s["blocker"]["reason"]
    assert [r["outcome"] for r in s["reviewers"]] == ["FAILURE", "FAILURE", "UNAVAILABLE"]
    assert all(r["verdict"] is None for r in s["reviewers"]) and remote_tip(remote) == base
    assert not s["evidence_ok_for_candidate"]
    # restart: a fresh load derives the counters from the hash-chained events and launches no reviewer
    cfg2 = L.load_config(tmp_path / "cfg.json")
    expect = {"0": {"count": 2, "last": "FAILURE"}, "1": {"count": 2, "last": "UNAVAILABLE (AUTH)"}}
    assert L.attempt_counts(cfg2, L.State(cfg2)) == expect
    st = L.State(cfg2)
    st.d["reviewer_attempts"] = {}                                # editing state.json changes no decision
    st.save()
    assert L.run(cfg2) == S.BLOCKED and L.status(cfg2)["rounds"] == 3
    # the owner restores a reviewer and unblocks: the counters reset and review resumes (still unavailable here)
    assert L.unblock(cfg2, "owner: claude signed in") == S.READY_TO_RESUME
    assert L.attempt_counts(cfg2, L.State(cfg2)) == {}
    assert L.run(cfg2) == S.BLOCKED and L.status(cfg2)["rounds"] == 6
    assert not L.verify(cfg2)


def test_routine_unavailability_waits_and_the_next_run_tries_the_preferred_reviewer_first(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "quota", ["auth"])
    assert L.run(cfg) == S.WAITING_FOR_MODEL                     # no owner action needed for quota / sign-in
    s = L.status(cfg)
    assert s["blocker"] is None and [(r["reviewer_index"], r["outcome"]) for r in s["reviewers"]] ==         [(0, "UNAVAILABLE"), (1, "UNAVAILABLE")]
    assert events(cfg, "REVIEWER_WAIT")[0]["reason"] == "NO_INDEPENDENT_REVIEWER"
    assert L.attempt_counts(cfg, L.State(cfg)) == {}
    assert L.run(cfg) == S.WAITING_FOR_MODEL
    assert [r["reviewer_index"] for r in L.status(cfg)["reviewers"]] == [0, 1, 0, 1]
    assert remote_tip(remote) == base and not L.verify(cfg)


# ---------------------------------------------------------------- independence is verified, not named

def test_a_fully_verified_claude_reviewer_is_independent():
    cfg = {"milestone": "URI-REAL", "reviewer": {"provider": "codex_cli"}, "coordinator_session_id": "coord"}
    ok, why = L.is_independent(cfg, good_cli_round())
    assert ok, why


@pytest.mark.parametrize("field,value,needle", [
    ("binary_anchor_ok", False, "not the installed CLI"),
    ("binary_is_default", False, "not the installed CLI"),
    ("config_isolated", False, "driver-made CLI config"),
    ("contained", None, "orphan containment"),
    ("session_id", None, "session id"),
])
def test_an_unverifiable_reviewer_identity_is_denied(field, value, needle):
    cfg = {"milestone": "URI-REAL", "reviewer": {"provider": "codex_cli"}, "coordinator_session_id": "coord"}
    rec = good_cli_round()
    rec["worker"][field] = value
    ok, why = L.is_independent(cfg, rec)
    assert not ok and needle in why


def test_a_claude_reviewer_that_shares_the_implementer_or_coordinator_session_is_rejected():
    cfg = {"milestone": "URI-REAL", "reviewer": {"provider": "codex_cli"}, "coordinator_session_id": "coord"}
    assert not L.is_independent(cfg, good_cli_round(sid="impl-1"), {"impl-1"})[0]
    assert not L.is_independent(cfg, good_cli_round(sid="coord"))[0]


@pytest.mark.parametrize("var", ["CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID"])
def test_the_claude_code_session_running_the_driver_is_never_the_reviewer(monkeypatch, var):
    cfg = {"milestone": "URI-REAL", "reviewer": {"provider": "codex_cli"}}
    monkeypatch.setenv(var, "claude-reviewer-1")
    ok, why = L.is_independent(cfg, good_cli_round())
    assert not ok and "coordinator" in why


def test_a_diagnosis_worker_session_is_never_the_reviewer(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "check", [])
    st = L.State(cfg)
    st.d["diagnoses"] = [{"worker": {"session_id": "diag-1"}}]
    sids = {(r.get("worker") or {}).get("session_id") for r in st.d["repairs"] + st.d["diagnoses"]}
    assert not L.is_independent(cfg, good_cli_round(sid="diag-1"), sids)[0]


def test_a_relayed_claude_review_never_satisfies_the_gate(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "auth", ["auth"])
    sha = g(wt, "rev-parse", "HEAD")
    f = tmp_path / "relayed.txt"
    f.write_text("AUDIT_RESULT_BEGIN\n" + json.dumps({"candidate": sha, "verdict": "ACCEPT", "findings": []})
                 + "\nAUDIT_RESULT_END\n")
    L.import_review(cfg, f, "claude_agent", "agent-1", "coordinator relay")
    st = L.State(cfg)
    assert st.d["rounds"][0]["independent"] is False and L.accepted_review(cfg, st, sha) is None


# ---------------------------------------------------------------- the other gates still hold

def test_owner_authorisation_is_still_required_after_a_fallback_accept(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = chain_config(tmp_path, repo, wt, "quota", ["check"],
                       integration={"mode": "fast-forward", "remote": "origin", "target_ref": "canon",
                                    "authorized": False})
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "OWNER_AUTHORIZATION" and remote_tip(remote) == base
    assert s["reviewers"][-1]["outcome"] == "ACCEPT" and s["reviewers"][-1]["reviewer_index"] == 1


def test_frozen_core_is_still_protected_with_a_fallback_reviewer(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = chain_config(tmp_path, repo, wt, "quota", ["check"], implementer="protected")
    assert L.run(cfg) == S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "OWNER_DECISION" and "core/frozen.py" in s["blocker"]["reason"]
    assert (wt / "core/frozen.py").read_text() == "FROZEN = True\n" and remote_tip(remote) == base


def test_new_gate_failure_still_prevents_integration_with_a_fallback_reviewer(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False, break_other=True)
    cfg = chain_config(tmp_path, repo, wt, "auth", ["always_accept"], implementer="noop",
                       limits={"max_repair_attempts": 1})
    assert L.run(cfg) != S.COMPLETE
    assert remote_tip(remote) == base


# ---------------------------------------------------------------- configuration

def test_config_rules_for_the_chain(tmp_path):
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    with pytest.raises(L.LifecycleError, match="positive integer"):
        chain_config(tmp_path, repo, wt, "check", ["x"], max_attempts=0)
    raw = json.loads((tmp_path / "cfg.json").read_text())
    raw["milestone"] = "URI-REAL-MILESTONE"
    raw["reviewer"] = {"provider": "codex_cli"}
    raw["reviewer_selection"] = {"max_attempts": 2}
    raw["reviewer_fallbacks"] = [{"provider": "command", "argv": [PY, "x"]}]
    (tmp_path / "cfg.json").write_text(json.dumps(raw))
    with pytest.raises(L.LifecycleError, match="reviewer fallback must be one of"):
        L.load_config(tmp_path / "cfg.json")
    raw["reviewer_fallbacks"] = [{"provider": "claude_cli", "counts_as_independent": True}]
    (tmp_path / "cfg.json").write_text(json.dumps(raw))
    with pytest.raises(L.LifecycleError, match="DEVTEST"):
        L.load_config(tmp_path / "cfg.json")
    raw["reviewer_fallbacks"] = [{"provider": "claude_cli"}]
    (tmp_path / "cfg.json").write_text(json.dumps(raw))
    cfg = L.load_config(tmp_path / "cfg.json")
    assert [s["provider"] for s in L.reviewer_chain(cfg)] == ["codex_cli", "claude_cli"]
    assert "reviewer_exec_fallbacks" in L.control_state(cfg)


def test_a_config_without_fallbacks_keeps_its_policy_and_control_state(tmp_path):
    """Runs planned before this change must not see a CONFIG_CHANGED or GIT_CONTROL drift."""
    repo, wt, base, remote = make_fixture(tmp_path, defect=False)
    cfg = config(tmp_path, repo, wt)
    assert set(L.policy(cfg)) == set(L.POLICY_KEYS)
    assert "reviewer_exec_fallbacks" not in L.control_state(cfg)
    assert L.reviewer_chain(cfg) == [cfg["reviewer"]]
