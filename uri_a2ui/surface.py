"""Surface: one interface instance owned by one authority.

A surface is components + an initial data model + BOUND data (read-only facts the authority vouches for, e.g. a
proposal hash) + the action names it allows. `messages()` renders it as A2UI v0.9 messages; the digest covers
everything except the user-editable data, and is delivered to the renderer at `/bound/surface/digest` so every action
can echo the exact version the user saw.

`check_action(surface, action)` is the authority-side gate for a client `action` message. It returns the resolved
context only if: the surface digest matches, the source component exists and is a Button carrying that action name,
the action is allowed on the surface, every literal in the Button's declared context was sent unchanged, every value
bound to `/bound/...` equals the bound data, and every value matches the action's schema. The authority then still
re-validates against its own state (owner, proposal hash, artifact hash).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field

from . import actions as A
from . import catalog as C
from .validate import A2uiInvalid, is_binding, require_valid, validate_components

_SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def resolve(data, pointer):
    """Value at an absolute JSON pointer, or KeyError."""
    if pointer == "/":
        return data
    cur = data
    for seg in pointer[1:].split("/"):
        seg = seg.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            cur = cur[seg]
        else:
            raise KeyError(pointer)
    return cur


@dataclass
class Surface:
    surface_id: str
    kind: str
    components: list
    data: dict = field(default_factory=dict)
    bound: dict = field(default_factory=dict)
    actions: tuple = ()
    placement: str = "companion"
    title: str = ""
    revision: int = 1

    def __post_init__(self):
        bad = [a for a in self.actions if a not in A.ACTIONS]
        if bad:
            raise A2uiInvalid([{"code": "UNKNOWN_ACTION", "path": "/actions", "message": ",".join(bad)}])
        if self.placement not in C.PLACEMENTS:
            raise A2uiInvalid([{"code": "BAD_ENUM", "path": "/placement", "message": self.placement}])
        errs = validate_components(self.components, set(self.actions))
        if errs:
            raise A2uiInvalid(errs)
        require_valid(self.messages())

    @property
    def digest(self) -> str:
        body = {"surfaceId": self.surface_id, "kind": self.kind, "catalogId": C.CATALOG_ID, "placement": self.placement,
                "components": self.components, "bound": self.bound, "actions": sorted(self.actions),
                "revision": self.revision, "title": self.title}
        return hashlib.sha256(canonical(body)).hexdigest()

    def model(self) -> dict:
        m = copy.deepcopy(self.data)
        m["bound"] = dict(copy.deepcopy(self.bound), surface={"digest": self.digest, "revision": self.revision,
                                                              "kind": self.kind, "title": self.title})
        return m

    def messages(self) -> list:
        theme = {"agentDisplayName": "URI", "placement": self.placement}
        return [
            {"version": C.VERSION, "createSurface": {"surfaceId": self.surface_id, "catalogId": C.CATALOG_ID, "theme": theme}},
            {"version": C.VERSION, "updateComponents": {"surfaceId": self.surface_id, "components": self.components}},
            {"version": C.VERSION, "updateDataModel": {"surfaceId": self.surface_id, "path": "/", "value": self.model()}},
        ]

    def delete_message(self) -> dict:
        return {"version": C.VERSION, "deleteSurface": {"surfaceId": self.surface_id}}

    def to_record(self) -> dict:
        return {"surface_id": self.surface_id, "kind": self.kind, "components": self.components, "data": self.data,
                "bound": self.bound, "actions": list(self.actions), "placement": self.placement, "title": self.title,
                "revision": self.revision}

    @classmethod
    def from_record(cls, r) -> "Surface":
        return cls(r["surface_id"], r["kind"], r["components"], r["data"], r["bound"], tuple(r["actions"]),
                   r["placement"], r.get("title", ""), r["revision"])

    def component(self, cid):
        return next((c for c in self.components if c["id"] == cid), None)


class ActionRefused(ValueError):
    def __init__(self, code, detail=""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


def _typed(kind, v):
    opt = kind.endswith("?")
    kind = kind.rstrip("?")
    if v is None or v == "":
        return opt
    if kind == "str":
        return isinstance(v, str) and len(v) <= A.MAX_CONTEXT_STRING
    if kind == "int":
        return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 10 ** 6
    if kind == "bool":
        return isinstance(v, bool)
    if kind == "sha256":
        return isinstance(v, str) and bool(_SHA.match(v))
    if kind == "time":
        return isinstance(v, str) and bool(_TIME.match(v))
    if kind == "date":
        return isinstance(v, str) and bool(_DATE.match(v))
    if kind == "keys":
        return isinstance(v, list) and len(v) <= C.MAX_OPTIONS and all(isinstance(x, str) and _SLUG.match(x) for x in v)
    if kind.startswith("enum:"):
        return v in kind[5:].split("|")
    return False


def check_action(surface: Surface, action) -> dict:
    """Authority-side gate for one client `action` message. Returns the checked context (without surface_digest)."""
    if not isinstance(action, dict) or set(action) - {"name", "surfaceId", "sourceComponentId", "timestamp", "context"} \
            or not {"name", "surfaceId", "sourceComponentId", "context"} <= set(action):
        raise ActionRefused("BAD_ACTION_MESSAGE")
    if action["surfaceId"] != surface.surface_id:
        raise ActionRefused("SURFACE_MISMATCH")
    ctx = action["context"]
    if not isinstance(ctx, dict):
        raise ActionRefused("BAD_CONTEXT")
    if ctx.get("surface_digest") != surface.digest:
        raise ActionRefused("STALE_SURFACE", "the surface changed since it was shown; review it again")
    name = action["name"]
    if name not in surface.actions:
        raise ActionRefused("ACTION_NOT_ALLOWED_ON_SURFACE", str(name)[:64])
    comp = surface.component(action["sourceComponentId"])
    if comp is None or comp["component"] != "Button" or comp["action"]["event"]["name"] != name:
        raise ActionRefused("NOT_FROM_THIS_BUTTON")
    declared = comp["action"]["event"].get("context", {})
    schema = A.ACTIONS[name]["context"]
    sent = {k: v for k, v in ctx.items() if k != "surface_digest"}
    if set(sent) - set(declared):
        raise ActionRefused("UNDECLARED_CONTEXT", ",".join(sorted(set(sent) - set(declared))))
    model = surface.model()
    out = {}
    for k, decl in declared.items():
        v = sent.get(k)
        if is_binding(decl):
            p = decl["path"]
            if p == "/bound" or p.startswith("/bound/"):
                try:
                    want = resolve(model, p)
                except (KeyError, IndexError, ValueError):
                    raise ActionRefused("BOUND_VALUE_MISSING", k) from None
                if v != want:
                    raise ActionRefused("BOUND_VALUE_MISMATCH", k)
        elif v != decl:
            raise ActionRefused("LITERAL_CHANGED", k)
        if not _typed(schema[k], v):
            raise ActionRefused("BAD_CONTEXT_VALUE", k)
        out[k] = v
    return out
