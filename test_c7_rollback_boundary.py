"""C7 second review: the rollback allow-list cannot alias, widen authority or restore private state.

The rehearsal writes only into a fresh work/c1 directory. These tests attack what the
archive may contain: Windows name aliasing (so the evidence would describe bytes that
are not on disk), a substituted catalogue that widens authority, and private state.
"""
import hashlib
import json
from pathlib import Path
import uuid
import zipfile

import pytest

from scripts.phase1_offline_rollback import rehearse

ROOT = Path(__file__).resolve().parent
CATALOGUE = "uri_workspace/capabilities_registry.json"


def archive(members):
    checkpoint = ROOT / "work/c1/checkpoints"
    checkpoint.mkdir(parents=True, exist_ok=True)
    z = checkpoint / ("negative_" + uuid.uuid4().hex + ".zip")
    with zipfile.ZipFile(z, "w") as a:
        for name, data in members:
            a.writestr(name, data)
    return z, hashlib.sha256(z.read_bytes()).hexdigest(), ROOT / "work/c1" / ("negative_restore_" + uuid.uuid4().hex)


def catalogue(mutate):
    data = json.loads((ROOT / CATALOGUE).read_text(encoding="utf-8"))
    mutate(data)
    return json.dumps(data)


@pytest.mark.parametrize("names", [
    ["uri_core/a.py", "uri_core/A.py"],                      # case-insensitive collision on NTFS
    ["uri_core/core./x.py"], ["uri_core/x.py "],              # trailing dot/space alias another name
    ["uri_core/CLIENT~1/x.py"],                               # 8.3 short-name alias
    ["uri_core/con.py"], ["docs/AUX.md"], ["tests/lpt1.py"],  # device names
    ["uri_core/core/TURN_STATE.py"],                          # differs only in case from a baseline file
    ["uri_core/x.py:stream"],                                 # alternate data stream
])
def test_windows_name_aliasing_is_refused_before_writing(names):
    z, sha, dest = archive([(n, "value = 1\n") for n in names])
    with pytest.raises(ValueError):
        rehearse(z, sha, dest)
    assert not dest.exists()


@pytest.mark.parametrize("mutate", [
    lambda d: d["active_tools"]["external_harness_task"].update(availability="available"),
    lambda d: d["active_tools"]["external_harness_task"].update(approval_requirement="none"),
    lambda d: d["active_tools"]["external_harness_task"].update(execution_surface="server"),
    lambda d: d["active_tools"]["gmail_create_draft"].update(approval_requirement="none"),
    lambda d: d["active_tools"]["drive_upload"].update(effect_type="read_only"),
    lambda d: d["active_tools"].update(new_tool={"availability": "available", "approval_requirement": "none"}),
    lambda d: d.update(active_tools=[]),
])
def test_substituted_catalogue_that_widens_authority_is_refused(mutate):
    z, sha, dest = archive([(CATALOGUE, catalogue(mutate))])
    with pytest.raises(ValueError, match="CATALOGUE"):
        rehearse(z, sha, dest)
    assert not dest.exists()


# Third review: planned_capabilities was never inspected. CapabilityRegistry turns planned entries into
# descriptors that honour their own status/approval, and id-keyed consumers (feasibility snapshot, the
# native tool loop's effect map) let a planned duplicate override the ACTIVE entry of the same id.
PLANNED_DUPLICATE = {"status": "implemented", "availability": "available", "approval_requirement": "none",
                     "effect_type": "read_only"}


@pytest.mark.parametrize("mutate", [
    lambda d: d["planned_capabilities"].update(gmail_create_draft=PLANNED_DUPLICATE),
    lambda d: d["planned_capabilities"].update(brand_new_tool=PLANNED_DUPLICATE),
    lambda d: next(iter(d["planned_capabilities"].values())).update(status="implemented"),
    lambda d: d.update(extra_authority={"anything": True}),
    lambda d: d.update(schema_version="other"),
    lambda d: d["active_tools"]["remember_fact"].update(foundational=1),   # 1 == True in Python, not in JSON
])
def test_substituted_planned_or_top_level_catalogue_content_is_refused(mutate):
    z, sha, dest = archive([(CATALOGUE, catalogue(mutate))])
    with pytest.raises(ValueError, match="CATALOGUE"):
        rehearse(z, sha, dest)
    assert not dest.exists()


def test_planned_duplicate_really_overrides_active_authority_in_id_keyed_consumers(tmp_path):
    """Control: the attack above is real, so its refusal is not vacuous."""
    from uri_core.core.capability_registry import CapabilityRegistry
    path = tmp_path / "registry.json"
    path.write_text(catalogue(lambda d: d["planned_capabilities"].update(gmail_create_draft=PLANNED_DUPLICATE)))
    by_id = {d.id: d for d in CapabilityRegistry(str(path)).list_capabilities()}
    assert by_id["gmail_create_draft"].approval_requirement == "none"
    assert by_id["gmail_create_draft"].effect_type == "read_only"


def test_catalogue_that_only_narrows_restores_and_tree_matches_evidence():
    z, sha, dest = archive([(CATALOGUE, catalogue(lambda d: d["active_tools"].pop("external_harness_task")))])
    evidence = rehearse(z, sha, dest)
    restored = {q.relative_to(dest).as_posix() for q in dest.rglob("*") if q.is_file()}
    assert evidence["restored_files"] == len(restored) - 1  # plus rollback-evidence.json
    assert not any(n.startswith(("work/", "uri_workspace/")) and n != CATALOGUE for n in restored)


@pytest.mark.parametrize("private", [
    "work/c1/x/secure/client-key.dpapi", "work/c1/x/private/store.json", "uri_workspace/sessions.db",
    "uri_workspace/users/u/state.json", "credentials.json", ".env", "work/c1/checkpoints/a.json",
    "uri_core/secure/key.dpapi", "fixtures/c4_harness/secret.json", "uri_ui/lib/main.dart",
])
def test_private_state_and_out_of_scope_files_are_refused(private):
    z, sha, dest = archive([(private, "{}")])
    with pytest.raises(ValueError):
        rehearse(z, sha, dest)
    assert not dest.exists()
