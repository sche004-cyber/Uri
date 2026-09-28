"""Approval-gate negation strengthening (Chetan, 2026-09-28).

`negated()` (M36, uri_v1.memory.contracts) only catches formal negation. Real
replies to an approval prompt also use informal negative interjections it
doesn't cover ("nah", "nope"), which let a reply like "nah apply it" or "nope,
allow network" be read as consent because it still contains an approval word.
`uri_v1.execution.approval.approval_declined` adds exactly that, shared across
the three approval/grant gates below, without touching M36 or negated() itself.
"""
from __future__ import annotations

import pytest

from tests.m37_edge_support import intake
from uri_v1.execution.approval import approval_declined
from uri_v1.execution.harness.contracts import CapabilityGrant, ElevationGrant, HarnessError
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
    assert g.elevation == "extra_dir:/home/someone/e"


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
