"""Writes the shared A2UI contract fixtures that BOTH the Python and the Dart validators must agree on (A-AC1).

  python tests/a2ui/make_fixtures.py      -> tests/a2ui/fixtures/contract_cases.json

Each case: {"name", "messages": [...], "expect": "valid" | <first error code>}.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from uri_a2ui import validate as V  # noqa: E402

CAT = "uri:a2ui/catalog/v1"


def create(sid="s1", theme=None):
    return {"version": "v0.9", "createSurface": {"surfaceId": sid, "catalogId": CAT,
                                                 "theme": theme or {"agentDisplayName": "URI", "placement": "companion"}}}


def comps(c, sid="s1"):
    return {"version": "v0.9", "updateComponents": {"surfaceId": sid, "components": c}}


def btn(i="b", name="surface.dismiss", ctx=None):
    return {"id": i, "component": "Button", "label": "OK", "action": {"event": {"name": name, "context": ctx or {}}}}


GOOD = [{"id": "root", "component": "Column", "children": ["t", "b"]},
        {"id": "t", "component": "Text", "text": "Hello", "variant": "title"}, btn()]


def mutate(fn):
    c = copy.deepcopy(GOOD)
    fn(c)
    return c


CASES = [
    ("good_minimal", [create(), comps(GOOD)], "valid"),
    ("good_data", [create(), {"version": "v0.9", "updateDataModel": {"surfaceId": "s1", "path": "/", "value": {"draft": {"x": 1}}}}], "valid"),
    ("good_delete", [{"version": "v0.9", "deleteSurface": {"surfaceId": "s1"}}], "valid"),
    ("bad_version", [{"version": "v0.8", "deleteSurface": {"surfaceId": "s1"}}], "BAD_VERSION"),
    ("two_payloads", [{"version": "v0.9", "deleteSurface": {"surfaceId": "s1"}, "createSurface": {"surfaceId": "s1"}}], "BAD_MESSAGE"),
    ("bad_surface_id", [{"version": "v0.9", "deleteSurface": {"surfaceId": "../x"}}], "BAD_SURFACE_ID"),
    ("unknown_catalog", [{"version": "v0.9", "createSurface": {"surfaceId": "s1", "catalogId": "https://a2ui.org/basic"}}], "UNKNOWN_CATALOG"),
    ("theme_colour", [create(theme={"primaryColor": "#ff0000"})], "THEME_KEY_REFUSED"),
    ("theme_icon_url", [create(theme={"iconUrl": "https://evil.example/x.png"})], "THEME_KEY_REFUSED"),
    ("bad_placement", [create(theme={"placement": "fullscreen"})], "BAD_ENUM"),
    ("send_data_model", [{"version": "v0.9", "createSurface": {"surfaceId": "s1", "catalogId": CAT, "sendDataModel": True}}], "SEND_DATA_MODEL_REFUSED"),
    ("extra_field", [{"version": "v0.9", "deleteSurface": {"surfaceId": "s1", "x": 1}}], "UNKNOWN_FIELD"),
    ("unknown_component", [comps(mutate(lambda c: c.append({"id": "w", "component": "WebView"})))], "UNKNOWN_COMPONENT"),
    ("unknown_property", [comps(mutate(lambda c: c[1].update(style={"color": "red"})))], "UNKNOWN_PROPERTY"),
    ("missing_required", [comps(mutate(lambda c: c[1].pop("text")))], "MISSING_PROPERTY"),
    ("duplicate_id", [comps(mutate(lambda c: c.append({"id": "t", "component": "Divider"})))], "DUPLICATE_ID"),
    ("bad_id", [comps(mutate(lambda c: c[1].update(id="9x")))], "BAD_ID"),
    ("no_root", [comps(mutate(lambda c: c[0].update(id="top")))], "NO_ROOT"),
    ("dangling", [comps(mutate(lambda c: c[0]["children"].append("ghost")))], "DANGLING_REF"),
    ("cycle", [comps([{"id": "root", "component": "Column", "children": ["a"]},
                      {"id": "a", "component": "Card", "child": "b"},
                      {"id": "b", "component": "Card", "child": "a"}])], "SHARED_OR_ROOT_CHILD"),
    ("shared_child", [comps([{"id": "root", "component": "Column", "children": ["a", "c"]},
                             {"id": "a", "component": "Card", "child": "t"},
                             {"id": "c", "component": "Card", "child": "t"},
                             {"id": "t", "component": "Text", "text": "x"}])], "SHARED_OR_ROOT_CHILD"),
    ("unreachable", [comps(mutate(lambda c: c.append({"id": "lost", "component": "Divider"})))], "UNREACHABLE"),
    ("too_deep", [comps([{"id": "root", "component": "Card", "child": "c1"}] +
                        [{"id": f"c{i}", "component": "Card", "child": f"c{i + 1}"} for i in range(1, 9)] +
                        [{"id": "c9", "component": "Divider"}])], "TOO_DEEP"),
    ("too_many", [comps([{"id": "root", "component": "Column", "children": [f"d{i}" for i in range(120)]}] +
                        [{"id": f"d{i}", "component": "Divider"} for i in range(120)])], "TOO_MANY_COMPONENTS"),
    ("url_in_text", [comps(mutate(lambda c: c[1].update(text="click https://evil.example")))], "URL_REFUSED"),
    ("javascript_in_text", [comps(mutate(lambda c: c[1].update(text="javascript:alert(1)")))], "URL_REFUSED"),
    ("plain_colon_ok", [create(), comps(mutate(lambda c: c[1].update(text="Source data: DoPT O.M.")))], "valid"),
    ("long_text", [comps(mutate(lambda c: c[1].update(text="x" * 4001)))], "BAD_TEXT"),
    ("bad_enum", [comps(mutate(lambda c: c[1].update(variant="blink")))], "BAD_ENUM"),
    ("unknown_action", [comps(mutate(lambda c: c.__setitem__(2, btn(name="shell.exec"))))], "UNKNOWN_ACTION"),
    ("function_call_action", [comps(mutate(lambda c: c[2].update(action={"functionCall": {"call": "openUrl", "args": {}}})))], "BAD_ACTION"),
    ("unknown_context_key", [comps(mutate(lambda c: c.__setitem__(2, btn(ctx={"x": 1}))))], "UNKNOWN_CONTEXT_KEY"),
    ("missing_context_key", [comps(mutate(lambda c: c.__setitem__(2, btn(name="scheduler.review_artifact",
                                                                          ctx={"decision": "approve"}))))], "MISSING_CONTEXT_KEY"),
    ("input_writes_bound", [comps(mutate(lambda c: (c[0]["children"].append("i"), c.append(
        {"id": "i", "component": "TextField", "label": "x", "value": {"path": "/bound/proposal_sha256"}}))))], "READ_ONLY_PATH"),
    ("bad_pointer", [comps(mutate(lambda c: (c[0]["children"].append("i"), c.append(
        {"id": "i", "component": "TextField", "label": "x", "value": {"path": "/a//b"}}))))], "BAD_PATH"),
    ("bad_sha", [comps(mutate(lambda c: (c[0]["children"].append("i"), c.append(
        {"id": "i", "component": "ArtifactImage", "artifactId": 1, "sha256": "ABC"}))))], "BAD_SHA256"),
    ("dup_option", [comps(mutate(lambda c: (c[0]["children"].append("i"), c.append(
        {"id": "i", "component": "ChoicePicker", "label": "x", "value": {"path": "/d/x"},
         "options": [{"label": "a", "value": "a"}, {"label": "b", "value": "a"}]}))))], "DUPLICATE_OPTION"),
    ("data_too_large", [{"version": "v0.9", "updateDataModel": {"surfaceId": "s1", "path": "/", "value": {"x": "y" * 3999, "z": ["y" * 3999] * 20}}}], "DATA_TOO_LARGE"),
    ("data_bad_path", [{"version": "v0.9", "updateDataModel": {"surfaceId": "s1", "path": "draft", "value": 1}}], "BAD_PATH"),
]


def main():
    out = []
    for name, msgs, expect in CASES:
        errs = []
        for m in msgs:
            errs += V.validate_message(m)
        got = errs[0]["code"] if errs else "valid"
        assert got == expect, (name, got, expect, errs[:3])
        out.append({"name": name, "messages": msgs, "expect": expect})
    p = ROOT / "tests" / "a2ui" / "fixtures" / "contract_cases.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(out)} cases -> {p}")


if __name__ == "__main__":
    main()
