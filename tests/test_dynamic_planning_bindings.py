"""Tests for runtime bindings, opaque handle table, and source isolation (G3)."""
from __future__ import annotations

import pytest

from uri_v1.execution.planning.bindings import (
    BindingError,
    Handle,
    HandleTable,
)
from uri_v1.execution.planning.contracts import PortType


def test_handle_table_issue_and_get():
    """Valid node output issues handle and value is retrievable."""
    table = HandleTable("user_1", "task_1", "run_1")
    val = {"sheets": [{"name": "Summary", "headers": ["ColA", "ColB"]}]}
    handle = table.issue("select_1", "selection", val, PortType.STRUCTURE_SELECTION)

    assert handle.node_id == "select_1"
    assert handle.port == "selection"
    assert handle.port_type == PortType.STRUCTURE_SELECTION

    retrieved = table.get("select_1", "selection")
    assert retrieved == val


def test_unissued_handle_raises_unbound_input():
    """Gate 3: Accessing an unissued handle raises UNBOUND_INPUT, never empty default (F12)."""
    table = HandleTable("user_1", "task_1", "run_1")
    with pytest.raises(BindingError) as exc:
        table.get("nonexistent_node", "port_x")
    assert exc.value.code == "UNBOUND_INPUT"


def test_cross_task_or_user_handle_validation():
    """Gate 3: Cross-user or cross-run handle fails validation."""
    table = HandleTable("user_1", "task_1", "run_1")
    val = {"sheets": []}
    handle = table.issue("node_1", "selection", val, PortType.STRUCTURE_SELECTION)

    # Forged handle with different user
    forged_user = Handle(
        user_id="user_2",
        task_id="task_1",
        run_id="run_1",
        node_id="node_1",
        port="selection",
        value_sha256=handle.value_sha256,
        port_type=handle.port_type,
    )
    assert not table.validate_handle(forged_user)

    # Forged handle with different run_id
    forged_run = Handle(
        user_id="user_1",
        task_id="task_1",
        run_id="run_2",
        node_id="node_1",
        port="selection",
        value_sha256=handle.value_sha256,
        port_type=handle.port_type,
    )
    assert not table.validate_handle(forged_run)

    # Valid handle validates
    assert table.validate_handle(handle)


def test_invalid_node_output_schema_rejected():
    """Gate 3: Invalid data for declared PortType is rejected at handle issue time."""
    table = HandleTable("user_1", "task_1", "run_1")
    invalid_val = "just_a_string_not_a_selection"
    with pytest.raises(BindingError) as exc:
        table.issue("node_1", "selection", invalid_val, PortType.STRUCTURE_SELECTION)
    assert exc.value.code == "INVALID_NODE_OUTPUT"
