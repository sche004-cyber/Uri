"""Newline-delimited JSON stream handling.

Rules (from the Phase 2A brief): read bytes; split ONLY on b"\\n"; retain the unterminated tail;
persist raw complete lines before interpreting them; tolerate unknown events/fields; a truncated
terminal-looking tail is never authoritative; exit without a valid terminal event is an interruption.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

PARSER_ID = "ndjson-rules/1"


MAX_LINE_BYTES = 4 * 1024 * 1024


class LineSplitter:
    """Bytes in, (raw_line, complete) out. A partial line is held until its newline arrives.

    A line longer than `max_line_bytes` is emitted as INCOMPLETE fragments (raw preserved, never interpreted),
    and the remainder of that same line, up to its newline, is also incomplete: memory stays bounded and an
    oversize line can never be mistaken for, or smuggle in, a complete event."""

    def __init__(self, max_line_bytes: int = MAX_LINE_BYTES):
        self._tail = bytearray()
        self._max = max_line_bytes
        self._discarding = False

    def feed(self, chunk: bytes) -> list[tuple[bytes, bool]]:
        if not chunk:
            return []
        self._tail.extend(chunk)
        out = []
        while True:
            i = self._tail.find(b"\n")
            if i < 0:
                if len(self._tail) > self._max:
                    out.append((bytes(self._tail), False))
                    self._tail.clear()
                    self._discarding = True
                break
            line = bytes(self._tail[: i + 1])  # keeps the newline: raw bytes are preserved exactly
            del self._tail[: i + 1]
            out.append((line, len(line) <= self._max and not self._discarding))
            self._discarding = False
        return out

    def flush_tail(self) -> bytes:
        """Unterminated remainder at EOF. Raw-only; callers must mark it incomplete."""
        out = bytes(self._tail)
        self._tail.clear()
        return out


# ---- declarative event rules -----------------------------------------------------------------

@dataclass(frozen=True)
class EventRule:
    """`when`: {dotted.path: matcher}. Matchers: literal, {"in":[..]}, {"not":x}, {"present":bool},
    {"falsy_or_absent":True}, {"truthy":True}, {"regex":pat}. `emit`: semantic label.
    `extract`: {name: dotted.path} captured when matched."""
    when: dict
    emit: str
    extract: dict = field(default_factory=dict)


def _get(obj, path):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False, None
    return True, cur


def _match(found, value, matcher):
    if isinstance(matcher, dict):
        if "in" in matcher:
            return found and value in matcher["in"]
        if "not" in matcher:
            return not (found and value == matcher["not"])
        if "present" in matcher:
            return found == bool(matcher["present"])
        if "falsy_or_absent" in matcher:
            return (not found) or not value
        if "truthy" in matcher:
            return found and bool(value)
        if "regex" in matcher:
            import re
            return found and isinstance(value, str) and re.search(matcher["regex"], value) is not None
        return False
    return found and value == matcher and type(value) is type(matcher)


def apply_rules(rules, event: dict):
    """-> list of (semantic, extracted_dict). Unknown shapes simply match nothing."""
    out = []
    for r in rules:
        ok = True
        for path, matcher in r.when.items():
            found, value = _get(event, path)
            if not _match(found, value, matcher):
                ok = False
                break
        if ok:
            ext = {}
            for name, path in r.extract.items():
                found, value = _get(event, path)
                if found:
                    ext[name] = value
            out.append((r.emit, ext))
    return out


@dataclass(frozen=True)
class Interpretation:
    parse_status: str          # ok | invalid_json | not_object | incomplete_line | invalid_utf8
    event_type: str | None
    semantics: tuple           # ((label, extracted), ...)

    @property
    def terminal(self):
        return [s for s in self.semantics if s[0] in ("terminal_success_claim", "terminal_error_claim")]


def interpret_line(raw: bytes, rules, complete: bool) -> Interpretation:
    """Interpret ONE already-persisted line. An incomplete line never yields semantics."""
    if not complete:
        return Interpretation("incomplete_line", None, ())
    body = raw.rstrip(b"\r\n")
    if not body.strip():
        return Interpretation("ok", None, ())
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return Interpretation("invalid_utf8", None, ())
    try:
        obj = json.loads(text)
    except ValueError:
        return Interpretation("invalid_json", None, ())
    if not isinstance(obj, dict):
        return Interpretation("not_object", None, ())
    et = obj.get("type") if isinstance(obj.get("type"), str) else None
    return Interpretation("ok", et, tuple(apply_rules(rules, obj)))
