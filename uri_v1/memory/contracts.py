"""Closed M36 v1 contracts; authority is derived, never caller assigned."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from pathlib import PurePosixPath
import re
from types import MappingProxyType
from collections.abc import Mapping
from typing import Any
import unicodedata
import uuid

MEMORY_SCHEMA_VERSION = "m36.memory.v1"
_INTAKE_AUTHORITY = object()
_BINDING_AUTHORITY = object()
_ATTACHMENT_AUTHORITY = object()


@dataclass(frozen=True)
class AttachmentManifest:
    user_id: str
    session_id: str
    turn_id: str
    source_ids: tuple[str,...]
    media_classes: tuple[tuple[str,str],...] = ()
    _authority: Any = field(default=None,repr=False,compare=False)

    def __reduce__(self): raise TypeError("attachment manifests cannot be serialized")


@dataclass(frozen=True)
class TrustedInput:
    """Transient URI-intake snapshot; model dictionaries cannot issue one."""
    user_id: str
    session_id: str
    turn_id: str
    trace_id: str
    raw_text: str
    spans: tuple[tuple[str, int, int], ...]
    round_id: str | None = None
    _authority: Any = field(default=None, repr=False, compare=False)

    @property
    def trusted(self):
        return self._authority is _INTAKE_AUTHORITY

    def __reduce__(self):
        raise TypeError("intake capabilities cannot be serialized")


@dataclass(frozen=True)
class BoundReference:
    ref_key: str
    source: Any
    binding_tier: str
    binding_id: str
    user_id: str
    session_id: str
    _authority: Any = field(default=None, repr=False, compare=False)

    @property
    def trusted(self):
        return self._authority is _BINDING_AUTHORITY

    def __reduce__(self):
        raise TypeError("binding capabilities cannot be serialized")


class RecordKind(StrEnum):
    SOURCE_OBSERVED = "SOURCE_OBSERVED"
    TASK_OPENED = "TASK_OPENED"
    TASK_STATE = "TASK_STATE"
    OUTCOME = "OUTCOME"
    DERIVATIVE = "DERIVATIVE"
    CORRECTION = "CORRECTION"
    TOMBSTONE = "TOMBSTONE"


class Provenance(StrEnum):
    USER_PROVIDED = "USER_PROVIDED"
    SOURCE_OBSERVED = "SOURCE_OBSERVED"
    URI_RECORDED = "URI_RECORDED"
    EXECUTION_OUTCOME = "EXECUTION_OUTCOME"
    VERIFIER_RESULT = "VERIFIER_RESULT"
    MODEL_DERIVED = "MODEL_DERIVED"
    USER_CORRECTION = "USER_CORRECTION"


class Authority(StrEnum):
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"
    USER_ASSERTED = "USER_ASSERTED"
    RUNTIME_RECORDED = "RUNTIME_RECORDED"
    VERIFIED_OUTCOME = "VERIFIED_OUTCOME"
    VERIFIER_ATTESTED = "VERIFIER_ATTESTED"
    CLAIMED_OUTCOME = "CLAIMED_OUTCOME"
    DERIVED_NON_AUTHORITATIVE = "DERIVED_NON_AUTHORITATIVE"


class Scope(StrEnum):
    PRIVATE = "PRIVATE"
    SHAREABLE = "SHAREABLE"


class TaskStatus(StrEnum):
    OPEN = "OPEN"
    WAITING_USER = "WAITING_USER"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIABLE = "UNVERIFIABLE"
    FAILED = "FAILED"
    CLAIMED_ONLY = "CLAIMED_ONLY"


class BindingTier(StrEnum):
    CONFIRMED = "CONFIRMED"
    TENTATIVE = "TENTATIVE"


class Freshness(StrEnum):
    CURRENT = "CURRENT"
    STALE_SOURCE = "STALE_SOURCE"
    SOURCE_MISSING = "SOURCE_MISSING"
    DERIVATIVE_STALE = "DERIVATIVE_STALE"
    SUPERSEDED_REFERENCE = "SUPERSEDED_REFERENCE"
    UNKNOWN = "UNKNOWN"


class IdentityStatus(StrEnum):
    HASH_VERIFIED = "HASH_VERIFIED"
    HASH_UNAVAILABLE_SIZE_CAP = "HASH_UNAVAILABLE_SIZE_CAP"
    HASH_UNAVAILABLE_POLICY = "HASH_UNAVAILABLE_POLICY"
    SOURCE_MISSING = "SOURCE_MISSING"
    UNSAFE_IDENTITY = "UNSAFE_IDENTITY"


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(v) for v in value)
    return value


def plain(value):
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    return value


def canonical(value) -> bytes:
    return json.dumps(plain(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp(value: str) -> datetime:
    d = datetime.fromisoformat(value)
    if d.tzinfo is None or d.utcoffset().total_seconds() != 0:
        raise ValueError("UTC timestamp required")
    return d


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value) or value == "0" * 32:
        raise ValueError("invalid opaque identifier")
    return value


def require_trace_id(value):
    # Lineage: uri_v1/evaluation/trace_context.py (core cannot import S7).
    return identifier(value)


def relpath(value: str) -> str:
    parts = value.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{s}{n}" for s in ("COM", "LPT") for n in range(1, 10)}
    if (not isinstance(value, str) or not value or PurePosixPath(value).is_absolute()
            or "\\" in value or ":" in value or any(
                p in ("", ".", "..") or p.endswith((".", " ")) or
                p.split(".")[0].upper() in reserved for p in parts)):
        raise ValueError("unsafe relative path")
    return value


def bounded(value, limit=512):
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValueError("invalid bounded text")
    # Lineage: uri_core/core/security_guards.py, reimplemented without import.
    if re.search(r"(?i)(?:\b(?:password|api[_ -]?key|secret|token)\s*[:=]|\bsk-[\w-]{16,}|-----BEGIN .*PRIVATE KEY)", value):
        raise ValueError("credential-looking text")
    return value


# Closed deterministic negation cues (audit F-1/F-2; re-audit R-1/R-2/R-3).
# The text is NFKC-normalized (so fullwidth "ｄｏｎ＇ｔ" reads as "don't"), then every
# apostrophe-like code point (straight, curly, modifier-letter, backtick, acute accent,
# fullwidth) is removed before tokenizing, and a split "do n't" form is rejoined, so
# "don't" matches regardless of quote glyph, width or whitespace. Vocabulary expansion needs later qualification; any hit fails
# closed to clarification.
NEGATION_WORDS = frozenset((
    "not", "no", "never", "skip", "except", "excluding", "exclude", "without", "avoid",
    "dont", "doesnt", "didnt", "isnt", "arent", "wasnt", "werent", "wont", "cant", "cannot",
    "shouldnt", "wouldnt", "couldnt", "mustnt", "neednt", "aint", "hasnt", "hadnt", "havent",
    "mightnt", "shant", "darent",
    "but", "ignore", "neither", "nor", "none", "nothing", "stop", "drop", "omit", "minus",
    "unless", "besides", "nope", "nah", "hardly",
))
NEGATION_PHRASES = (
    "other than", "instead of", "rather than", "apart from", "aside from",
    "leave out", "anything besides", "except for", "far from",
)

_APOSTROPHE_RE = re.compile("['‘’‛ʻʼ′‵❛❜`´＇]")


def negated(text: str) -> bool:
    normalized = _APOSTROPHE_RE.sub("", unicodedata.normalize("NFKC", text).casefold())
    # Rejoin a split "do n't" -> "dont" before tokenizing.
    normalized = re.sub(r"(\w+)\s+nt\b", r"\1nt", normalized)
    tokens = re.findall(r"\w+", normalized)
    joined = " " + " ".join(tokens) + " "
    return bool(NEGATION_WORDS.intersection(tokens)) or any(" " + p + " " in joined for p in NEGATION_PHRASES)


# Positive allowlist gate (User decision 2026-09-28, replacing blocklist growth).
# A turn may carry certainty (an exact-title/ID binding or an explicit user status
# transition) only when every word around the reference is plainly affirmative.
# Anything else, including every negation or exclusion form, whatever its glyphs,
# spelling or idiom, falls outside the closed vocabulary and asks for clarification.
# Contractions split at the apostrophe, so "it's" -> "it" "s" is admitted but
# "don't" -> "don" "t" is not: "t" is never affirmative.
#
# Repair round 4 (re-audit c179e42, findings P-1): "up", "over", "through" and
# "give" are dropped -- each combines with otherwise-allowed words into a
# phrasal exclusion ("give up on X", "we're over X", "I'm through with X").
# And a non-trivial context (anything beyond a bare filename plus filler such
# as please/ok/yes/the/file) must contain an explicit action verb, closing
# "let go of X" / "let X go" / "that's it for X", which use only allowed words
# but name no action.
_AFFIRMATIVE_PUNCTUATION = set(".,!?:;\"'()“”‘’")
AFFIRMATIVE_FILLERS = frozenset(
    "a an the my our your this that it its one same file document doc spreadsheet workbook sheet script pdf "
    "please pls kindly now today again also just quickly here ok okay yes yeah sure thanks thank you "
    "i we me us let lets s d ll m re ve can could would will want need like go ahead and to with on in at "
    "for of into".split())
AFFIRMATIVE_ACTIONS = frozenset(
    "open update edit use read check review summarize summarise analyze analyse fix format print show load "
    "look see process convert run attach clean correct change modify finish continue resume work start "
    "prepare draft write fill add save export find get make take send share proofread translate tidy "
    "improve rewrite refresh recalculate calculate validate verify".split())
# Trivial fillers: a context made only of these (or empty) needs no action verb --
# a bare filename plus politeness/pointer words is still plainly affirmative.
TRIVIAL_FILLERS = frozenset(
    "please pls kindly ok okay yes yeah sure thanks thank you "
    "a an the this that it its one same file document doc spreadsheet workbook sheet script pdf".split())
# Duration fillers only make a declaration affirmative for PAUSED ("pause for a
# moment"); elsewhere they let through non-declarations like "done for now".
DURATION_FILLERS = frozenset("for a moment while bit time then back on again".split())
STATUS_FILLERS = frozenset(
    "i im m we re it its s this that the task job work is are am all now please pls mark as set to "
    "thanks thank you ok okay yes yeah go ahead and just let lets us here fully completely finally can".split())
# Leading words that turn a status keyword into a request rather than a
# declaration (audit P-2): "please/can you complete this task" asks for work.
REQUEST_LEAD_WORDS = frozenset("please pls can could would you".split())


def affirmative_words(text: str, allowed) -> tuple[str, ...] | None:
    """Tokens of ``text`` if every character and word is inside the closed
    affirmative vocabulary; ``None`` (not affirmative) otherwise."""
    if any(not (c.isascii() and (c.isalnum() or c.isspace())) and c not in _AFFIRMATIVE_PUNCTUATION for c in text):
        return None
    tokens = tuple(re.findall(r"[a-z0-9]+", text.casefold()))
    return tokens if all(t in allowed for t in tokens) else None


def affirmative_context(text: str) -> bool:
    tokens = affirmative_words(text, AFFIRMATIVE_FILLERS | AFFIRMATIVE_ACTIONS)
    if tokens is None:
        return False
    if any(t not in TRIVIAL_FILLERS for t in tokens) and not any(t in AFFIRMATIVE_ACTIONS for t in tokens):
        return False
    return True


def opaque_link(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}",value):
        raise ValueError("identifier-only link required")
    return value


def closed(value, required, optional=()):
    if not isinstance(value, Mapping) or set(value) - set(required) - set(optional) or not set(required) <= set(value):
        raise ValueError("closed schema violation")


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    root_id: str
    relpath: str
    media_type: str
    content_sha256: str | None
    size_bytes: int
    mtime_ns: int
    observed_at: str
    identity_status: IdentityStatus = IdentityStatus.HASH_VERIFIED

    def __post_init__(self):
        identifier(self.source_id); identifier(self.root_id); relpath(self.relpath)
        timestamp(self.observed_at)
        object.__setattr__(self, "identity_status", IdentityStatus(self.identity_status))
        if self.media_type not in ("spreadsheet", "script", "document", "unknown"):
            raise ValueError("invalid source class")
        if type(self.size_bytes) is not int or type(self.mtime_ns) is not int or min(self.size_bytes, self.mtime_ns) < 0:
            raise ValueError("invalid source metadata")
        expected = hashlib.sha256((self.root_id + "\0" + self.relpath).encode()).hexdigest()[:32]
        if expected != self.source_id:
            raise ValueError("source identity mismatch")
        if self.identity_status == IdentityStatus.HASH_VERIFIED:
            if not isinstance(self.content_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.content_sha256):
                raise ValueError("verified source requires SHA-256")
        elif self.content_sha256 is not None:
            raise ValueError("degraded source cannot claim verified hash")


_ADMITTED = {
    RecordKind.SOURCE_OBSERVED: {Provenance.SOURCE_OBSERVED},
    RecordKind.TASK_OPENED: {Provenance.USER_PROVIDED},
    RecordKind.TASK_STATE: {Provenance.URI_RECORDED, Provenance.USER_PROVIDED, Provenance.USER_CORRECTION},
    RecordKind.OUTCOME: {Provenance.EXECUTION_OUTCOME, Provenance.VERIFIER_RESULT},
    RecordKind.DERIVATIVE: {Provenance.MODEL_DERIVED},
    RecordKind.CORRECTION: {Provenance.USER_CORRECTION},
    RecordKind.TOMBSTONE: {Provenance.USER_PROVIDED},
}


def derive_authority(kind, provenance, status=None) -> Authority:
    kind, provenance = RecordKind(kind), Provenance(provenance)
    if provenance not in _ADMITTED[kind]:
        raise ValueError("kind/provenance not admitted")
    if kind == RecordKind.OUTCOME:
        status = VerificationStatus(status)
        if provenance == Provenance.EXECUTION_OUTCOME:
            if status not in (VerificationStatus.CLAIMED_ONLY, VerificationStatus.FAILED):
                raise ValueError("claim cannot verify")
            return Authority.CLAIMED_OUTCOME
        if status == VerificationStatus.CLAIMED_ONLY:
            raise ValueError("verifier must issue a verdict")
        return Authority.VERIFIED_OUTCOME if status == VerificationStatus.VERIFIED else Authority.VERIFIER_ATTESTED
    return {
        Provenance.SOURCE_OBSERVED: Authority.AUTHORITATIVE_SOURCE,
        Provenance.USER_PROVIDED: Authority.USER_ASSERTED,
        Provenance.USER_CORRECTION: Authority.USER_ASSERTED,
        Provenance.URI_RECORDED: Authority.RUNTIME_RECORDED,
        Provenance.MODEL_DERIVED: Authority.DERIVED_NON_AUTHORITATIVE,
    }[provenance]


def hash_link(value):
    closed(value, ("source_id", "content_sha256"))
    identifier(value["source_id"])
    if value["content_sha256"] is not None and not re.fullmatch(r"[0-9a-f]{64}", value["content_sha256"]):
        raise ValueError("invalid link hash")


def validate_payload(kind, p):
    schemas = {
        RecordKind.SOURCE_OBSERVED: ((), ()),
        RecordKind.TASK_OPENED: (("objective_label", "origin_turn_trace_id", "transition_evidence_ids"), ("explicit_user_labels",)),
        RecordKind.TASK_STATE: (("status", "references", "opening_record_id", "transition_evidence_ids"), ("next_step", "last_outcome_record_id", "correction_record_id", "correction_operation_id")),
        RecordKind.OUTCOME: (("action_label", "verification_status", "inputs", "outputs", "evidence_ids", "attempt_id"), ("exit_code", "verifier_id", "verifier_type", "verifier_version", "invocation_id", "assessed_outcome_record_id", "acceptance_evidence_ref", "acceptance_evidence_digest", "attestation_ref")),
        RecordKind.DERIVATIVE: (("result_id", "result_version", "content_sha256", "derived_from", "derivative_kind"), ()),
        RecordKind.CORRECTION: (("target", "prior_task_state_record_id", "correction_operation_id", "transition_evidence_ids"), ("wrong_source_id", "right_source_id", "old_source_ref", "new_source_ref", "new_binding_id", "new_binding_tier", "s7_event_id", "note")),
        RecordKind.TOMBSTONE: (("target_record_ids", "reason", "transition_evidence_ids"), ()),
    }
    closed(p, *schemas[kind])
    def text_walk(v, key=""):
        if isinstance(v, str):
            bounded(v, 2000 if key in ("text", "note", "next_step") else 512)
        elif isinstance(v, Mapping):
            for k, x in v.items(): text_walk(x, k)
        elif isinstance(v, (list, tuple)):
            if len(v) > 128: raise ValueError("payload collection exceeded")
            for x in v: text_walk(x, key)
        elif v is not None and type(v) not in (bool, int):
            raise ValueError("unsupported payload type")
    text_walk(p)
    for key in ("transition_evidence_ids","evidence_ids","target_record_ids"):
        if key in p:
            if not isinstance(p[key],(tuple,list)): raise ValueError("identifier collection required")
            for value in p[key]: opaque_link(value)
    if kind == RecordKind.TASK_OPENED:
        require_trace_id(p["origin_turn_trace_id"])
    if kind == RecordKind.TASK_STATE:
        TaskStatus(p["status"]); identifier(p["opening_record_id"])
        keys = []
        for ref in p["references"]:
            closed(ref, ("ref_key", "source_id", "content_sha256", "binding_tier", "binding_id"))
            hash_link({k: ref[k] for k in ("source_id", "content_sha256")})
            BindingTier(ref["binding_tier"]); bounded(ref["binding_id"]); keys.append(ref["ref_key"])
            opaque_link(ref["binding_id"])
            if ref["content_sha256"] is None and ref["binding_tier"]==BindingTier.CONFIRMED: raise ValueError("unhashed reference cannot be confirmed")
        if len(keys) != len(set(keys)): raise ValueError("duplicate reference slot")
        if "next_step" in p:
            closed(p["next_step"], ("text", "provenance"))
            if p["next_step"]["provenance"] != Provenance.MODEL_DERIVED: raise ValueError("next-step is a proposal")
    if kind in (RecordKind.OUTCOME, RecordKind.DERIVATIVE):
        for link in p.get("inputs", p.get("derived_from", ())): hash_link(link)
        for link in p.get("outputs", ()):
            if "source_id" in link: hash_link(link)
            else:
                closed(link, ("result_id", "result_version", "content_sha256"))
                if type(link["result_version"]) is not int or link["result_version"] < 1: raise ValueError("invalid version")
                if not re.fullmatch(r"[0-9a-f]{64}", link["content_sha256"]): raise ValueError("invalid derivative hash")
    if kind == RecordKind.DERIVATIVE:
        if p["derivative_kind"] not in ("summary", "modified_script", "output_file", "other"): raise ValueError("invalid derivative kind")
        if type(p["result_version"]) is not int or p["result_version"] < 1 or not re.fullmatch(r"[0-9a-f]{64}", p["content_sha256"]): raise ValueError("invalid derivative version/hash")
    if kind == RecordKind.TOMBSTONE and p["reason"] != "USER_FORGET": raise ValueError("invalid hide instruction")
    if kind == RecordKind.CORRECTION:
        identifier(p["prior_task_state_record_id"]); identifier(p["correction_operation_id"])
        if isinstance(p["target"],str): identifier(p["target"])
        else:
            closed(p["target"],("task_id","ref_key")); identifier(p["target"]["task_id"])
            for key in ("wrong_source_id","right_source_id","old_source_ref","new_source_ref","new_binding_id","new_binding_tier"):
                if key not in p: raise ValueError("reference correction evidence required")
            SourceRef(**p["old_source_ref"]); SourceRef(**p["new_source_ref"])
            BindingTier(p["new_binding_tier"]); opaque_link(p["new_binding_id"])


@dataclass(frozen=True)
class MemoryRecord:
    user_id: str
    kind: RecordKind
    provenance: Provenance
    payload: Mapping
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    schema_version: str = MEMORY_SCHEMA_VERSION
    scope: Scope = Scope.PRIVATE
    recorded_at: str = field(default_factory=utc_now)
    session_id: str | None = None
    trace_id: str | None = None
    task_id: str | None = None
    subject_ids: tuple[str, ...] = ()
    source_refs: tuple[SourceRef, ...] = ()
    supersedes: tuple[str, ...] = ()

    def __post_init__(self):
        if str(uuid.UUID(self.user_id)) != self.user_id: raise ValueError("canonical user UUID required")
        identifier(self.record_id); timestamp(self.recorded_at)
        if self.schema_version != MEMORY_SCHEMA_VERSION: raise ValueError("unsupported schema")
        object.__setattr__(self, "kind", RecordKind(self.kind))
        object.__setattr__(self, "provenance", Provenance(self.provenance))
        object.__setattr__(self, "scope", Scope(self.scope))
        if self.scope != Scope.PRIVATE: raise ValueError("sharing deferred")
        if self.trace_id is not None: require_trace_id(self.trace_id)
        if self.session_id is not None: bounded(self.session_id)
        if self.task_id is not None: identifier(self.task_id)
        object.__setattr__(self, "payload", freeze(self.payload))
        for name in ("subject_ids", "source_refs", "supersedes"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not all(isinstance(s,SourceRef) for s in self.source_refs): raise ValueError("typed SourceRefs required")
        if max(len(self.subject_ids),len(self.source_refs),len(self.supersedes))>128: raise ValueError("record collection exceeded")
        for sid in self.subject_ids: opaque_link(sid)
        for x in self.supersedes: identifier(x)
        if len(set(self.supersedes)) != len(self.supersedes): raise ValueError("duplicate supersession")
        validate_payload(self.kind, self.payload)
        derive_authority(self.kind, self.provenance, self.payload.get("verification_status"))
        if self.kind == RecordKind.SOURCE_OBSERVED and len(self.source_refs) != 1: raise ValueError("observation needs one source")
        if self.kind not in (RecordKind.SOURCE_OBSERVED, RecordKind.TOMBSTONE) and self.task_id is None: raise ValueError("task linkage required")

    @property
    def authority(self):
        return derive_authority(self.kind, self.provenance, self.payload.get("verification_status"))

    def to_dict(self):
        return {**plain(self), "authority": self.authority.value}

    @classmethod
    def from_dict(cls, raw):
        closed(raw, tuple(f.name for f in fields(cls)) + ("authority",))
        d = dict(raw); a = d.pop("authority")
        d["source_refs"] = tuple(SourceRef(**v) for v in d["source_refs"])
        obj = cls(**d)
        if a != obj.authority: raise ValueError("forged authority")
        return obj


@dataclass(frozen=True)
class WriteResult:
    persisted: bool
    reason: str
    record_ids: tuple[str, ...] = ()
    per_record: tuple[bool, ...] = ()
    recovery_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryQuery:
    user_id: str
    session_id: str
    reference_expression: str
    task_id: str | None = None
    type_hint: str | None = None  # proposal only
    session_source_ids: tuple[str, ...] = ()
    attachment_source_ids: tuple[str, ...] = ()  # URI ingestion only
    attachment_manifest: Any = None
    session_confirmed: bool = False
    now_utc: str = field(default_factory=utc_now)
    user_timezone: str = "UTC"
    max_candidates: int = 16
    max_bytes: int = 16384
    max_tasks: int = 10000
    intake: Any = None  # transient opaque adapter intake, never serialized
    ref_key: str = "file"

    def __post_init__(self):
        timestamp(self.now_utc); bounded(self.reference_expression, 2000)
        if not 1 <= self.max_candidates <= 16 or not 1 <= self.max_bytes <= 16384: raise ValueError("invalid budget")
        for name in ("session_source_ids","attachment_source_ids"):
            object.__setattr__(self,name,tuple(getattr(self,name)))


def authorized_attachments(query):
    m=query.attachment_manifest; i=query.intake
    if (not isinstance(m,AttachmentManifest) or m._authority is not _ATTACHMENT_AUTHORITY
            or not isinstance(i,TrustedInput) or not i.trusted
            or (m.user_id,m.session_id,m.turn_id)!=(query.user_id,query.session_id,i.turn_id)
            or m.source_ids!=query.attachment_source_ids): return ()
    return m.source_ids


@dataclass(frozen=True)
class RetrievedCandidate:
    source: SourceRef
    tier: str
    last_used_at: str
    locator: str
    task_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CollisionReceipt:
    root_ids: tuple[str, ...]
    snapshot_digest: str
    matching_ids: tuple[str, ...]
    complete: bool
    reason: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    query: MemoryQuery
    candidates: tuple[RetrievedCandidate, ...]
    collision: CollisionReceipt | None = None
    stale: tuple[Mapping, ...] = ()
    degraded: str | None = None
    telemetry: Mapping = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "stale", tuple(freeze(s) for s in self.stale))
        object.__setattr__(self, "telemetry", freeze(self.telemetry))
