"""Second review of the shared Turn State change (JSON-only active pointer).

Base e8e3b65 put Fact objects into active_pointer.known_inputs; the legacy decision
request is serialised with json.dumps, so any paused workflow with a stored fact raised
TypeError. These tests pin the repaired projection: values only, JSON-safe, current facts
only (superseded values never become inputs), and C5 intent records project their own slots.
"""
import json

from uri_core.core.fact_manager import update_fact
from uri_core.core.facts import Fact
from uri_core.core.state import SessionManager, SessionState
from uri_core.core.turn_state import _project_active_pointer


def paused():
    s = SessionState(session_id="s")
    s.active_workflow = {"capability": "student_lookup", "action": "find", "goal": "Find the student"}
    s.active_workflow_question = "Which roll number?"
    s.active_workflow_required_field = "roll_number"
    s.active_workflow_status = "waiting_for_input"
    return s


def test_legacy_fact_objects_project_to_json_values():
    s = paused()
    update_fact(s, Fact(name="department", value="CS", status="CONFIRMED", source="user"))
    pointer = _project_active_pointer(s)
    assert pointer["known_inputs"] == {"department": "CS"}
    json.dumps(pointer)


def test_superseded_value_never_becomes_a_known_input():
    s = paused()
    update_fact(s, Fact(name="department", value="CS", status="CONFIRMED", source="user"))
    update_fact(s, Fact(name="department", value="EE", status="CONFIRMED", source="user"))
    assert _project_active_pointer(s)["known_inputs"] == {"department": "EE"}


def test_projection_is_identical_after_a_persistence_round_trip(tmp_path):
    s = paused()
    update_fact(s, Fact(name="department", value="CS", status="CONFIRMED", source="user"))
    codec = SessionManager.__new__(SessionManager)
    restored = SessionState(session_id="s")
    restored.__dict__.update(paused().__dict__)
    restored.current_facts = codec._deserialize_fact_collection(
        json.loads(json.dumps(codec._serialize_fact_collection(s.current_facts))))
    assert _project_active_pointer(restored) == _project_active_pointer(s)


def test_intent_record_projects_only_its_slot_values():
    s = SessionState(session_id="t")
    s.active_workflow = {"schema": "uri.intent.v1", "capability": "remember_fact",
                         "slots": {"statement": {"value": "x is due on Monday", "source": "user"}, "junk": "not-a-slot"}}
    s.active_workflow_question = "Confirm?"
    update_fact(s, Fact(name="unrelated", value="must not leak", status="CONFIRMED", source="user"))
    pointer = _project_active_pointer(s)
    assert pointer["known_inputs"] == {"statement": "x is due on Monday"}
    json.dumps(pointer)
