"""Perception contracts and adapters (A0). Read-only.

Snapshot schemas an adapter must produce (all content UNTRUSTED):

  Adapters return the snapshot with `target_id` set to the target they captured (required).

  uri.assist.dom.v1  {schema, url, title, lang?, selection, selection_source?, selection_withheld?, headings[], text,
                      fields[{id, tag, type, name, label, autocomplete, placeholder, required, readonly, value,
                      has_value?, sensitive?, withheld?, rect?}], sensitive_rects?}
                      produced by the browser extension (`browser_extension/snapshot.js`) with `activeTab`.
  uri.assist.uia.v1  {schema, window{title, process, pid}, text?, elements[{role, name, automation_id, value,
                      is_password, required?, readonly?, rect?}]}
                      produced by a Windows UI Automation adapter (NOT IMPLEMENTED in this build; see adapters).

  Page text, selection and headings (owner decision D10; R13-01 render check): the strings `text`, `selection`
  and `headings` are NOT used. Only `pieces` {text: [piece], selection: [piece], headings: [[piece]]} are, where a
  piece is {t: text, u: [unit index], g: group}, with `units` [{n, a, b, r: [[x, y, w, h] viewport CSS px],
  c: rect count, k: non-space characters, h: text hash}], `viewport` {w, h} and `device_pixel_ratio`. A piece is
  kept only if `onscreen.py` finds every one of its units drawn, in its own colour and in its own box, by the
  adapter's differential render (`probe`, uri.assist.probe.v1, browser_extension/probe.js) taken at observation
  time under the same grant; without a usable probe no page text is kept (fail closed). The same holds for a field's
  `label_pieces` (R14-01): only those make the field's `shown_label`, the only label the Brain sees, and for a
  contenteditable's `value_pieces` (R15-01): only those make its `shown_value`, the only field value the Brain sees
  besides checkbox/radio state. Input, textarea and select values cannot be render-checked and are never sent.

`normalise()` validates the schema, bounds every size, applies `redact` and returns an Observation stamped by the
access controller. A selection is accepted only when the adapter marks it `selection_source: "page_text"` (built from
the page's own text, never from inside a field; R9-01). A field the adapter withheld stays withheld, and its
`has_value` is kept (the adapter sends the value empty; R9-03). Adapters never decide permissions; they are asked for
one capture and must return a snapshot for the target the grant names (a mismatched target id is refused).
"""
from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, Protocol

from . import onscreen as OS
from . import redact as RD
from .access import AccessController, Permission, ScopeKind, Stamp

MAX_TEXT = 40_000
MAX_FIELDS = 200
MAX_HEADINGS = 60
MAX_STR = 500
MAX_TEXT_PIECES, MAX_SEL_PIECES, MAX_HEAD_PIECES, MAX_LABEL_PIECES, MAX_VALUE_PIECES = 4000, 1000, 40, 20, 40
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
    selection_withheld: bool = False   # the user selected something that was not page text (e.g. inside a field)
    trust: str = "UNTRUSTED_CONTENT"

    @property
    def unlocated_sensitive(self) -> bool:
        """A private field that is on screen but has no rectangle cannot be blacked out. Hidden inputs and fields
        the adapter reports as not visible are not on screen (interim review LOW: CSRF hidden inputs)."""
        # An empty field shows nothing; a withheld (D8) or sensitive field with a value, or whose emptiness is not
        # known, must be locatable (R9-03).
        return any(f.get("sensitive") and f.get("has_value") is not False and not f.get("rect") and f.get("visible", True)
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


def normalise(snapshot: dict, stamp: Stamp, probe: Optional[dict] = None) -> Observation:
    """`probe`: the adapter's differential render of this snapshot, taken at observation time (D10, R13-01).
    None -> no page text is kept."""
    if not isinstance(snapshot, dict) or snapshot.get("schema") not in (DOM, UIA):
        raise PerceptionRefused("SNAPSHOT_SCHEMA")
    counts = Counter()
    pieces = snapshot.get("pieces") if isinstance(snapshot.get("pieces"), dict) else {}
    screen = OS.load(probe, snapshot)
    if screen is None and (pieces or snapshot.get("text")):
        counts["pixel_check_unavailable"] += 1
    withheld_values = []            # raw values this layer withheld (never kept; used only to vet the selection)
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
            out = RD.redact_field(base, counts)
            _keep_adapter_withholding(out, f)
            out["shown_label"] = _shown_label(f, screen) if out["visible"] else ""
            out["shown_value"] = _shown_value(f, out, screen)
            fields.append(out)
            if out.get("sensitive"):
                withheld_values.append(base["value"])
        title, location = _s(snapshot.get("title")), RD.redact_url(_s(snapshot.get("url"), 2048), counts)
        headings = []
        raw_heads = pieces.get("headings") if isinstance(pieces.get("headings"), list) else []
        for hp in raw_heads[:MAX_HEADINGS]:
            h = OS.join(OS.keep(hp, screen, counts, MAX_HEAD_PIECES), " ")
            if h:
                headings.append(RD.redact_text(h[:300], counts))
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
            out = RD.redact_field(base, counts)
            fields.append(out)
            if out.get("sensitive"):
                withheld_values.append(base["value"])
        title, location, headings = _s(win.get("title")), _s(win.get("process"), 200), []
        source = "uia"
    # R9-01: text selected inside a field is that field's value. Only a selection the adapter built from page text is
    # accepted, and never one that contains a value withheld above; otherwise only the fact of a selection is kept.
    # The vetting looks at everything the adapter reported as selected (the legacy string and every piece, drawn or
    # not); what is kept is only the pieces drawn on screen (D10).
    sel_pieces = pieces.get("selection") if isinstance(pieces.get("selection"), list) else []
    all_sel = [q for q in (OS._piece(p) for p in sel_pieces[:MAX_SEL_PIECES]) if q]
    raw_sel = _s(snapshot.get("selection"), 4000) + " " + OS.join(all_sel, "")[:4000]
    selection_withheld = snapshot.get("selection_withheld") is True
    keep_sel = True
    if raw_sel.strip() and (snapshot.get("selection_source") != "page_text"
                            or any(v.strip() and v.strip() in raw_sel for v in withheld_values)):
        keep_sel, selection_withheld = False, True
    if selection_withheld:
        counts["selection_withheld"] += 1
    sel = OS.join(OS.keep(sel_pieces, screen, counts, MAX_SEL_PIECES), "")[:4000] if keep_sel else ""
    selection = RD.redact_text(sel, counts)
    text_pieces = pieces.get("text") if isinstance(pieces.get("text"), list) else []
    if not text_pieces and isinstance(snapshot.get("text"), str) and snapshot["text"].strip():
        counts[OS.UNVERIFIED] += 1                     # page text without rectangles cannot be checked
    text = RD.redact_text(OS.join(OS.keep(text_pieces, screen, counts, MAX_TEXT_PIECES), "\n")[:MAX_TEXT], counts)
    title = RD.redact_text(title, counts)
    rects = [r for r in (_rect(x) for x in (snapshot.get("sensitive_rects") or [])) if r]
    rects += [f["rect"] for f in fields if f.get("sensitive") and f.get("rect")]
    body = {"title": title, "location": location, "selection": selection, "headings": headings, "text": text,
            "fields": fields}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return Observation(stamp, source, title, location, selection, headings, text, fields, dict(counts), digest, rects,
                       selection_withheld=selection_withheld)


def _shown_label(raw: dict, screen) -> str:
    """R14-01: the field label the Brain may see: only the label pieces whose own glyphs passed the render check
    (D10). The adapter's `label` string (which may come from aria-label or a label that is not drawn) is used only to
    decide whether the field is private; it is never sent. Redaction counts were taken on `label` already."""
    junk = Counter()
    kept = OS.keep(raw.get("label_pieces"), screen, junk, MAX_LABEL_PIECES)
    return RD.redact_text(OS.join(kept, " ")[:300], junk)


def _shown_value(raw: dict, out: dict, screen) -> str:
    """R15-01: the field value the Brain may see. Checkbox/radio state is a fixed word. A contenteditable's value is
    only its value pieces whose own glyphs passed the render check (D10). An input's, textarea's or select's value is
    drawn by the browser's own editor, not as text nodes the probe can repaint: it cannot be bound to its pixels (it
    may be transparent, masked, covered or scrolled away) and is never sent (fail closed). D8 decides first."""
    if out.get("sensitive") or not out.get("visible"):
        return ""
    kind = out.get("type")
    if kind in ("checkbox", "radio"):
        return out.get("value") if out.get("value") in ("checked", "unchecked") else ""
    if kind != "contenteditable":
        return ""
    junk = Counter()
    kept = OS.keep(raw.get("value_pieces"), screen, junk, MAX_VALUE_PIECES)
    return RD.redact_text(OS.join(kept, " ")[:2000], junk)


def _keep_adapter_withholding(out: dict, raw: dict) -> None:
    """The in-page layer may withhold a field this layer would share (its value is sent empty, so a value-based rule
    such as a short code cannot fire here). Its decision and its `has_value` are kept (R9-03)."""
    adapter_withheld = raw.get("sensitive") is True or raw.get("withheld") in ("sensitive", "not_shared")
    if adapter_withheld and not out.get("sensitive"):
        out.pop("value", None)
        out["sensitive"] = True
        out["withheld"] = "sensitive" if raw.get("withheld") != "not_shared" else "not_shared"
        out["has_value"] = bool(raw.get("value")) or None
    if out.get("sensitive"):
        if raw.get("has_value") is True:
            out["has_value"] = True
        elif not out.get("has_value") and adapter_withheld and raw.get("has_value") is not False:
            out["has_value"] = None      # the adapter withheld it without saying whether it is filled: unknown


# ---- adapters ------------------------------------------------------------------------------------------------------

AVAILABLE, UNAVAILABLE = "AVAILABLE", "UNAVAILABLE"


class Adapter(Protocol):
    kind: ScopeKind
    name: str

    def status(self) -> dict: ...

    def targets(self) -> list: ...                      # [{"target_id", "label", "origin"?}]

    def capture(self, target_id: str) -> dict: ...      # a uri.assist.*.v1 snapshot

    def screenshot(self, target_id: str) -> Optional[bytes]: ...   # PNG bytes or None

    # Optional (D10, R13-01): the differential render (uri.assist.probe.v1) of the snapshot just captured, or None.
    def probe(self, target_id: str) -> Optional[dict]: ...


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

    def probe(self, target_id):
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

    def observe(self, pixel_check: bool = False) -> Observation:
        """`pixel_check` (an ask the user started, D10): also have the adapter render-probe the target under the
        same grant (in-memory screenshots, R13-01), used only to decide which page text is drawn on screen. Without
        a usable probe no page text is kept."""
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
        probe, shot_stamp = None, None
        if pixel_check:
            shot_stamp = self.access.stamp("screenshot")
            try:
                probe = adapter.probe(grant.scope.target_id) if callable(getattr(adapter, "probe", None)) else None
            except Exception:
                probe = None                                     # no probe -> no page text (fail closed)
        obs = normalise(snap, stamp, probe=probe)
        self.access.check_fresh(stamp, Permission.OBSERVE)     # revoked/paused during the capture -> discarded
        if shot_stamp is not None:
            self.access.check_fresh(shot_stamp, Permission.OBSERVE)
        self.last_observation_at = stamp.captured_at
        return obs
