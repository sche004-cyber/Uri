"""Approval-gate negation strengthening (Chetan, 2026-09-28).

`negated()` (M36, uri_v1.memory.contracts) only catches formal negation. Real
replies to an approval prompt also use informal negative interjections it
doesn't cover ("nah", "nope"), which let a reply like "nah apply it" or "nope,
allow network" be read as consent because it still contains an approval word.
`uri_v1.execution.approval.approval_declined` adds exactly that, shared across
the three approval/grant gates below, without touching M36 or negated() itself.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.m37_edge_support import intake
from uri_v1.execution.approval import approval_declined
from uri_v1.execution.harness.contracts import CapabilityGrant, ElevationGrant, HarnessError, PermissionProfile
from uri_v1.execution.workspace import WorkspaceError, WritebackApproval

RUN_ID = "r" * 32


# -- direct unit coverage of the shared mechanism ------------------------------------------------

@pytest.mark.parametrize("text", [
    "nah apply it", "nope apply it", "nope, apply it", "Nope, apply it!", "NAH. Apply it.",
    "nah, allow network", "  nah  ", "nope.", "apply it, nah", "nah allow the git server",
])
def test_informal_negatives_are_declined(text):
    assert approval_declined(text) is True


@pytest.mark.parametrize("text", [
    "yes, apply the fix", "approve", "yes apply", "allow the git server",
    "yes, allow access to /home/someone/e for this run", "confirm",
    "yes, allow network access for this run", "channel banana",  # substring, not a whole-word hit
])
def test_positive_controls_are_not_declined(text):
    assert approval_declined(text) is False


@pytest.mark.parametrize("text", [
    "don't apply it", "do not apply it", "never apply it", "skip it", "apply it? no",
])
def test_formal_negation_still_declined(text):
    assert approval_declined(text) is True


# -- WritebackApproval (M37) ---------------------------------------------------------------------

@pytest.mark.parametrize("text", ["nah apply it", "nope apply it", "Nope, apply it!", "NAH. Apply it."])
def test_writeback_approval_rejects_informal_negatives(text):
    with pytest.raises(WorkspaceError, match="EXPLICIT_APPROVAL_REQUIRED"):
        WritebackApproval.from_user(intake(text), RUN_ID, {"report.py": "0" * 64})


def test_writeback_approval_accepts_positive_with_path_like_value():
    ap = WritebackApproval.from_user(intake("yes, apply the fix"), RUN_ID, {"report.py": "0" * 64})
    assert ap.relpaths == ("report.py",)


def test_writeback_approval_still_rejects_formal_negation():
    with pytest.raises(WorkspaceError, match="EXPLICIT_APPROVAL_REQUIRED"):
        WritebackApproval.from_user(intake("don't apply it"), RUN_ID, {"report.py": "0" * 64})


# -- ElevationGrant (M38) -------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["nah allow network", "nope, allow network access for this run"])
def test_elevation_grant_rejects_informal_negatives(text):
    with pytest.raises(HarnessError, match="EXPLICIT_ELEVATION_REQUIRED"):
        ElevationGrant.from_user(intake(text), "network", "run-1")


def test_elevation_grant_accepts_positive_extra_dir_path():
    g = ElevationGrant.from_user(intake("yes, allow access to /home/someone/e for this run"),
                                 "extra_dir:/home/someone/e", "run-1")
    assert g.elevation == f"extra_dir:{Path('/home/someone/e').resolve()}"  # C:\home\someone\e on Windows


def test_elevation_grant_still_rejects_formal_negation():
    with pytest.raises(HarnessError, match="EXPLICIT_ELEVATION_REQUIRED"):
        ElevationGrant.from_user(intake("do not allow network"), "network", "run-1")


# -- CapabilityGrant (M38) ------------------------------------------------------------------------

def test_capability_grant_rejects_informal_negative():
    with pytest.raises(HarnessError, match="EXPLICIT_CAPABILITY_GRANT_REQUIRED"):
        CapabilityGrant.from_user(intake("nah allow the git server"), [("MCP_SERVER", "git")])


def test_capability_grant_accepts_positive():
    g = CapabilityGrant.from_user(intake("allow the git server"), [("MCP_SERVER", "git")])
    assert g.items == (("MCP_SERVER", "git"),)


# -- .valid()/.valid_for() re-check the decline test too, not only trust+shape ---------------------
# (Codex audit, 2026-09-28): a grant/approval built directly, bypassing `from_user`, from text that
# reads as declined must still fail the gate that `write_back`/harness code actually calls.

def test_writeback_approval_valid_rejects_directly_constructed_declined_intake():
    ap = WritebackApproval(RUN_ID, ("report.py",), {"report.py": "0" * 64}, intake("do not approve"))
    assert ap.valid() is False


def test_elevation_grant_valid_for_rejects_directly_constructed_declined_intake():
    g = ElevationGrant("network", "run-1", intake("nah allow network"))
    assert g.valid_for("run-1") is False


def test_capability_grant_valid_rejects_directly_constructed_declined_intake():
    g = CapabilityGrant((("MCP_SERVER", "git"),), intake("nah allow the git server"))
    assert g.valid() is False


def test_capability_grant_valid_still_true_for_none():
    assert CapabilityGrant.none().valid() is True


# -- only `from_user` issues a valid approval/grant ------------------------------------------------
# (Codex audit, requalification of 6420f3e): 6420f3e re-checked only the decline test, so a
# directly built approval/grant whose text has no approval word at all still validated, and
# `PermissionProfile().elevate(...)` granted network. `from_user` is now the only issuer.

NO_APPROVAL_WORD = ("show me the diff", "what changed?", "network", "thanks")


@pytest.mark.parametrize("text", NO_APPROVAL_WORD)
def test_directly_built_writeback_approval_never_validates(text):
    assert WritebackApproval(RUN_ID, ("report.py",), {"report.py": "0" * 64}, intake(text)).valid() is False


@pytest.mark.parametrize("text", NO_APPROVAL_WORD)
def test_directly_built_elevation_grant_never_validates_or_elevates(text):
    g = ElevationGrant("network", "scope1", intake(text))
    assert g.valid_for("scope1") is False
    with pytest.raises(HarnessError): PermissionProfile().elevate(g, "scope1")
    with pytest.raises(HarnessError): PermissionProfile(network=True, grants=(g,))


@pytest.mark.parametrize("text", NO_APPROVAL_WORD)
def test_directly_built_capability_grant_never_validates(text):
    assert CapabilityGrant((("MCP_SERVER", "git"),), intake(text)).valid() is False


def test_from_user_issued_grants_still_validate_and_copies_do_not():
    import dataclasses
    ap = WritebackApproval.from_user(intake("yes, apply the fix"), RUN_ID, {"report.py": "0" * 64})
    assert ap.valid() and not dataclasses.replace(ap).valid()
    g = ElevationGrant.from_user(intake("yes, allow network access"), "network", "scope1")
    assert g.valid_for("scope1") and PermissionProfile().elevate(g, "scope1").network
    assert not dataclasses.replace(g).valid_for("scope1")
    c = CapabilityGrant.from_user(intake("allow the git server"), [("MCP_SERVER", "git")])
    assert c.valid() and not dataclasses.replace(c).valid()


# -- CapabilityGrant needs an explicit grant verb, not just the name ------------------------------
# (Codex requalification of 4cd360f, plan AC-H5): "show me sheets" etc. named the capability
# without granting it and were issued as valid grants.

@pytest.mark.parametrize("text", ["show me sheets", "thanks sheets", "what is sheets", "sheets"])
def test_capability_named_without_a_grant_verb_is_refused(text):
    with pytest.raises(HarnessError, match="EXPLICIT_CAPABILITY_GRANT_REQUIRED"):
        CapabilityGrant.from_user(intake(text), [("MCP_SERVER", "sheets")])
    assert CapabilityGrant((("MCP_SERVER", "sheets"),), intake(text)).valid() is False  # nor built directly


@pytest.mark.parametrize("text", ["allow sheets", "yes, enable the sheets server", "use the sheets server",
                                  "approve sheets for this run", "grant sheets"])
def test_capability_grant_with_an_explicit_verb_is_issued(text):
    assert CapabilityGrant.from_user(intake(text), [("MCP_SERVER", "sheets")]).valid()


# -- a question or hypothetical is never a grant ----------------------------------------------------
# (Codex bridge probe of f9ac385, plan AC-H5). One shared test, `approval_withheld`, in every gate.

QUESTION_OR_HYPOTHETICAL_USE = ("can I use sheets?", "should we use sheets", "how would I use sheets", "maybe use sheets",
                                "if you use sheets it breaks", "do you use sheets", "use it? sheets")


@pytest.mark.parametrize("text", QUESTION_OR_HYPOTHETICAL_USE + ("use sheets? no", "I wouldn't use sheets",
                                                                   "I used sheets yesterday", "show me sheets"))
def test_capability_question_or_hypothetical_is_not_a_grant(text):
    with pytest.raises(HarnessError, match="EXPLICIT_CAPABILITY_GRANT_REQUIRED"):
        CapabilityGrant.from_user(intake(text), [("MCP_SERVER", "sheets")])
    assert CapabilityGrant((("MCP_SERVER", "sheets"),), intake(text)).valid() is False


@pytest.mark.parametrize("text", ["can I allow network?", "should we allow network", "can I allow network",
                                  "maybe allow network", "if you allow network it breaks", "allow network?"])
def test_elevation_question_or_hypothetical_is_not_a_grant(text):
    with pytest.raises(HarnessError, match="EXPLICIT_ELEVATION_REQUIRED"):
        ElevationGrant.from_user(intake(text), "network", "scope1")


@pytest.mark.parametrize("text", ["should I apply it?", "can you apply it", "yes, apply it?", "maybe apply it",
                                  "what if I approve this", "would you apply the fix"])
def test_writeback_question_or_hypothetical_is_not_an_approval(text):
    with pytest.raises(WorkspaceError, match="EXPLICIT_APPROVAL_REQUIRED"):
        WritebackApproval.from_user(intake(text), RUN_ID, {"report.py": "0" * 64})


@pytest.mark.parametrize("text", ["yes, allow network access for this run", "allow network", "ok, please enable internet access"])
def test_explicit_elevation_is_still_granted(text):
    assert ElevationGrant.from_user(intake(text), "network", "scope1").valid_for("scope1")


# -- positive allowlist (Codex bridge probe of c7832b9) -------------------------------------------
# Only grant verbs, the granted data (names, path, file names) and closed fillers make a grant;
# a hedge, condition or extra clause anywhere in the turn does not.

HEDGED_CAPABILITY = ("please can we use sheets", "I guess use sheets", "just wondering if we use sheets", "so can I use sheets",
                     "I think maybe use sheets", "use sheets maybe", "use sheets, I wonder", "we could use sheets",
                     "not sure, use sheets")
HEDGED_ELEVATION = ("ok so should we allow network", "hmm maybe allow network", "yes, allow network if needed",
                    "allow network, it's needed", "allow network unless it fails")


@pytest.mark.parametrize("text", HEDGED_CAPABILITY)
def test_hedged_capability_grant_is_refused(text):
    with pytest.raises(HarnessError, match="EXPLICIT_CAPABILITY_GRANT_REQUIRED"):
        CapabilityGrant.from_user(intake(text), [("MCP_SERVER", "sheets")])
    assert CapabilityGrant((("MCP_SERVER", "sheets"),), intake(text)).valid() is False


@pytest.mark.parametrize("text", HEDGED_ELEVATION)
def test_hedged_elevation_is_refused(text):
    with pytest.raises(HarnessError, match="EXPLICIT_ELEVATION_REQUIRED"):
        ElevationGrant.from_user(intake(text), "network", "scope1")


@pytest.mark.parametrize("text", ["I guess apply it", "apply it, I think", "yes apply report.py unless it breaks",
                                  "ok so yes apply", "we could apply the fix"])
def test_hedged_writeback_approval_is_refused(text):
    with pytest.raises(WorkspaceError, match="EXPLICIT_APPROVAL_REQUIRED"):
        WritebackApproval.from_user(intake(text), RUN_ID, {"report.py": "0" * 64})


@pytest.mark.parametrize("text", ["yes, apply the fix", "yes apply report.py", "ok, please apply the fix", "approve"])
def test_explicit_writeback_approval_is_issued(text):
    assert WritebackApproval.from_user(intake(text), RUN_ID, {"report.py": "0" * 64}).valid()


def test_path_and_names_are_data_not_words(tmp_path):
    d = tmp_path / "quarterly-reports" / "2026"; d.mkdir(parents=True)
    g = ElevationGrant.from_user(intake(f"yes, allow access to {d} for this run"), f"extra_dir:{d}", "run-1")
    assert g.valid_for("run-1")
    with pytest.raises(HarnessError):  # the path is data, but a hedge around it still is not a grant
        ElevationGrant.from_user(intake(f"maybe allow access to {d} I guess"), f"extra_dir:{d}", "run-1")
    assert CapabilityGrant.from_user(intake("use the sheets server and the xlsx-helper skill"),
                                     [("MCP_SERVER", "sheets"), ("SKILL", "xlsx-helper")]).valid()


def test_approval_uncertain_helper():
    from uri_v1.execution.approval import approval_uncertain, approval_withheld
    assert approval_uncertain("can I use sheets?") and approval_uncertain("Perhaps allow it")
    assert approval_uncertain("allow it？")  # fullwidth question mark
    assert not approval_uncertain("yes, apply it") and not approval_uncertain("allow the git server")
    assert approval_withheld("nah apply it") and approval_withheld("maybe apply it")


# -- hedged or speculative language never authorizes (Chetan, 2026-09-28 17:53) ----------------------
# Every hedge, in front of, inside and after an otherwise-valid grant, for all four grant kinds.

HEDGES = ("could", "I guess", "maybe", "perhaps", "might", "possibly", "probably", "I think", "I suppose",
          "hopefully", "would", "should", "may", "if needed", "unless", "presumably", "ideally", "kind of")


def _placements(hedge, grant):
    head, _, tail = grant.partition(" ")
    return (f"{hedge} {grant}", f"{grant} {hedge}", f"{head} {hedge} {tail}", f"{grant}, {hedge}")


@pytest.mark.parametrize("hedge", HEDGES)
def test_hedge_never_authorizes_a_capability(hedge):
    assert CapabilityGrant.from_user(intake("use the sheets server"), [("MCP_SERVER", "sheets")]).valid()
    for text in _placements(hedge, "use the sheets server"):
        with pytest.raises(HarnessError):
            CapabilityGrant.from_user(intake(text), [("MCP_SERVER", "sheets")])


@pytest.mark.parametrize("hedge", HEDGES)
def test_hedge_never_authorizes_an_elevation(hedge):
    assert ElevationGrant.from_user(intake("allow network access"), "network", "scope1").valid_for("scope1")
    for text in _placements(hedge, "allow network access"):
        with pytest.raises(HarnessError):
            ElevationGrant.from_user(intake(text), "network", "scope1")


@pytest.mark.parametrize("hedge", HEDGES)
def test_hedge_never_authorizes_an_extra_dir(hedge, tmp_path):
    d = tmp_path / "reports"; d.mkdir()
    grant = f"allow access to {d}"
    assert ElevationGrant.from_user(intake(grant), f"extra_dir:{d}", "scope1").valid_for("scope1")
    for text in _placements(hedge, grant):
        with pytest.raises(HarnessError):
            ElevationGrant.from_user(intake(text), f"extra_dir:{d}", "scope1")


@pytest.mark.parametrize("hedge", HEDGES)
def test_hedge_never_authorizes_a_writeback(hedge):
    assert WritebackApproval.from_user(intake("yes apply the fix"), RUN_ID, {"report.py": "0" * 64}).valid()
    for text in _placements(hedge, "yes apply the fix"):
        with pytest.raises(WorkspaceError):
            WritebackApproval.from_user(intake(text), RUN_ID, {"report.py": "0" * 64})


# -- declaratives, time/scope qualifiers and dotted names never authorize --------------------------
# (Codex re-check of 249660e.) "i", "now", "just", "on", "for", "this" and "run" are no longer
# fillers; the only scope phrase accepted is the exact "for this run". A granted name must stand
# on its own: "sheets.server" does not name "sheets". Every string Codex reported is a case here.

CODEX_CAPABILITY = ("I use sheets", "use sheets for now", "use sheets.server", "I approve sheets for this run",
                    "use sheets just for this", "use sheets on", "use sheets for this", "use 'sheets'.server",
                    "use sheets-server", "use x/sheets")
CODEX_ELEVATION = ("I allow network", "yes allow network for now", "yes allow network just for this",
                   "allow network on", "allow network for this", "allow network for the run", "allow network here")
CODEX_WRITEBACK = ("I apply the fix", "yes apply the fix for now", "apply the fix just for this", "apply the fix on",
                   "yes apply report.py.bak", "I approve")


@pytest.mark.parametrize("text", CODEX_CAPABILITY)
def test_declarative_qualified_or_dotted_capability_is_refused(text):
    with pytest.raises(HarnessError, match="EXPLICIT_CAPABILITY_GRANT_REQUIRED"):
        CapabilityGrant.from_user(intake(text), [("MCP_SERVER", "sheets")])


@pytest.mark.parametrize("text", CODEX_ELEVATION)
def test_declarative_or_qualified_elevation_is_refused(text):
    with pytest.raises(HarnessError):
        ElevationGrant.from_user(intake(text), "network", "scope1")


@pytest.mark.parametrize("tail", ["for now", "just for this", "on", "for this"])
def test_qualified_extra_dir_is_refused(tail, tmp_path):
    d = tmp_path / "reports"; d.mkdir()
    with pytest.raises(HarnessError):
        ElevationGrant.from_user(intake(f"yes allow access to {d} {tail}"), f"extra_dir:{d}", "scope1")
    with pytest.raises(HarnessError):
        ElevationGrant.from_user(intake(f"I allow access to {d}"), f"extra_dir:{d}", "scope1")


@pytest.mark.parametrize("text", CODEX_WRITEBACK)
def test_declarative_qualified_or_dotted_writeback_is_refused(text):
    with pytest.raises(WorkspaceError):
        WritebackApproval.from_user(intake(text), RUN_ID, {"report.py": "0" * 64})


def test_exact_run_scope_and_sentence_punctuation_still_grant(tmp_path):
    d = tmp_path / "reports"; d.mkdir()
    assert CapabilityGrant.from_user(intake("use sheets for this run."), [("MCP_SERVER", "sheets")]).valid()
    assert CapabilityGrant.from_user(intake("yes, use 'sheets', please"), [("MCP_SERVER", "sheets")]).valid()
    assert ElevationGrant.from_user(intake("yes allow network for this run"), "network", "s").valid_for("s")
    assert ElevationGrant.from_user(intake(f"yes, allow access to {d} for this run."), f"extra_dir:{d}", "s").valid_for("s")
    assert WritebackApproval.from_user(intake("yes, apply report.py."), RUN_ID, {"report.py": "0" * 64}).valid()


# -- dangling referents and non-standalone elevation names never authorize --------------------------
# (Codex re-check of f8115d5.) Fillers are now only assent/politeness words; "it", "that", "in",
# "with", "to", "access" are not. "access to <path>" is accepted only as that exact phrase, and an
# elevation's own words must stand alone. Every string Codex reported is a case here.

REFERENT_CAPABILITY = ("use sheets with it", "use sheets in that", "use sheets to it", "use sheets, it's fine")
REFERENT_ELEVATION = ("allow network in that", "allow network.server", "allow network-server", "allow network with it",
                      "allow it network", "allow internet.web", "allow pip.install")
REFERENT_WRITEBACK = ("apply the fix with it", "yes, apply it", "apply the fix in that", "apply that")


@pytest.mark.parametrize("text", REFERENT_CAPABILITY)
def test_dangling_referent_capability_is_refused(text):
    with pytest.raises(HarnessError):
        CapabilityGrant.from_user(intake(text), [("MCP_SERVER", "sheets")])


@pytest.mark.parametrize("text", REFERENT_ELEVATION)
def test_dangling_referent_or_joined_elevation_is_refused(text):
    elevation = "package_install" if "pip" in text else "network"
    with pytest.raises(HarnessError):
        ElevationGrant.from_user(intake(text), elevation, "scope1")


@pytest.mark.parametrize("tail", ["in that", "with it", "to it"])
def test_dangling_referent_extra_dir_is_refused(tail, tmp_path):
    d = tmp_path / "reports"; d.mkdir()
    with pytest.raises(HarnessError):
        ElevationGrant.from_user(intake(f"yes allow access to {d} {tail}"), f"extra_dir:{d}", "scope1")
    with pytest.raises(HarnessError):  # "to" is only accepted inside the exact "access to <path>"
        ElevationGrant.from_user(intake(f"yes allow to {d}"), f"extra_dir:{d}", "scope1")


@pytest.mark.parametrize("text", REFERENT_WRITEBACK)
def test_dangling_referent_writeback_is_refused(text):
    with pytest.raises(WorkspaceError):
        WritebackApproval.from_user(intake(text), RUN_ID, {"report.py": "0" * 64})


def test_plain_grants_still_work_after_the_filler_cut(tmp_path):
    d = tmp_path / "reports"; d.mkdir()
    assert ElevationGrant.from_user(intake("yes, allow network access for this run"), "network", "s").valid_for("s")
    assert ElevationGrant.from_user(intake("ok, please allow pip install"), "package_install", "s").valid_for("s")
    assert ElevationGrant.from_user(intake(f'yes, allow access to "{d}" for this run'), f"extra_dir:{d}", "s").valid_for("s")
    assert ElevationGrant.from_user(intake(f"allow {d}"), f"extra_dir:{d}", "s").valid_for("s")
    assert CapabilityGrant.from_user(intake("yes, use the sheets server, thanks"), [("MCP_SERVER", "sheets")]).valid()
    assert WritebackApproval.from_user(intake("yes, go ahead and apply the fix"), RUN_ID, {"report.py": "0" * 64}).valid()
