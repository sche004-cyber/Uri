import json
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uri_v1.turn.contracts import IntentFamily

schema = {
    "type": "object",
    "properties": {
        "goal": {"type": "string", "description": "Concise phrase stating user primary intended outcome."},
        "intent_family": {
            "type": "string",
            "enum": [f.value for f in IntentFamily],
            "description": "Category of user intent.",
        },
        "requested_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Operations or actions requested by user.",
        },
        "prohibited_operations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Operations or actions explicitly prohibited or negated (e.g. 'do not send').",
        },
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Referring expression (e.g. 'it', 'that file', 'same thing')."},
                    "target_id": {"type": "string", "description": "Matching target ID (e.g. 'x1', 'e1') from active context if present, else empty string."},
                },
                "required": ["expression", "target_id"],
                "additionalProperties": False,
            },
            "description": "Referring expressions.",
        },
        "temporal_references": {
            "type": "array",
            "items": {"type": "string"},
        },
        "constraints": {
            "type": "object",
            "properties": {
                "included_items": {"type": "array", "items": {"type": "string"}},
                "excluded_items": {"type": "array", "items": {"type": "string"}},
                "length_limit": {"type": "string"},
                "language_constraints": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "output_preferences": {
            "type": "object",
            "properties": {
                "artifact_type": {"type": "string"},
                "tone": {"type": "string"},
                "audience": {"type": "string"},
                "language": {"type": "string"},
                "language_variant": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["goal", "intent_family", "requested_operations", "prohibited_operations", "references"],
    "additionalProperties": False,
}

test_prompts = [
    # Test 1: Mode A Raw on R4
    ("R4_ModeA", "Don't send it. Just draft the email."),
    # Test 2: Mode B on R4
    ("R4_ModeB", "User message: Don't send it. Just draft the email.\n\nPre-semantic surface cues:\n- Clauses: [\"Don't send it\", \"Just draft the email\"]\n- Negation cues: [\"don't\"]\n- Candidate action verbs: [\"send\", \"draft\"]\n- Candidate referring expressions: [\"it\"]"),
    # Test 3: Mode C on C1
    ("C1_ModeC", "User message: Bring that file up.\n\nPre-semantic surface cues:\n- Candidate referring expressions: [\"that file\"]\n\nActive session working context:\n- Active artifacts: [('x1', 'Hostel_Order_21Sep.docx')]"),
]

for name, p in test_prompts:
    payload = {
        'model': 'qwen3-14b',
        'messages': [
            {'role': 'system', 'content': 'You are URI Step-1 Semantic Decoder. Extract goal, operations, references, and constraints into JSON matching the schema. If an active context target matches a reference, set target_id to that ID, else leave target_id empty.'},
            {'role': 'user', 'content': p}
        ],
        'temperature': 0.0,
        'max_tokens': 600,
        'response_format': {
            'type': 'json_schema',
            'json_schema': {
                'name': 'decoded_request',
                'schema': schema
            }
        }
    }
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:1234/v1/chat/completions', data=body, headers={'Content-Type': 'application/json'})
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    elapsed = time.perf_counter() - start
    print(f'=== {name} in {elapsed:.2f}s ===')
    content = data['choices'][0]['message'].get('content')
    print('Content:', content)
    usage = data.get('usage', {})
    print('Reasoning tokens:', usage.get('completion_tokens_details', {}).get('reasoning_tokens'), 'Total tokens:', usage.get('completion_tokens'))
