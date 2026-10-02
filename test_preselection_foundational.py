"""Registry-declared foundational capabilities remain visible to the Brain."""

from contextlib import nullcontext
from unittest.mock import patch

from uri_core.core.capability_directory import CapabilityDirectory
from uri_core.core.capability_feasibility import CapabilityFeasibility
from uri_core.core.capability_registry import CapabilityRegistry
from uri_core.core.decision_engine import preselect_candidate_ids


def _directory(registry_path, raw_registry=None):
    with patch("uri_core.core.capability_feasibility.list_connection_status", return_value=[]):
        registry_override = (
            patch.object(CapabilityRegistry, "_load_raw", return_value=raw_registry)
            if raw_registry is not None else nullcontext()
        )
        with registry_override:
            feasibility = CapabilityFeasibility(registry_path=str(registry_path))
            snapshot = feasibility.snapshot()
            directory = CapabilityDirectory(
                capability_feasibility=feasibility, include_procedures=False
            )
    return snapshot, directory


def test_registry_foundational_boolean_flows_to_snapshot_and_directory():
    raw_registry = {"active_tools": {
            "declared": {"description": "A declared capability", "foundational": True},
            "invalid": {"description": "An invalid declaration", "foundational": "true"},
            "ordinary": {"description": "An ordinary capability"},
        }}
    with patch.object(CapabilityRegistry, "_load_raw", return_value=raw_registry):
        registry = CapabilityRegistry()
        assert registry.describe_status("declared").foundational is True
        assert registry.describe_status("invalid").foundational is None
        snapshot, directory = _directory("unused", raw_registry)
        assert snapshot["declared"]["foundational"] is True
        assert snapshot["invalid"]["foundational"] is None
        assert directory.describe("declared")["foundational"] is True
        assert directory.describe("invalid")["foundational"] is False
        assert directory.describe("ordinary")["foundational"] is False


def test_web_search_and_memory_foundational_without_lexical_match():
    _, directory = _directory("uri_workspace/capabilities_registry.json")
    request = "Check for any recruitment notice from the District Court Gangtok"
    candidates = preselect_candidate_ids(
        {"turn": {"user_text": request}}, directory, limit=1
    )

    assert {"web_search", "remember_fact", "recall_memory"} <= set(candidates)
    assert directory.describe("web_search")["foundational"] is True
    assert directory.describe("recall_memory")["foundational"] is True
    assert "generate_document" not in candidates


def test_non_foundational_capability_still_needs_lexical_preselection():
    raw_registry = {"active_tools": {
            "alpha": {"description": "Alpha task", "foundational": True},
            "beta": {"description": "Beta task"},
        }}
    _, directory = _directory("unused", raw_registry)

    candidates = preselect_candidate_ids(
        {"turn": {"user_text": "alpha"}}, directory, limit=1
    )
    assert "alpha" in candidates
    assert "beta" not in candidates
