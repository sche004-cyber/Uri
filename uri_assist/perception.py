"""Perception contracts and adapters (A0). Read-only.

Snapshot schemas an adapter must produce (all content UNTRUSTED):

  Adapters return the snapshot with `target_id` set to the target they captured (required).

  uri.assist.dom.v1  {schema, url, title, lang?, selection, headings[], text, fields[{id, tag, type, name, label,
                      autocomplete, placeholder, required, readonly, value, rect?}], sensitive_rects?}
                      produced by the browser extension (`browser_extension/snapshot.js`) with `activeTab`.
  uri.assist.uia.v1  {schema, window{title, process, pid}, text?, elements[{role, name, automation_id, value,
                      is_password, required?, readonly?, rect?}]}
                      produced by a Windows UI Automation adapter (NOT IMPLEMENTED in this build; see adapters).

`normalise()` validates the schema, bounds every size, applies `redact` and returns an Observation stamped by the
access controller. Adapters never decide permissions; they are asked for one capture and must return a snapshot
for the target the grant names (a mismatched target id is refused).
"""
from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, Protocol

from . import redact as RD
from .access import AccessController, Permission, ScopeKind, Stamp

MAX_TEXT = 40_000
MAX_FIELDS = 200
MAX_HEADINGS = 60
MAX_STR = 500
DOM, UIA = "uri.assist.dom.v1", "uri.assist.uia.v1"


class PerceptionRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass
class Observation:
    stamp: Stamp
    source: str                     # dom | uia
    title: str
    location: Optional[str]         # page URL (query secrets masked) or window/process name
    selection: str
    headings: list
    text: str
    fields: list
    redactions: dict
    digest: str
    sensitive_rects: list = field(default_factory=list)
    trust: str = "UNTRUSTED_CONTENT"

    @property
    def unlocated_sensitive(self) -> bool:
        """A private field that is on screen but has no rectangle cannot be blacked out. Hidden inputs and fields
        the adapter reports as not visible are not on screen (interim review LOW: CSRF hidden inputs)."""
        # An empty field shows nothing; a withheld (D8) or sensitive field with a value must be locatable.
        return any(f.get("sensitive") and f.get("has_value", True) and not f.get("rect") and f.get("visible", True)
                   and f.get("type") != "hidden"
                   for f in self.fields)

    def summary(self) -> dict:
        """What the UI and diagnostics may show (no page text)."""
        return {"source": self.source, "title": self.title[:200], "location": self.location, "fields": len(self.fields),
                "sensitive_fields": sum(1 for f in self.fields if f.get("sensitive")), "redactions": self.redactions,
                "text_chars": len(self.text), "digest": self.digest}


def _s(v, n=MAX_STR):
    return v[:n] if isinstance(v, str) else ""


def _rect(r):
    if isinstance(r, dict) and all(isinstance(r.get(k), (int, float)) for k in ("x", "y", "w", "h")):
        return {k: int(r[k]) for k in ("x", "y", "w", "h")}
    return None


def normalise(snapshot: dict, stamp: Stamp) -> Observation:
    if not isinstance(snapshot, dict) or snapshot.get("schema") not in (DOM, UIA):
        raise PerceptionRefused("SNAPSHOT_SCHEMA")
    counts = Counter()
    if snapshot["schema"] == DOM:
        raw_fields = snapshot.get("fields") or []
        fields = []
        for f in raw_fields[:MAX_FIELDS] if isinstance(raw_fields, list) else []:
            if not isinstance(f, dict):
                continue
            base = {k: _s(f.get(k)) for k in ("id", "tag", "type", "name", "label", "autocomplete", "placeholder")}
            base.update(required=bool(f.get("required")), readonly=bool(f.get("readonly")), value=_s(f.get("value"), 2000),
                        visible=f.get("visible") is not False)
            r = _rect(f.get("rect"))
            if r:
                base["rect"] = r
            fields.append(RD.redact_field(base, counts))
        title, location = _s(snapshot.get("title")), RD.redact_text(_s(snapshot.get("url"), 2048), counts)
        headings = [RD.redact_text(_s(h, 300), counts) for h in (snapshot.get("headings") or [])[:MAX_HEADINGS]
                    if isinstance(h, str)]
        source = "dom"
    else:
        win = snapshot.get("window") or {}
        fields = []
        for e in (snapshot.get("elements") or [])[:MAX_FIELDS]:
            if not isinstance(e, dict):
                continue
            base = {"role": _s(e.get("role")), "name": _s(e.get("name")), "label": _s(e.get("name")),
                    "automation_id": _s(e.get("automation_id")), "is_password": e.get("is_password") is True,
                    "required": bool(e.get("required")), "readonly": bool(e.get("readonly")),
                    "value": _s(e.get("value"), 2000), "visible": e.get("offscreen") is not True}
            r = _rect(e.get("rect"))
            if r:
                base["rect"] = r
            fields.append(RD.redact_field(base, counts))
        title, location, headings = _s(win.get("title")), _s(win.get("process"), 200), []
        source = "uia"
    selection = RD.redact_text(_s(snapshot.get("selection"), 4000), counts)
    text = RD.redact_text(_s(snapshot.get("text"), MAX_TEXT), counts)
    title = RD.redact_text(title, counts)
    rects = [r for r in (_rect(x) for x in (snapshot.get("sensitive_rects") or [])) if r]
    rects += [f["rect"] for f in fields if f.get("sensitive") and f.get("rect")]
    body = {"title": title, "location": location, "selection": selection, "headings": headings, "text": text,
            "fields": fields}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return Observation(stamp, source, title, location, selection, headings, text, fields, dict(counts), digest, rects)


# ---- adapters ------------------------------------------------------------------------------------------------------

AVAILABLE, UNAVAILABLE = "AVAILABLE", "UNAVAILABLE"


class Adapter(Protocol):
    kind: ScopeKind
    name: str

    def status(self) -> dict: ...

    def targets(self) -> list: ...                      # [{"target_id", "label", "origin"?}]

    def capture(self, target_id: str) -> dict: ...      # a uri.assist.*.v1 snapshot

    def screenshot(self, target_id: str) -> Optional[bytes]: ...   # PNG bytes or None


class UnavailableAdapter:
    """An honest placeholder: reports why it cannot run and refuses every call."""

    def __init__(self, kind: ScopeKind, name: str, reason: str):
        self.kind, self.name, self.reason = kind, name, reason

    def status(self):
        return {"adapter": self.name, "kind": self.kind.value, "state": UNAVAILABLE, "reason": self.reason}

    def targets(self):
        raise PerceptionRefused("ADAPTER_UNAVAILABLE")

    def capture(self, target_id):
        raise PerceptionRefused("ADAPTER_UNAVAILABLE")

    def screenshot(self, target_id):
        raise PerceptionRefused("ADAPTER_UNAVAILABLE")


def default_adapters() -> dict:
    """What this build can actually do. Nothing here pretends to work."""
    win = platform.system() == "Windows"
    return {
        ScopeKind.BROWSER_TAB: UnavailableAdapter(
            ScopeKind.BROWSER_TAB, "browser_extension",
            "The URI browser extension's snapshot script exists and is tested in Chromium, but its channel to the "
            "URI worker is not implemented in A0."),
        ScopeKind.DESKTOP_WINDOW: UnavailableAdapter(
            ScopeKind.DESKTOP_WINDOW, "windows_uia",
            "Windows UI Automation adapter not implemented in A0" + ("" if win else " (and this host is not Windows)")),
        ScopeKind.ENTIRE_SCREEN: UnavailableAdapter(
            ScopeKind.ENTIRE_SCREEN, "screen_capture",
            "Screen capture adapter not implemented in A0; URI never captures the screen without one."),
    }


class Perceiver:
    """The only path from an adapter to an Observation. Checks the grant before AND after the capture."""

    def __init__(self, access: AccessController, adapters: dict):
        self.access, self.adapters = access, adapters
        self.last_observation_at: Optional[float] = None

    def adapter_for(self, kind: ScopeKind):
        return self.adapters.get(ScopeKind(kind))

    def targets(self, kind) -> list:
        a = self.adapter_for(kind)
        if a is None:
            raise PerceptionRefused("ADAPTER_UNAVAILABLE")
        out = []
        for t in a.targets()[:50]:
            if isinstance(t, dict) and isinstance(t.get("target_id"), str):
                out.append({"target_id": t["target_id"][:200], "label": _s(t.get("label"), 200),
                            "origin": _s(t.get("origin"), 200) or None})
        return out

    def observe(self) -> Observation:
        grant = self.access.require(Permission.OBSERVE)
        adapter = self.adapter_for(grant.scope.kind)
        if adapter is None:
            raise PerceptionRefused("ADAPTER_UNAVAILABLE")
        stamp = self.access.stamp("uia" if grant.scope.kind == ScopeKind.DESKTOP_WINDOW else "dom")
        snap = adapter.capture(grant.scope.target_id)
        # The adapter must say which target it captured (the page script cannot know URI's id; the adapter's channel
        # attaches it). Missing or different -> refused (interim review LOW: the check was vacuous when absent).
        if not isinstance(snap, dict) or snap.get("target_id") is None:
            raise PerceptionRefused("TARGET_UNBOUND")
        if snap.get("target_id") != grant.scope.target_id:
            raise PerceptionRefused("TARGET_CHANGED")
        obs = normalise(snap, stamp)
        self.access.check_fresh(stamp, Permission.OBSERVE)     # revoked/paused during the capture -> discarded
        self.last_observation_at = stamp.captured_at
        return obs
