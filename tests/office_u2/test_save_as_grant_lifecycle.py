"""A closed authoring Save as card cannot keep a destination folder in use."""

from types import SimpleNamespace

import pytest

from uri_office.approvals import Approvals
from uri_office.authoring.session import AuthSession, Authoring, blank_pptx
from uri_office.errors import OfficeError
from uri_office.grants import Grants


def _action(messages, button, name):
    sid = messages[0]["createSurface"]["surfaceId"]
    model = messages[2]["updateDataModel"]["value"]
    return {"name": name, "surfaceId": sid, "sourceComponentId": button,
            "context": {"surface_digest": model["bound"]["surface"]["digest"],
                        "change_sha256": model["bound"]["change_sha256"]}}


class _Documents:
    def get(self, _):
        return SimpleNamespace(state="ready")

    def close(self, _):
        pass


@pytest.mark.parametrize("finish", ["decline", "supersede", "apply", "close"])
def test_authoring_save_as_releases_card_grant_but_keeps_active_edit(tmp_path, finish):
    destination = tmp_path / "chosen"
    destination.mkdir()
    grants = Grants([], tmp_path / "folders.json")
    grants.add_folder(str(destination))
    state = tmp_path / "state"
    state.mkdir()
    approvals = Approvals(state, "owner")
    approvals.on_close = grants.revoke
    authoring = Authoring(state, _Documents(), grants, approvals)
    edit = AuthSession("edit", "pptx", "New.pptx", None, None, None, [blank_pptx()], preview_doc="preview")
    authoring.sessions[edit.aid] = edit
    first = authoring.propose_save(edit.aid, str(destination / "first.pptx"))
    with pytest.raises(OfficeError) as error:
        grants.remove_folder(str(destination))
    assert error.value.code == "FOLDER_IN_USE"
    if finish == "decline":
        approvals.action(_action(first["messages"], "reject", "office.reject_change"), authoring.apply_save)
        assert grants.remove_folder(str(destination))["removed"] is True
    elif finish == "supersede":
        second = authoring.propose_save(edit.aid, str(destination / "second.pptx"))
        approvals.action(_action(second["messages"], "reject", "office.reject_change"), authoring.apply_save)
        assert grants.remove_folder(str(destination))["removed"] is True
    elif finish == "apply":
        approvals.action(_action(first["messages"], "apply", "office.apply_change"), authoring.apply_save)
        assert grants.get(edit.grant_id, "open").path == destination / "first.pptx"
        with pytest.raises(OfficeError) as error:
            grants.remove_folder(str(destination))
        assert error.value.code == "FOLDER_IN_USE"
    else:
        authoring.close(edit.aid)
    if finish != "close":
        authoring.close(edit.aid)
    if finish in ("apply", "close"):
        assert grants.remove_folder(str(destination))["removed"] is True
