"""Draft state for text intelligence: blocks, immutable versions, undo/redo, deterministic edit application.

A draft is an ordered list of blocks. Each block has a stable id ("b1", "b2", ...), a role and its text. Roles:
recipient, subject, salutation, body, closing, signature, line. "Paragraph N" in a user's instruction means the N-th
body block. Versions are immutable snapshots; `cursor` points at the version shown. Undo/redo move the cursor; a new
version created after an undo drops the versions after the cursor (the usual editor rule), and the original input is
kept on the draft itself, so it is never lost.

Nothing in this module calls a model or touches the file system.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field

ROLES = ("recipient", "subject", "salutation", "body", "closing", "signature", "line")
MAX_VERSIONS = 50
MAX_BLOCKS = 80
MAX_BLOCK_CHARS = 6000


class DraftError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Block:
    id: str
    role: str
    text: str

    def to_dict(self):
        return {"id": self.id, "role": self.role, "text": self.text}


@dataclass(frozen=True)
class Version:
    n: int
    blocks: tuple
    facts: tuple           # ({"key", "value", "superseded": [...]}, ...)
    exclusions: tuple      # phrases the user asked not to include
    missing: tuple         # material information the user has not given
    op: str                # created | revised | corrected | rewritten | restored
    instruction: str       # the user's words that produced this version (as received)
    summary: str
    changed: tuple         # block ids whose text changed or that were added
    removed: tuple         # block ids removed
    flags: tuple           # verification flags for this version
    t: float = field(default_factory=time.time)

    def body_ids(self):
        return [b.id for b in self.blocks if b.role == "body"]

    def text(self):
        return render(self.blocks)

    def to_dict(self):
        return {"n": self.n, "blocks": [b.to_dict() for b in self.blocks], "facts": [dict(f) for f in self.facts],
                "exclusions": list(self.exclusions), "missing": list(self.missing), "op": self.op,
                "instruction": self.instruction, "summary": self.summary, "changed": list(self.changed),
                "removed": list(self.removed), "flags": list(self.flags), "text": self.text()}


def render(blocks) -> str:
    return "\n\n".join(b.text for b in blocks if b.text.strip())


def _check_block(role, text):
    if role not in ROLES:
        raise DraftError("BLOCK_ROLE")
    if not isinstance(text, str) or len(text) > MAX_BLOCK_CHARS:
        raise DraftError("BLOCK_TEXT")


class Draft:
    def __init__(self, *, session_id, doc_type, tone, source, original_text):
        self.draft_id = str(uuid.uuid4())
        self.session_id = session_id
        self.doc_type = doc_type
        self.tone = tone
        self.source = dict(source)            # TextInput.to_dict() of the input that created the draft
        self.original_text = original_text    # the user's first words, verbatim (raw transcript for speech)
        self.versions: list[Version] = []
        self.cursor = -1
        self._next = 0
        self._vn = 0                          # version numbers are never reused, even after undo + new edit
        self.pending_question = None          # clarification awaiting the user's answer
        # UIV2-F1: a new document never silently discards the open one. The draft this one replaced is kept (one
        # level): Undo on this draft's first version brings it back, Redo returns here (DraftDesk.op).
        self.replaced: "Draft | None" = None
        self.replaced_by: "Draft | None" = None
        self.replaced_by_cursor: int | None = None

    # ---- ids --------------------------------------------------------------------------------------
    def new_id(self):
        self._next += 1
        return "b%d" % self._next

    # ---- state ------------------------------------------------------------------------------------
    @property
    def current(self) -> Version | None:
        return self.versions[self.cursor] if self.cursor >= 0 else None

    @property
    def can_undo(self):
        return self.cursor > 0 or (self.cursor == 0 and self.replaced is not None)

    @property
    def can_redo(self):
        return 0 <= self.cursor < len(self.versions) - 1 or \
            (self.replaced_by is not None and self.cursor == self.replaced_by_cursor)

    def push(self, *, blocks, facts, exclusions, missing, op, instruction, summary, changed, removed, flags):
        if len(blocks) > MAX_BLOCKS:
            raise DraftError("TOO_MANY_BLOCKS")
        for b in blocks:
            _check_block(b.role, b.text)
        del self.versions[self.cursor + 1:]
        self.replaced_by = None               # a new edit ends the way forward, like any redo
        self.replaced_by_cursor = None
        self._vn += 1
        n = self._vn
        v = Version(n, tuple(blocks), tuple(dict(f) for f in facts), tuple(exclusions), tuple(missing), op,
                    instruction, summary, tuple(changed), tuple(removed), tuple(flags))
        self.versions.append(v)
        if len(self.versions) > MAX_VERSIONS:
            # Keep version 1 (the original draft) and the most recent ones.
            del self.versions[1:len(self.versions) - MAX_VERSIONS + 1]
        self.cursor = len(self.versions) - 1
        self.pending_question = None
        return v

    def undo(self):
        if self.cursor <= 0:                  # going back to a replaced draft is DraftDesk.op's switch
            raise DraftError("NOTHING_TO_UNDO")
        self.cursor -= 1
        self.pending_question = None
        return self.current

    def redo(self):
        if not 0 <= self.cursor < len(self.versions) - 1:
            raise DraftError("NOTHING_TO_REDO")
        self.cursor += 1
        self.pending_question = None
        return self.current

    def restore(self, n):
        """Make an earlier version current again by copying it forward as a new version (history is kept)."""
        src = next((v for v in self.versions if v.n == n), None)
        if src is None:
            raise DraftError("NO_SUCH_VERSION")
        cur = self.current
        changed, removed = diff_ids(cur.blocks if cur else (), src.blocks)
        return self.push(blocks=src.blocks, facts=src.facts, exclusions=src.exclusions, missing=src.missing,
                         op="restored", instruction="restore version %d" % n, summary="Restored version %d." % n,
                         changed=changed, removed=removed, flags=src.flags)

    def to_dict(self, *, include_history=True):
        cur = self.current
        # uri.ti.draft.v1 (docs/integration/ti_ws_20261009/TI_DRAFT_CONTRACT.md): the one contract every surface
        # (Draft panel, a future A2UI draft surface) reads. A draft never sends, saves or executes anything.
        out = {"schema": SNAPSHOT_SCHEMA, "execution": dict(EXECUTION_NONE),
               "draft_id": self.draft_id, "doc_type": self.doc_type, "tone": self.tone, "source": dict(self.source),
               "original_text": self.original_text, "version": cur.n if cur else 0,
               "position": self.cursor + 1, "count": len(self.versions), "can_undo": self.can_undo,
               "can_redo": self.can_redo, "current": cur.to_dict() if cur else None,
               "pending_question": self.pending_question}
        if self.cursor == 0 and self.replaced is not None and self.replaced.current is not None:
            out["replaced"] = {"doc_type": self.replaced.doc_type, "version": self.replaced.current.n}
        if include_history:
            first = self.versions[0] if self.versions else None
            prev = self.versions[self.cursor - 1] if self.cursor > 0 else None
            out["first"] = first.to_dict() if first else None
            out["previous"] = prev.to_dict() if prev else None
            out["history"] = [{"n": v.n, "op": v.op, "summary": v.summary, "instruction": v.instruction[:200]}
                              for v in self.versions]
        return out


SNAPSHOT_SCHEMA = "uri.ti.draft.v1"
EXECUTION_NONE = {"state": "NOT_EXECUTED", "sent": False, "saved": False,
                  "note": "Drafting never sends, saves or executes. Actions go to Core, which asks for approval."}


def diff_ids(old_blocks, new_blocks):
    old = {b.id: b for b in old_blocks}
    new = {b.id: b for b in new_blocks}
    changed = [b.id for b in new_blocks if b.id not in old or old[b.id].text != b.text or old[b.id].role != b.role]
    removed = [i for i in old if i not in new]
    return changed, removed


def split_paragraphs(role, text):
    """Body text holding several paragraphs (blank-line separated) becomes several body blocks, so "the second
    paragraph" always names a block (live finding LQ-7: the model put two paragraphs in one body block)."""
    if role != "body":
        return [text]
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return parts or [text]


def blocks_from_model(draft: Draft, items) -> list:
    """Model blocks [{"role", "text"}] -> Block list with fresh ids. Empty blocks are dropped."""
    out = []
    for it in items:
        role, text = it.get("role"), (it.get("text") or "").strip()
        if role not in ROLES:
            role = "line"
        if not text:
            continue
        for part in split_paragraphs(role, text):
            _check_block(role, part)
            out.append(Block(draft.new_id(), role, part))
    if not out:
        raise DraftError("EMPTY_DRAFT")
    return out


def apply_edits(draft: Draft, blocks, edits, *, allowed_ids=None):
    """Apply edit operations deterministically. Returns (new_blocks, applied, dropped).

    edits: [{"op": "replace"|"delete"|"insert_after"|"insert_before", "block_id", "role"?, "text"?}]
    allowed_ids: when not None, edits to blocks outside this set are DROPPED (reported, never applied). Inserts are
    allowed only next to an allowed block.
    Blocks that no edit touches are carried over unchanged (same id, same bytes).
    """
    cur = list(blocks)
    index = {b.id: i for i, b in enumerate(cur)}
    applied, dropped = [], []
    replace, delete, before, after = {}, set(), {}, {}
    for e in edits:
        op, bid = e.get("op"), e.get("block_id")
        if op not in ("replace", "delete", "insert_after", "insert_before") or bid not in index:
            dropped.append({"edit": e, "reason": "UNKNOWN_BLOCK_OR_OP"})
            continue
        if allowed_ids is not None and bid not in allowed_ids:
            dropped.append({"edit": e, "reason": "OUTSIDE_TARGET"})
            continue
        if op == "replace":
            text = (e.get("text") or "").strip()
            if not text:
                op = "delete"
            else:
                role = e.get("role") if e.get("role") in ROLES else cur[index[bid]].role
                _check_block(role, text)
                replace[bid] = (role, text)
                applied.append(e)
                continue
        if op == "delete":
            delete.add(bid)
            applied.append(e)
            continue
        text = (e.get("text") or "").strip()
        if not text:
            dropped.append({"edit": e, "reason": "EMPTY_INSERT"})
            continue
        role = e.get("role") if e.get("role") in ROLES else "body"
        _check_block(role, text)
        for part in split_paragraphs(role, text):         # inserted paragraphs are separate blocks too (r12)
            (after if op == "insert_after" else before).setdefault(bid, []).append((role, part))
        applied.append(e)
    out = []
    for b in cur:
        for role, text in before.get(b.id, ()):
            out.append(Block(draft.new_id(), role, text))
        if b.id in delete:
            pass
        elif b.id in replace:
            role, text = replace[b.id]
            parts = split_paragraphs(role, text)
            out.append(b if (role, parts[0]) == (b.role, b.text) else Block(b.id, role, parts[0]))
            out.extend(Block(draft.new_id(), role, p) for p in parts[1:])
        else:
            out.append(b)
        for role, text in after.get(b.id, ()):
            out.append(Block(draft.new_id(), role, text))
    return out, applied, dropped
