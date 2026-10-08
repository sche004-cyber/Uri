import json
import urllib.request

schema = {
    "type": "object",
    "properties": {
        "goal": {"type": "string", "description": "User intended outcome"},
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

sys_prompt = """You are the Step-1 Semantic Decoder for URIv1.
Extract the user's semantic intent into the exact JSON schema.
Field definitions:
- goal: concise phrase of the user's objective (e.g. 'Convert document to PDF', 'Draft an email'). Never write message bodies or drafts.
- intent_family: intent category from enum.
- requested_operations: base verbs user wants performed (e.g. ['convert'], ['draft']).
- prohibited_operations: base verbs explicitly forbidden or negated (e.g. ['send'] for "Don't send").
- operation_bindings: list of {operation, target_id} linking each operation to its target artifact/entity ID if known.
- references: list of {expression, target_id} for referring expressions (e.g. 'it', 'this', 'that file'). Leave target_id empty if unresolved.
- temporal_references: list of time words (e.g. ['yesterday', 'tomorrow']).
- constraints: included_items, excluded_items, length_limit, language_constraints.
- output_preferences: artifact_type, format, tone, structure.
- ambiguities: list of {kind, description, candidates} if request is ambiguous.
- context_dependencies: list of {category, description} if external/prior context is required.
Never invent references or IDs not provided in context. Correctly distinguish requested vs prohibited actions."""

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
