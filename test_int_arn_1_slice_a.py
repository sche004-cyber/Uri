"""Offline qualification of the INT-ARN-1 Slice A evidence boundary."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from uri_core.core.file_store import FileStore
from uri_desktop_seams.reference_clarification.evidence import (
    AuthorizedReadBatch, produce_evidence,
)
from uri_desktop_seams.reference_clarification.proposal import (
    InvalidReferenceProposal, validate_reference_slots,
)
from uri_v1.memory.contracts import (
    CollisionReceipt, MemoryQuery, RetrievalResult, RetrievedCandidate, SourceRef,
)
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended


TEXT = "Open the budget.txt"
ACTIONS = {("files", "open"): {"file_id"}}
NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


@pytest.fixture
def test_dir(request):
    path = Path(".int-arn-test-work") / request.node.name
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def slot(source_class="any", expression="budget.txt"):
    start = TEXT.index(expression)
    raw = {"reference_slots": [{
        "span": {"start": start, "end": start + len(expression), "text": expression},
        "ref_key": "document",
        "target": {"capability_id": "files", "action_name": "open", "argument_name": "file_id"},
        "relation": "direct", "source_class": source_class,
    }]}
    return validate_reference_slots(raw, TEXT, ACTIONS)[0]


def store(tmp_path):
    result = FileStore(str(tmp_path / "alice"))
    first = result.save(filename="budget.txt", content=b"one", session_id="s1")
    return result, first


def produce(s, **kwargs):
    return produce_evidence(slot(), principal_id="alice", session_id="s1",
                            file_store=s, file_store_user_id="alice", now=NOW, **kwargs)


def test_slot_shape_span_target_and_backward_compatibility():
    assert validate_reference_slots({}, TEXT, ACTIONS) == ()
    assert validate_reference_slots({"reference_slots": []}, TEXT, ACTIONS) == ()
    assert slot().expression == "budget.txt"
    valid = {"reference_slots": [{
        "span": {"start": 9, "end": 19, "text": "budget.txt"},
        "ref_key": "document",
        "target": {"capability_id": "files", "action_name": "open", "argument_name": "file_id"},
        "relation": "direct", "source_class": "file",
    }]}
    for malformed in (
        {"reference_slots": {}},
        {"reference_slots": ["budget.txt"]},
        {"reference_slots": [{**valid["reference_slots"][0], "extra": True}]},
        {"reference_slots": [{**valid["reference_slots"][0], "span": {"start": True, "end": 19, "text": "budget.txt"}}]},
        {"reference_slots": [{**valid["reference_slots"][0], "span": {"start": 8, "end": 18, "text": "budget.txt"}}]},
        {"reference_slots": [{**valid["reference_slots"][0], "target": {"capability_id": "files", "action_name": "delete", "argument_name": "file_id"}}]},
        {"reference_slots": [{**valid["reference_slots"][0], "target": {"capability_id": "files", "action_name": "open", "argument_name": "unknown"}}]},
    ):
        with pytest.raises(InvalidReferenceProposal):
            validate_reference_slots(malformed, TEXT, ACTIONS)


def test_file_scope_missing_and_deleted_abstain(test_dir):
    files, item = store(test_dir)
    assert produce_evidence(slot(), principal_id="bob", session_id="s1",
                            file_store=files, file_store_user_id="alice", now=NOW).abstain_reason == "CROSS_USER_FILE_STORE"
    assert produce_evidence(slot(), principal_id="alice", session_id="other",
                            file_store=files, file_store_user_id="alice", now=NOW).inventory == ()
    assert not produce(files).abstained
    files.delete(item.file_id)
    assert produce(files, current_attachment_handles=(item.file_id,)).abstained


def test_deleted_bytes_and_changed_size_abstain(test_dir):
    files, item = store(test_dir)
    path = files.path_for(item.file_id)
    assert path
    with open(path, "wb") as out:
        out.write(b"longer")
    assert produce(files).abstain_reason == "FILE_MISSING_OR_STALE"


def test_duplicate_titles_remain_in_full_collision_scope(test_dir):
    files, _ = store(test_dir)
    files.save(filename="budget.txt", content=b"two", session_id="s1")
    result = produce(files)
    assert not result.abstained
    assert len(result.inventory) == 2
    assert len({item.id for item in result.inventory}) == 2
    assert result.query.deterministic_anchor.unique_title_match is None
    assert {item.id for item in result.inventory} == set(result.query.candidate_ids)


def test_current_attachment_must_be_explicit_handle(test_dir):
    files, old = store(test_dir)
    current = files.save(filename="new.txt", content=b"new", session_id="s1")
    ordinary = produce(files)
    assert not any(item.is_current_attachment for item in ordinary.inventory)
    result = produce_evidence(slot("attachment"), principal_id="alice", session_id="s1",
                              file_store=files, file_store_user_id="alice",
                              current_attachment_handles=(current.file_id,), now=NOW)
    assert [item.source_id for item in result.inventory] == [current.file_id]
    assert result.query.deterministic_anchor.current_attachment_id == result.inventory[0].id
    assert old.file_id not in [item.source_id for item in result.inventory]
    denied = produce_evidence(slot("attachment"), principal_id="alice", session_id="s1",
                              file_store=files, file_store_user_id="alice",
                              current_attachment_handles=("invented",), now=NOW)
    assert denied.abstained


def test_authorized_provider_refresh_permission_staleness_and_collision():
    record = {"message_id": "m1", "subject": "budget.txt", "from": "a@example.test", "date": "today"}
    batch = AuthorizedReadBatch("gmail", "alice", NOW.isoformat(),
                                {"status": "success", "messages": [record]},
                                lambda _id: record, lambda _id: True, complete=True)
    result = produce_evidence(slot("gmail"), principal_id="alice", session_id="s1", gmail=batch, now=NOW)
    assert len(result.inventory) == 1
    assert result.inventory[0].source_id == "m1"
    assert produce_evidence(slot("gmail"), principal_id="alice", session_id="s1",
                            gmail=replace(batch, user_id="bob"), now=NOW).abstained
    assert produce_evidence(slot("gmail"), principal_id="alice", session_id="s1",
                            gmail=replace(batch, can_read=lambda _id: False), now=NOW).abstained
    assert produce_evidence(slot("gmail"), principal_id="alice", session_id="s1",
                            gmail=replace(batch, read_current=lambda _id: None), now=NOW).abstained
    assert produce_evidence(slot("gmail"), principal_id="alice", session_id="s1",
                            gmail=replace(batch, observed_at=(NOW-timedelta(hours=1)).isoformat()), now=NOW).abstained
    assert produce_evidence(slot("gmail"), principal_id="alice", session_id="s1",
                            gmail=replace(batch, complete=False), now=NOW).abstain_reason == "COLLISION_SCOPE_INCOMPLETE"
    drive_record = {"id": "d1", "name": "budget.txt", "mimeType": "document"}
    drive = AuthorizedReadBatch("drive", "alice", NOW.isoformat(),
                                {"status": "success", "files": [drive_record]},
                                lambda _id: drive_record, lambda _id: True, complete=True)
    assert produce_evidence(slot("drive"), principal_id="alice", session_id="s1", drive=drive, now=NOW).inventory[0].source_id == "d1"


def test_m36_factual_recency_no_weights_and_no_invention(test_dir):
    files, file = store(test_dir)
    root, relpath = "b" * 32, "budget.txt"
    source_id = hashlib.sha256((root + "\0" + relpath).encode()).hexdigest()[:32]
    source = SourceRef(source_id, root, relpath, "document", "a" * 64, 3, 1, NOW.isoformat())
    query = MemoryQuery("alice", "s1", "budget.txt", now_utc=NOW.isoformat())
    memory = RetrievalResult(query, (RetrievedCandidate(source, "HISTORY", NOW.isoformat(), "file:root/budget.txt@aaaa"),),
                             CollisionReceipt((root,), "snapshot", (source_id,), True))
    result = produce(files, memory_result=memory,
                     conversation_records=({"user_id": "alice", "session_id": "s1", "provenance": "execution_result",
                                            "candidate_id": "invented", "source_id": "invented", "recorded_at": NOW.isoformat()},))
    assert not result.abstained
    assert {item.id for item in result.inventory} == set(result.query.candidate_ids)
    assert len(result.inventory) == 2
    assert all(not hasattr(candidate, "weight") for candidate in result.query.candidates)
    assert produce(files, memory_result=replace(memory, query=replace(query, user_id="bob"))).abstained


def test_conversation_result_requires_underlying_version(test_dir):
    files, _ = store(test_dir)
    older = files.save(filename="older.txt", content=b"older", session_id="previous-session")
    scoped_id = f"file:alice:{older.file_id}"
    record = {"user_id": "alice", "session_id": "s1", "provenance": "execution_result",
              "source_class": "file", "source_id": older.file_id,
              "source_version": "sha256:" + hashlib.sha256(b"older").hexdigest(),
              "candidate_id": scoped_id, "recorded_at": NOW.isoformat()}
    result = produce(files, conversation_records=(record,))
    older_item = next(item for item in result.inventory if item.source_id == older.file_id)
    assert not older_item.is_current_attachment
    assert scoped_id in result.query.candidate_ids
    assert produce(files, conversation_records=(dict(record, source_version="wrong"),)).abstained
    assert len(produce(files, conversation_records=({"text": "older.txt"},)).inventory) == 1


def test_budget_and_frozen_resolver_round_trip(test_dir):
    files, _ = store(test_dir)
    for i in range(2):
        files.save(filename=f"other{i}.txt", content=str(i).encode(), session_id="s1")
    assert produce(files, max_candidates=2).abstain_reason == "BUDGET_EXCEEDED"
    for result in (produce(files), produce_evidence(slot("attachment"), principal_id="alice", session_id="s1",
                                                     file_store=files, file_store_user_id="alice", now=NOW)):
        assert not result.abstained
        trace = resolve_rar_deterministic_extended(result.query)
        assert trace is not None
        assert set(result.query.candidate_ids) == {item.id for item in result.inventory}
