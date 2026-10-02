"""Verified source inventory and deliberately lossy frozen-RAR projection.

This module is inert until a later slice supplies authenticated, user-bound
inputs. Transcript prose and model-proposed IDs are never source records.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Callable, Mapping

from uri_v1.turn.rar_contracts import (
    RARCandidate, RARDeterministicAnchor, RAREvidence, RARQuery,
)

from .proposal import ReferenceSlot


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return result.astimezone(timezone.utc)


def _version(value: Mapping) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class EvidenceCandidate:
    id: str
    source_id: str
    source_class: str
    title: str
    candidate_type: str
    locator: str
    version: str
    observed_at: str
    user_id: str
    session_id: str | None
    owner: str | None = None
    is_current_attachment: bool = False
    last_used_at: str | None = None


@dataclass(frozen=True)
class AuthorizedReadBatch:
    """A trusted caller's user-bound search result with live access hooks.

    ``read_current`` must re-read metadata by ID under the same principal.
    ``can_read`` checks the current grant. No network call is made by this
    package itself; the real Gmail/Drive services are supplied by Slice C.
    """

    source_class: str
    user_id: str
    observed_at: str
    result: Mapping
    read_current: Callable[[str], Mapping | None]
    can_read: Callable[[str], bool]
    complete: bool = False


@dataclass(frozen=True)
class EvidenceEnvelope:
    slot: ReferenceSlot
    inventory: tuple[EvidenceCandidate, ...]
    query: RARQuery
    abstain_reason: str | None = None

    @property
    def abstained(self) -> bool:
        return self.abstain_reason is not None


def _provider_fields(source_class: str, record: Mapping) -> tuple[str, str, str, str]:
    if source_class == "gmail":
        return (record.get("message_id"), record.get("subject"), "email", record.get("from"))
    return (record.get("id"), record.get("name"), record.get("mimeType") or "document", record.get("owner"))


def _provider_version(source_class: str, record: Mapping) -> str:
    if isinstance(record.get("version"), str) and record["version"]:
        return record["version"]
    if source_class == "gmail":
        keys = ("message_id", "thread_id", "subject", "from", "date")
    else:
        keys = ("id", "name", "mimeType", "modifiedTime", "etag")
    return _version({key: record.get(key) for key in keys})


def _empty(slot: ReferenceSlot, reason: str) -> EvidenceEnvelope:
    return EvidenceEnvelope(slot, (), RARQuery(slot.expression), reason)


def _file_item(file_store, record, principal_id: str, session_id: str,
               now: datetime, current_handles: set[str]) -> EvidenceCandidate | None:
    path = file_store.path_for(record.file_id)
    if path is None:
        return None
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        stat = os.stat(path)
    except OSError:
        return None
    if stat.st_size != record.size_bytes:
        return None
    candidate_id = f"file:{principal_id}:{record.file_id}"
    return EvidenceCandidate(
        candidate_id, record.file_id, "file", record.filename,
        record.media_type or "file", record.file_id,
        f"sha256:{digest.hexdigest()}", now.isoformat(), principal_id,
        session_id, is_current_attachment=record.file_id in current_handles,
    )


def produce_evidence(
    slot: ReferenceSlot,
    *,
    principal_id: str,
    session_id: str,
    file_store=None,
    file_store_user_id: str | None = None,
    current_attachment_handles: tuple[str, ...] = (),
    conversation_records: tuple[Mapping, ...] = (),
    gmail: AuthorizedReadBatch | None = None,
    drive: AuthorizedReadBatch | None = None,
    memory_result=None,
    now: datetime | None = None,
    max_candidates: int = 16,
    freshness_seconds: int = 300,
) -> EvidenceEnvelope:
    """Build one bounded inventory; any uncheckable relevant source abstains.

    ``file_store`` must be the principal's scoped FileStore and its owner must
    be passed separately. A later binding must re-check locator/version again.
    """
    if not isinstance(slot, ReferenceSlot) or not principal_id or not session_id:
        raise ValueError("validated slot and authenticated scope required")
    if not 1 <= max_candidates <= 16 or freshness_seconds <= 0:
        raise ValueError("invalid evidence budget")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    items: dict[str, EvidenceCandidate] = {}
    attachment_ids = set(current_attachment_handles)
    if len(attachment_ids) != len(current_attachment_handles) or any(not isinstance(x, str) or not x for x in attachment_ids):
        return _empty(slot, "INVALID_ATTACHMENT_HANDLES")

    if slot.source_class in {"any", "file", "attachment", "conversation"}:
        if file_store is not None:
            if file_store_user_id != principal_id:
                return _empty(slot, "CROSS_USER_FILE_STORE")
            try:
                records = file_store.list_for_session(session_id)
            except (OSError, ValueError):
                return _empty(slot, "FILE_STORE_UNAVAILABLE")
            known_handles = set()
            for record in records:
                if record.session_id != session_id or not record.file_id or not record.filename:
                    return _empty(slot, "INVALID_FILE_PROVENANCE")
                if slot.source_class == "attachment" and record.file_id not in attachment_ids:
                    continue
                if len(items) >= max_candidates:
                    return _empty(slot, "BUDGET_EXCEEDED")
                item = _file_item(file_store, record, principal_id, session_id, now, attachment_ids)
                if item is None:
                    return _empty(slot, "FILE_MISSING_OR_STALE")
                items[item.id] = item
                known_handles.add(record.file_id)
            if not attachment_ids <= known_handles:
                return _empty(slot, "ATTACHMENT_MISSING_OR_OUT_OF_SCOPE")
        elif attachment_ids:
            return _empty(slot, "ATTACHMENT_STORE_MISSING")

    for batch in (gmail, drive):
        if batch is None or slot.source_class not in {"any", batch.source_class}:
            continue
        if batch.source_class not in {"gmail", "drive"} or batch.user_id != principal_id:
            return _empty(slot, "CROSS_USER_PROVIDER")
        try:
            age = (now - _time(batch.observed_at)).total_seconds()
        except (ValueError, TypeError):
            return _empty(slot, "PROVIDER_TIMESTAMP_INVALID")
        if age < 0 or age > freshness_seconds:
            return _empty(slot, "PROVIDER_STALE")
        result = batch.result
        key = "messages" if batch.source_class == "gmail" else "files"
        if not isinstance(result, Mapping) or result.get("status") != "success" or not isinstance(result.get(key), list):
            return _empty(slot, "PROVIDER_RESULT_UNAVAILABLE")
        records = result[key]
        if len(records) + len(items) > max_candidates:
            return _empty(slot, "BUDGET_EXCEEDED")
        for record in records:
            if not isinstance(record, Mapping):
                return _empty(slot, "INVALID_PROVIDER_RECORD")
            source_id, title, candidate_type, owner = _provider_fields(batch.source_class, record)
            if not isinstance(source_id, str) or not source_id or not isinstance(title, str) or not title:
                return _empty(slot, "INVALID_PROVIDER_PROVENANCE")
            try:
                if not batch.can_read(source_id):
                    return _empty(slot, "PROVIDER_PERMISSION_DENIED")
                fresh = batch.read_current(source_id)
            except Exception:
                return _empty(slot, "PROVIDER_REFRESH_FAILED")
            if not isinstance(fresh, Mapping) or _provider_fields(batch.source_class, fresh)[0] != source_id:
                return _empty(slot, "PROVIDER_MISSING")
            if _provider_version(batch.source_class, fresh) != _provider_version(batch.source_class, record):
                return _empty(slot, "PROVIDER_STALE")
            candidate_id = f"{batch.source_class}:{principal_id}:{source_id}"
            if candidate_id in items:
                return _empty(slot, "DUPLICATE_SOURCE_ID")
            items[candidate_id] = EvidenceCandidate(
                candidate_id, source_id, batch.source_class, title, candidate_type,
                source_id, _provider_version(batch.source_class, fresh),
                batch.observed_at, principal_id, None, owner=owner,
            )
        if not batch.complete and any(
            item.source_class == batch.source_class and item.title.casefold() == slot.expression.casefold()
            for item in items.values()
        ):
            return _empty(slot, "COLLISION_SCOPE_INCOMPLETE")

    if memory_result is not None and slot.source_class in {"any", "file", "memory"}:
        query = getattr(memory_result, "query", None)
        if (getattr(query, "user_id", None) != principal_id or getattr(query, "session_id", None) != session_id):
            return _empty(slot, "CROSS_USER_MEMORY")
        collision = getattr(memory_result, "collision", None)
        if (memory_result.degraded or memory_result.stale or collision is None or not collision.complete):
            return _empty(slot, "MEMORY_UNVERIFIED")
        for retrieved in memory_result.candidates:
            source = retrieved.source
            if str(source.identity_status) not in {"HASH_VERIFIED", "IdentityStatus.HASH_VERIFIED"} or not source.content_sha256:
                return _empty(slot, "MEMORY_IDENTITY_UNVERIFIED")
            age = (now - _time(source.observed_at)).total_seconds()
            if age < 0 or age > freshness_seconds:
                return _empty(slot, "MEMORY_STALE")
            candidate_id = f"memory:{principal_id}:{source.source_id}"
            if candidate_id not in items and len(items) >= max_candidates:
                return _empty(slot, "BUDGET_EXCEEDED")
            items[candidate_id] = EvidenceCandidate(
                candidate_id, source.source_id, "memory", PurePosixPath(source.relpath).name,
                source.media_type, retrieved.locator, f"sha256:{source.content_sha256}",
                source.observed_at, principal_id, None, last_used_at=retrieved.last_used_at,
            )

    # A result record may identify an older user file, but only its ID and
    # observed version can admit it. Its prose alone cannot create an object.
    if slot.source_class in {"any", "file", "conversation"} and file_store is not None:
        for record in conversation_records:
            if (not isinstance(record, Mapping) or record.get("user_id") != principal_id
                    or record.get("session_id") != session_id
                    or record.get("provenance") not in {"execution_result", "source_observed"}
                    or record.get("source_class") != "file"):
                continue
            source_id = record.get("source_id")
            if not isinstance(source_id, str) or not source_id or not isinstance(record.get("source_version"), str):
                continue
            candidate_id = f"file:{principal_id}:{source_id}"
            if candidate_id in items:
                continue
            if len(items) >= max_candidates:
                return _empty(slot, "BUDGET_EXCEEDED")
            source_record = file_store.get(source_id)
            if source_record is None:
                return _empty(slot, "CONVERSATION_SOURCE_MISSING")
            item = _file_item(file_store, source_record, principal_id, session_id, now, attachment_ids)
            if item is None or item.version != record["source_version"]:
                return _empty(slot, "CONVERSATION_SOURCE_STALE")
            items[item.id] = item

    # Conversation/result records can also supply factual recency for IDs
    # already verified above. A text-only mention has no effect.
    recency: dict[str, str] = {}
    for record in conversation_records:
        if (not isinstance(record, Mapping) or record.get("user_id") != principal_id
                or record.get("session_id") != session_id
                or record.get("provenance") not in {"execution_result", "source_observed"}):
            continue
        candidate_id = record.get("candidate_id")
        if candidate_id not in items or record.get("source_id") != items[candidate_id].source_id:
            continue
        try:
            used_at = _time(record["recorded_at"])
            if used_at > now:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        stamp = used_at.isoformat()
        recency[candidate_id] = max(recency.get(candidate_id, stamp), stamp)
    ordered = sorted(items.values(), key=lambda item: (
        -( _time(recency.get(item.id, item.last_used_at or item.observed_at)).timestamp()), item.id,
    ))
    ids = {item.id for item in ordered}
    exact_id = next((item.id for item in ordered if slot.expression in {item.id, item.source_id}), None)
    exact_titles = [item.id for item in ordered if item.title.casefold() == slot.expression.casefold()]
    current = [item.id for item in ordered if item.is_current_attachment]
    anchor = RARDeterministicAnchor(
        exact_id=exact_id,
        unique_title_match=exact_titles[0] if len(exact_titles) == 1 else None,
        current_attachment_id=current[0] if slot.source_class == "attachment" and len(current) == 1 else None,
    )
    rar = RARQuery(
        slot.expression,
        tuple(RARCandidate(item.id, item.title, item.candidate_type, rank,
                           owner=item.owner, is_attachment=item.is_current_attachment)
              for rank, item in enumerate(ordered)),
        RAREvidence(clause_text=slot.expression), anchor,
    )
    assert set(rar.candidate_ids) == ids
    return EvidenceEnvelope(slot, tuple(ordered), rar)
