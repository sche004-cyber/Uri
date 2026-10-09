"""The URI component catalog `uri:a2ui/catalog/v1` (the only catalog URI renders).

Each component lists its allowed properties and their kinds. Property kinds:

  text      a string (<= MAX_STRING) or a binding {"path": <JSON pointer>}
  bool      a boolean or a binding
  enum:a|b  one of the listed literals
  ref       the id of one component (single child)
  refs      a list of component ids, or a template {"componentId": id, "path": pointer}
  path      a binding {"path": pointer} (inputs: where the value is written)
  options   a list of {"label": text, "value": str} (<= MAX_OPTIONS)
  action    {"event": {"name": <registered action>, "context": {key: literal | {"path": pointer}}}}
  sha256    64 lowercase hex characters
  int       a non-negative integer (<= 10**9)

Anything not listed is refused: no URLs, no colours, no styles, no scripts, no functions.
"""

CATALOG_ID = "uri:a2ui/catalog/v1"
VERSION = "v0.9"

MAX_COMPONENTS = 120
MAX_DEPTH = 8
MAX_STRING = 4000
MAX_OPTIONS = 80
MAX_CONTEXT_KEYS = 16
MAX_DATA_BYTES = 64 * 1024
ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"
SURFACE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"

PLACEMENTS = ("companion", "workspace", "inline")
THEME_KEYS = {"agentDisplayName": "text", "placement": "enum:" + "|".join(PLACEMENTS)}

COMPONENTS = {
    "Column": {"children": "refs", "gap": "enum:none|small|medium|large"},
    "Row": {"children": "refs", "gap": "enum:none|small|medium|large", "align": "enum:start|center|end|spaceBetween"},
    "Card": {"child": "ref", "tone": "enum:neutral|accent|warning|danger"},
    "Text": {"text": "text", "variant": "enum:title|body|caption|label"},
    "Divider": {},
    "Badge": {"text": "text", "tone": "enum:neutral|accent|success|warning|danger"},
    "Button": {"label": "text", "action": "action", "variant": "enum:primary|secondary|danger", "enabled": "bool"},
    "CheckBox": {"label": "text", "value": "path"},
    "ChoicePicker": {"label": "text", "value": "path", "options": "options", "multiple": "bool"},
    "DateTimeInput": {"label": "text", "value": "path", "mode": "enum:date|time"},
    "TextField": {"label": "text", "value": "path", "maxLength": "int", "multiline": "bool"},
    "ArtifactImage": {"artifactId": "int", "sha256": "sha256", "caption": "text"},
    "List": {"children": "refs"},
}
REQUIRED = {
    "Text": ("text",), "Badge": ("text",), "Button": ("label", "action"), "CheckBox": ("label", "value"),
    "ChoicePicker": ("label", "value", "options"), "DateTimeInput": ("label", "value", "mode"),
    "TextField": ("label", "value"), "ArtifactImage": ("artifactId", "sha256"), "Card": ("child",),
    "Column": ("children",), "Row": ("children",), "List": ("children",),
}
INPUTS = {"CheckBox", "ChoicePicker", "DateTimeInput", "TextField"}
# Inputs write the local data model only. They may never write under these prefixes (read-only data the authority
# bound to the surface, e.g. the proposal hash or the artifact hash).
READ_ONLY_PREFIXES = ("/bound",)
