import json
import urllib.request

schema = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "intent_family": {
            "type": "string",
            "enum": [
                "retrieve", "create", "modify", "communicate",
                "execute", "analyze", "compare", "research",
                "navigate", "converse", "unspecified"
            ],
        },
        "requested_operations": {"type": "array", "items": {"type": "string"}},
        "prohibited_operations": {"type": "array", "items": {"type": "string"}},
        "operation_bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "target_id": {"type": "string"},
                },
                "required": ["operation", "target_id"],
                "additionalProperties": False,
            },
        },
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                    "target_id": {"type": "string"},
                },
                "required": ["expression", "target_id"],
                "additionalProperties": False,
            },
        },
        "temporal_references": {"type": "array", "items": {"type": "string"}},
        "constraints": {
            "type": "object",
            "properties": {
                "included_items": {"type": "array", "items": {"type": "string"}},
                "excluded_items": {"type": "array", "items": {"type": "string"}},
                "length_limit": {"type": "string"},
                "language_constraints": {"type": "string"},
            },
            "required": ["included_items", "excluded_items", "length_limit", "language_constraints"],
            "additionalProperties": False,
        },
        "output_preferences": {
            "type": "object",
            "properties": {
                "artifact_type": {"type": "string"},
                "format": {"type": "string"},
                "tone": {"type": "string"},
                "structure": {"type": "string"},
            },
            "required": ["artifact_type", "format", "tone", "structure"],
            "additionalProperties": False,
        },
        "ambiguities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"},
                    "description": {"type": "string"},
                    "candidates": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["kind", "description", "candidates"],
                "additionalProperties": False,
            },
        },
        "context_dependencies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["category", "description"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "goal",
        "intent_family",
        "requested_operations",
        "prohibited_operations",
        "operation_bindings",
        "references",
        "temporal_references",
        "constraints",
        "output_preferences",
        "ambiguities",
        "context_dependencies",
    ],
    "additionalProperties": False,
}

sys_prompt = """Step-1 Semantic Decoder for URIv1.
Extract only what is explicitly expressed in the user turn into JSON.
- goal: concise summary of user goal. Never write drafts or body text.
- intent_family: one intent enum.
- requested_operations: base actions requested in user turn. If none, [].
- prohibited_operations: base actions explicitly negated or forbidden in user turn. If none, [].
- operation_bindings: {operation, target_id} for each operation. If target unknown, empty target_id. If none, [].
- references: {expression, target_id} for referring expressions in user turn. If none, [].
- temporal_references: time words present in user turn. If none, [].
- constraints: explicit limitations stated in user turn.
- output_preferences: format, artifact_type, tone, structure if stated.
- ambiguities: {kind, description, candidates} if turn is ambiguous. If none, [].
- context_dependencies: {category, description} if turn requires prior context. If none, [].
Invariants:
Do NOT invent referents, dates, or operations. Empty lists [] for absent fields."""

test_queries = [
    "Convert this to PDF.",
    "Don't send it. Just draft the email.",
    "Do not summarize this; compare the exact figures in a table.",
]

for q in test_queries:
    payload = {
        "model": "lfm2.5-350m",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": q},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "decoded_request",
                "strict": True,
                "schema": schema,
            },
        },
    }
    req = urllib.request.Request(
        "http://127.0.0.1:1234/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        content = res["choices"][0]["message"]["content"]
        print(f"=== Query: {q} ===")
        print(content)
