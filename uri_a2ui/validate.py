"""Strict validation of A2UI messages against the URI catalog. Every definition is untrusted until this accepts it.

`validate_message(msg)` checks one server->client message; `validate_components(components, allowed_actions)` checks a
component list as a whole (ids, references, cycles, depth, single parent, root); `check_value` checks a property.
Errors are A2UI-style `{"code", "path", "message"}` records; `A2uiInvalid` carries all of them.
"""
from __future__ import annotations

import json
import re

from . import actions as A
from . import catalog as C

_ID = re.compile(C.ID_PATTERN)
_SURFACE_ID = re.compile(C.SURFACE_ID_PATTERN)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SEGMENT = re.compile(r"^(?:[^~/]|~[01])*$")
_URLISH = re.compile(r"(?i)\b(?:https?|ftp|file)://|\b(?:javascript|vbscript|data):\S")
MESSAGE_KEYS = ("createSurface", "updateComponents", "updateDataModel", "deleteSurface")


def u16(s: str) -> int:
    """Length in UTF-16 code units: the unit Dart's String.length uses, so both sides agree (A2UI r2, N2)."""
    return len(s.encode("utf-16-le", "surrogatepass")) // 2   # lone surrogates count as one unit, like Dart


def lone_surrogate(s: str) -> bool:
    """An unpaired UTF-16 surrogate (only possible as a JSON escape). Refused as text everywhere: it cannot be stored,
    hashed or audited reliably, and Python and Dart would size it differently (A2UI r4)."""
    return any(0xD800 <= ord(c) <= 0xDFFF for c in s)


class A2uiInvalid(ValueError):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(f"{e['code']}@{e['path']}" for e in self.errors[:6]))


def _err(code, path, message=""):
    return {"code": code, "path": path, "message": message}


def is_pointer(p, *, relative_ok=True) -> bool:
    if not isinstance(p, str) or u16(p) > 256 or lone_surrogate(p):
        return False
    if p == "/":
        return True
    if p.startswith("/"):
        body = p[1:]
    elif relative_ok and p:
        body = p
    else:
        return False
    return all(seg != "" and _SEGMENT.match(seg) for seg in body.split("/"))


def is_binding(v) -> bool:
    return isinstance(v, dict) and set(v) == {"path"} and is_pointer(v["path"])


def _text_ok(s) -> bool:
    return isinstance(s, str) and u16(s) <= C.MAX_STRING and "\x00" not in s and not lone_surrogate(s)


def check_value(kind, v, path, allowed_actions=None):
    """Errors for one property value of the given catalog kind."""
    if kind == "text":
        if is_binding(v) or _text_ok(v):
            return []
        return [_err("BAD_TEXT", path)]
    if kind == "bool":
        return [] if isinstance(v, bool) or is_binding(v) else [_err("BAD_BOOL", path)]
    if kind == "int":
        return [] if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 10 ** 9 else [_err("BAD_INT", path)]
    if kind == "sha256":
        return [] if isinstance(v, str) and _SHA.match(v) else [_err("BAD_SHA256", path)]
    if kind.startswith("enum:"):
        return [] if isinstance(v, str) and v in kind[5:].split("|") else [_err("BAD_ENUM", path, f"allowed: {kind[5:]}")]
    if kind == "ref":
        return [] if isinstance(v, str) and _ID.match(v) else [_err("BAD_REF", path)]
    if kind == "refs":
        if isinstance(v, list):
            if len(v) > C.MAX_COMPONENTS or not all(isinstance(x, str) and _ID.match(x) for x in v):
                return [_err("BAD_REFS", path)]
            return []
        if isinstance(v, dict) and set(v) == {"componentId", "path"} and isinstance(v["componentId"], str) \
                and _ID.match(v["componentId"]) and is_pointer(v["path"], relative_ok=False):
            return []
        return [_err("BAD_REFS", path)]
    if kind == "path":
        if not is_binding(v):
            return [_err("BAD_PATH", path)]
        p = v["path"]
        if any(p == pre or p.startswith(pre + "/") for pre in C.READ_ONLY_PREFIXES):
            return [_err("READ_ONLY_PATH", path, "inputs cannot write bound data")]
        return []
    if kind == "options":
        if not isinstance(v, list) or not 0 < len(v) <= C.MAX_OPTIONS:
            return [_err("BAD_OPTIONS", path)]
        errs = []
        for i, o in enumerate(v):
            if not (isinstance(o, dict) and set(o) == {"label", "value"} and _text_ok(o["label"])
                    and isinstance(o["value"], str) and 0 < u16(o["value"]) <= 128 and not lone_surrogate(o["value"])):
                errs.append(_err("BAD_OPTION", f"{path}/{i}"))
        if len({o["value"] for o in v if isinstance(o, dict) and isinstance(o.get("value"), str)}) != len(v):
            errs.append(_err("DUPLICATE_OPTION", path))
        return errs
    if kind == "action":
        return _check_action_decl(v, path, allowed_actions)
    return [_err("UNKNOWN_KIND", path, kind)]


def _check_action_decl(v, path, allowed_actions):
    if not (isinstance(v, dict) and set(v) == {"event"} and isinstance(v["event"], dict)
            and set(v["event"]) <= {"name", "context"} and "name" in v["event"]):
        return [_err("BAD_ACTION", path, "only {event: {name, context}} is allowed (no functionCall)")]
    name, ctx = v["event"]["name"], v["event"].get("context", {})
    if not isinstance(name, str) or name not in A.ACTIONS:
        return [_err("UNKNOWN_ACTION", path, str(name)[:64])]
    if allowed_actions is not None and name not in allowed_actions:
        return [_err("ACTION_NOT_ALLOWED_ON_SURFACE", path, name)]
    if not isinstance(ctx, dict) or len(ctx) > C.MAX_CONTEXT_KEYS:
        return [_err("BAD_CONTEXT", path)]
    schema = A.ACTIONS[name]["context"]
    errs = []
    for k, val in ctx.items():
        if k not in schema:
            errs.append(_err("UNKNOWN_CONTEXT_KEY", f"{path}/event/context/{k}"))
        elif not (is_binding(val) or _literal_ok(val)):
            errs.append(_err("BAD_CONTEXT_VALUE", f"{path}/event/context/{k}"))
    for k, kind in schema.items():
        if k not in ctx and not kind.endswith("?"):
            errs.append(_err("MISSING_CONTEXT_KEY", f"{path}/event/context/{k}"))
    return errs


def _literal_ok(v) -> bool:
    if isinstance(v, bool) or v is None:
        return True
    if isinstance(v, int):
        return 0 <= v <= 10 ** 9
    if isinstance(v, str):
        return u16(v) <= A.MAX_CONTEXT_STRING and not lone_surrogate(v)
    if isinstance(v, list):
        return len(v) <= C.MAX_OPTIONS and all(isinstance(x, str) and u16(x) <= 128 and not lone_surrogate(x) for x in v)
    return False


def _no_urls(obj, path, errs):
    """A text value that looks like a URL or a script scheme is refused anywhere in a definition."""
    if isinstance(obj, str):
        if _URLISH.search(obj):
            errs.append(_err("URL_REFUSED", path))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _no_urls(v, f"{path}/{k}", errs)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _no_urls(v, f"{path}/{i}", errs)


def validate_components(components, allowed_actions=None, path="/components"):
    errs = []
    if not isinstance(components, list) or not components:
        return [_err("BAD_COMPONENTS", path)]
    if len(components) > C.MAX_COMPONENTS:
        return [_err("TOO_MANY_COMPONENTS", path, str(len(components)))]
    by_id, edges = {}, {}
    for i, comp in enumerate(components):
        p = f"{path}/{i}"
        if not isinstance(comp, dict) or "id" not in comp or "component" not in comp:
            errs.append(_err("BAD_COMPONENT", p))
            continue
        cid, ctype = comp["id"], comp["component"]
        if not isinstance(cid, str) or not _ID.match(cid):
            errs.append(_err("BAD_ID", p))
            continue
        if cid in by_id:
            errs.append(_err("DUPLICATE_ID", p, cid))
            continue
        if not isinstance(ctype, str) or ctype not in C.COMPONENTS:
            errs.append(_err("UNKNOWN_COMPONENT", p, str(ctype)[:64]))
            continue
        spec = C.COMPONENTS[ctype]
        for k in comp:
            if k in ("id", "component"):
                continue
            if k not in spec:
                errs.append(_err("UNKNOWN_PROPERTY", f"{p}/{k}", f"{ctype}.{k}"))
                continue
            errs += check_value(spec[k], comp[k], f"{p}/{k}", allowed_actions)
        for k in C.REQUIRED.get(ctype, ()):
            if k not in comp:
                errs.append(_err("MISSING_PROPERTY", f"{p}/{k}", f"{ctype}.{k}"))
        by_id[cid] = comp
        kids = []
        if "child" in comp and isinstance(comp["child"], str):
            kids.append(comp["child"])
        ch = comp.get("children")
        if isinstance(ch, list):
            kids += [x for x in ch if isinstance(x, str)]
        elif isinstance(ch, dict) and isinstance(ch.get("componentId"), str):
            kids.append(ch["componentId"])
        edges[cid] = kids
    _no_urls(components, path, errs)
    if errs:
        return errs
    if "root" not in by_id:
        return [_err("NO_ROOT", path)]
    parents = {}
    for cid, kids in edges.items():
        for k in kids:
            if k not in by_id:
                errs.append(_err("DANGLING_REF", path, f"{cid} -> {k}"))
            elif k in parents or k == "root":
                errs.append(_err("SHARED_OR_ROOT_CHILD", path, k))
            else:
                parents[k] = cid
    if errs:
        return errs
    seen, depth_err = set(), []

    def walk(cid, depth, stack):
        if cid in stack:
            depth_err.append(_err("CYCLE", path, cid))
            return
        if depth > C.MAX_DEPTH:
            depth_err.append(_err("TOO_DEEP", path, cid))
            return
        seen.add(cid)
        for k in edges.get(cid, ()):
            walk(k, depth + 1, stack | {cid})

    walk("root", 1, frozenset())
    errs += depth_err
    unreachable = sorted(set(by_id) - seen)
    if unreachable and not depth_err:
        errs.append(_err("UNREACHABLE", path, ",".join(unreachable[:5])))
    return errs


def validate_data(value, path="/value"):
    errs = []
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return [_err("BAD_DATA", path, "not JSON")]
    if len(raw.encode("utf-8", "surrogatepass")) > C.MAX_DATA_BYTES:
        return [_err("DATA_TOO_LARGE", path)]

    def walk(v, p):
        if isinstance(v, str) and (u16(v) > C.MAX_STRING or lone_surrogate(v)):
            errs.append(_err("BAD_TEXT", p))
        elif isinstance(v, dict):
            for k, x in v.items():
                if not isinstance(k, str) or u16(k) > 256 or lone_surrogate(k):    # keys too (A2UI r5, R5-1)
                    errs.append(_err("BAD_KEY", p))
                    continue
                walk(x, f"{p}/{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{p}/{i}")
    walk(value, path)
    return errs


MAX_NESTING = 32


def _nesting_ok(obj, limit=MAX_NESTING) -> bool:
    """Iterative depth check before any recursive inspection: hostile nesting is refused, never a RecursionError."""
    stack = [(obj, 1)]
    seen = 0
    while stack:
        v, d = stack.pop()
        if d > limit:
            return False
        seen += 1
        if seen > 200_000:
            return False
        if isinstance(v, dict):
            stack.extend((x, d + 1) for x in v.values())
        elif isinstance(v, list):
            stack.extend((x, d + 1) for x in v)
    return True


def validate_message(msg, allowed_actions=None):
    """Errors for one server->client message (empty list = valid)."""
    if not _nesting_ok(msg):
        return [_err("TOO_NESTED", "/", f"more than {MAX_NESTING} levels")]
    if not isinstance(msg, dict) or msg.get("version") != C.VERSION:
        return [_err("BAD_VERSION", "/version", f"expected {C.VERSION}")]
    keys = [k for k in msg if k != "version"]
    if len(keys) != 1 or keys[0] not in MESSAGE_KEYS:
        return [_err("BAD_MESSAGE", "/", "exactly one of " + ", ".join(MESSAGE_KEYS))]
    kind, body = keys[0], msg[keys[0]]
    if not isinstance(body, dict) or not isinstance(body.get("surfaceId"), str) or not _SURFACE_ID.match(body["surfaceId"]):
        return [_err("BAD_SURFACE_ID", f"/{kind}/surfaceId")]
    allowed = {"createSurface": {"surfaceId", "catalogId", "theme", "sendDataModel"},
               "updateComponents": {"surfaceId", "components"},
               "updateDataModel": {"surfaceId", "path", "value"},
               "deleteSurface": {"surfaceId"}}[kind]
    extra = set(body) - allowed
    if extra:
        return [_err("UNKNOWN_FIELD", f"/{kind}", ",".join(sorted(extra)))]
    if kind == "createSurface":
        errs = []
        if body.get("catalogId") != C.CATALOG_ID:
            errs.append(_err("UNKNOWN_CATALOG", f"/{kind}/catalogId"))
        theme = body.get("theme", {})
        if not isinstance(theme, dict):
            errs.append(_err("BAD_THEME", f"/{kind}/theme"))
        else:
            for k, v in theme.items():
                if k not in C.THEME_KEYS:
                    errs.append(_err("THEME_KEY_REFUSED", f"/{kind}/theme/{k}", "the Living theme is inherited"))
                else:
                    errs += check_value(C.THEME_KEYS[k], v, f"/{kind}/theme/{k}")
        if "sendDataModel" in body and body["sendDataModel"] is not False:
            errs.append(_err("SEND_DATA_MODEL_REFUSED", f"/{kind}/sendDataModel", "inputs travel only in action context"))
        return errs
    if kind == "updateComponents":
        return validate_components(body.get("components"), allowed_actions, f"/{kind}/components")
    if kind == "updateDataModel":
        errs = []
        p = body.get("path", "/")
        if not is_pointer(p, relative_ok=False):
            errs.append(_err("BAD_PATH", f"/{kind}/path"))
        elif any(p == pre or p.startswith(pre + "/") for pre in C.READ_ONLY_PREFIXES):
            # Bound data is set only by the authority's full model load (path "/"), never patched (A2UI r1, F1).
            errs.append(_err("READ_ONLY_PATH", f"/{kind}/path", "bound data cannot be updated in part"))
        if "value" in body:
            errs += validate_data(body["value"], f"/{kind}/value")
        return errs
    return []


def require_valid(messages, allowed_actions=None):
    errs = []
    for i, m in enumerate(messages):
        errs += [dict(e, path=f"/{i}{e['path']}") for e in validate_message(m, allowed_actions)]
    if errs:
        raise A2uiInvalid(errs)
    return messages
