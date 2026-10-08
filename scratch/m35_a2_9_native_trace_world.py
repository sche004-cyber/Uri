"""M35 URIv1 A2.9 -- Riverside Depot Console: deterministic synthetic environment.

Disposable pilot harness. Not production URI code. See
docs/plans/M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_PLAN.md.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional, Tuple

CAPABILITY_CATALOG = [
    {"action": "inspect_capabilities", "description": "List all actions currently available in this console.", "params": []},
    {"action": "lookup_record", "description": "Retrieve one specific record by its type and identifier, if it exists.", "params": ["record_type", "record_id"]},
    {"action": "search_records", "description": "Search all records of a given type for ones matching free-text terms.", "params": ["record_type", "filter_text"]},
    {"action": "update_record", "description": "Change one field on an existing record to a new value.", "params": ["record_type", "record_id", "field", "value"]},
    {"action": "move_item", "description": "Relocate an inventory item from one storage bin to another.", "params": ["sku", "from_bin", "to_bin"]},
    {"action": "dispatch_shipment", "description": "Mark a packed shipment as dispatched from the loading dock.", "params": ["shipment_id"]},
    {"action": "contact_user", "description": "Pause and ask the human operator a direct question when information is missing.", "params": ["question"]},
    {"action": "finish", "description": "End this turn and report your result or answer to the human operator.", "params": ["answer"]},
]

INVENTORY_FIXTURES = {
    "SKU-7741": {"sku": "SKU-7741", "name": "Anchor Bolts M8", "bin": "C-12", "qty": 340},
    "SKU-5510": {"sku": "SKU-5510", "name": "Rubber Gaskets", "bin": "A-04", "qty": 1200},
}
TASK_FIXTURES = {
    "T-118": {"task_id": "T-118", "description": "Repack pallet 9", "status": "OPEN"},
    "T-204": {"task_id": "T-204", "description": "Audit bin C-12", "status": "DONE"},
}
SHIPMENT_FIXTURES = {
    "SHIP-2209": {"shipment_id": "SHIP-2209", "status": "PACKED_READY"},
    "SHIP-3301": {"shipment_id": "SHIP-3301", "status": "ON_HOLD_CUSTOMS"},
}
NOTE_FIXTURES = {
    "NOTE-88": {"note_id": "NOTE-88", "content": "Transfer SKU-5510 to bin B-09 per Tuesday's count correction."},
}


def _fresh(*, inventory=None, task=None, shipment=None, note=None) -> Dict[str, Any]:
    return {
        "inventory": copy.deepcopy(inventory or {}),
        "task": copy.deepcopy(task or {}),
        "shipment": copy.deepcopy(shipment or {}),
        "note": copy.deepcopy(note or {}),
        "dispatch_calls": {},
    }


def build_s1_world() -> Dict[str, Any]:
    return _fresh(inventory={"SKU-7741": INVENTORY_FIXTURES["SKU-7741"]})


def build_s2_world() -> Dict[str, Any]:
    return _fresh(shipment={"SHIP-2209": SHIPMENT_FIXTURES["SHIP-2209"]})


def build_s3_world() -> Dict[str, Any]:
    return _fresh(inventory={"SKU-5510": INVENTORY_FIXTURES["SKU-5510"]})


def build_s4_world() -> Dict[str, Any]:
    return _fresh(shipment={"SHIP-2209": SHIPMENT_FIXTURES["SHIP-2209"], "SHIP-3301": SHIPMENT_FIXTURES["SHIP-3301"]})


def build_s5_world() -> Dict[str, Any]:
    return _fresh(inventory=dict(INVENTORY_FIXTURES), task=dict(TASK_FIXTURES))


def build_s6_world() -> Dict[str, Any]:
    return _fresh(shipment={"SHIP-2209": SHIPMENT_FIXTURES["SHIP-2209"]})


def build_s7_world() -> Dict[str, Any]:
    return _fresh(task=dict(TASK_FIXTURES))


def build_s8_world() -> Dict[str, Any]:
    return _fresh(inventory={"SKU-5510": INVENTORY_FIXTURES["SKU-5510"]}, note={"NOTE-88": NOTE_FIXTURES["NOTE-88"]})


def _search(records: Dict[str, Any], filter_text: str, text_fields) -> list:
    if not filter_text:
        return []
    terms = str(filter_text).lower().split()
    hits = []
    for rec in records.values():
        haystack = " ".join(str(rec.get(f, "")) for f in text_fields).lower()
        if any(t in haystack for t in terms):
            hits.append(rec)
    return hits


def _no_matching_task() -> Dict[str, Any]:
    """Return the frozen-table response for an action outside a scenario."""
    return {"status": "error", "code": "NO_MATCHING_TASK"}


def apply_action(world: Dict[str, Any], scenario_id: str, action: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Pure deterministic transition. Returns (observation, new_world). Never mutates input world."""
    world = copy.deepcopy(world)
    params = params or {}

    if action == "inspect_capabilities":
        return {"status": "ok", "capabilities": copy.deepcopy(CAPABILITY_CATALOG)}, world

    # The catalog is constant across scenarios, but its entries do not grant
    # every action a scenario-specific effect.  These guards implement the
    # frozen tables in the blueprint rather than letting generic record
    # mutation leak into a scenario whose environment never defines it.
    if scenario_id == "S1" and action in {"move_item", "update_record", "dispatch_shipment"}:
        return _no_matching_task(), world

    if scenario_id == "S4" and action == "update_record":
        return _no_matching_task(), world

    if scenario_id == "S5" and action == "search_records":
        filter_text = str(params.get("filter_text") or "").lower()
        if any(term in filter_text for term in ("flagged", "pallet", "supervisor")):
            return {"status": "empty", "results": []}, world

    if action == "lookup_record":
        record_type = params.get("record_type")
        record_id = params.get("record_id")
        table = world.get(record_type or "", None)
        if table is None:
            return {"status": "error", "code": "UNKNOWN_RECORD_TYPE"}, world
        rec = table.get(record_id)
        if rec is None:
            return {"status": "error", "code": "NOT_FOUND"}, world
        return {"status": "ok", "record": copy.deepcopy(rec)}, world

    if action == "search_records":
        record_type = params.get("record_type")
        filter_text = params.get("filter_text")
        table = world.get(record_type or "", None)
        if table is None:
            return {"status": "error", "code": "UNKNOWN_RECORD_TYPE"}, world
        text_fields = {
            "inventory": ("sku", "name", "bin"),
            "task": ("task_id", "description"),
            "shipment": ("shipment_id", "status"),
            "note": ("note_id", "content"),
        }.get(record_type, ())
        hits = _search(table, filter_text, text_fields)
        if not hits:
            return {"status": "empty", "results": []}, world
        return {"status": "ok", "results": copy.deepcopy(hits)}, world

    if action == "update_record":
        record_type = params.get("record_type")
        record_id = params.get("record_id")
        field = params.get("field")
        value = params.get("value")
        table = world.get(record_type or "", None)
        if table is None or record_id not in table:
            return {"status": "error", "code": "NOT_FOUND"}, world
        rec = table[record_id]
        known_fields = list(rec.keys())
        if field not in known_fields:
            return {"status": "error", "code": "UNKNOWN_FIELD", "message": f"Known fields: {', '.join(known_fields)}."}, world
        old_value = rec[field]
        try:
            new_value = type(old_value)(value) if not isinstance(old_value, str) else value
        except (TypeError, ValueError):
            new_value = value
        rec[field] = new_value
        return {"status": "ok", "old_value": old_value, "new_value": new_value}, world

    if action == "move_item":
        sku = params.get("sku")
        from_bin = params.get("from_bin")
        to_bin = params.get("to_bin")
        inv = world.get("inventory", {})
        rec = inv.get(sku)
        if rec is None:
            return {"status": "error", "code": "UNKNOWN_SKU"}, world
        known_bins = {"A-04", "B-09", "C-12"}
        if to_bin not in known_bins:
            return {"status": "error", "code": "UNKNOWN_BIN"}, world
        if from_bin is not None and rec.get("bin") != from_bin:
            return {"status": "error", "code": "FROM_BIN_MISMATCH", "message": f"Recorded bin for {sku} is not '{from_bin}'."}, world
        rec["bin"] = to_bin
        return {"status": "ok", "sku": sku, "new_bin": to_bin}, world

    if action == "dispatch_shipment":
        shipment_id = params.get("shipment_id")
        ships = world.get("shipment", {})
        rec = ships.get(shipment_id)
        if rec is None:
            return {"status": "error", "code": "NOT_FOUND"}, world
        if world["dispatch_calls"].get(shipment_id):
            return {"status": "error", "code": "ALREADY_DISPATCHED"}, world
        if rec.get("status") == "ON_HOLD_CUSTOMS":
            world["dispatch_calls"].setdefault(shipment_id, 0)
            return {"status": "error", "code": "BLOCKED_CUSTOMS_HOLD", "message": f"{shipment_id} cannot be dispatched: shipment is on customs hold."}, world
        rec["status"] = "DISPATCHED"
        world["dispatch_calls"][shipment_id] = True
        return {"status": "ok", "shipment_id": shipment_id, "new_status": "DISPATCHED"}, world

    if action == "contact_user":
        return {"status": "ok", "note": "question forwarded to user; environment has no further info"}, world

    if action == "finish":
        return {"status": "ok", "terminal": True}, world

    return _no_matching_task(), world
