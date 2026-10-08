import json
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uri_v1.turn.qwen_wire import QWEN_WIRE_SCHEMA, QWEN_WIRE_SCHEMA_NAME

test_schema = dict(QWEN_WIRE_SCHEMA)
test_schema["required"] = ["goal", "intent_family", "requested_operations", "prohibited_operations", "references"]

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.turn_frame_builder import build_turn_frame

prompt = "Revise it to sound more formal and add Dean's approval note"
frame = build_turn_frame(prompt)
art = ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document")
ctx = ActiveContext(active_artifacts=(art,))

mode_c_prompt = f"""User message: {prompt}

Pre-semantic surface cues:
- Clauses: {list(frame.clauses)}
- Candidate action verbs: {[a.verb for a in frame.candidate_actions]}
- Candidate referring expressions: {[r.expression for r in frame.candidate_references]}

Active session working context:
- Active artifacts: {[(a.id, a.name) for a in ctx.active_artifacts]}"""

payload = {
    'model': 'qwen3-14b',
    'messages': [
        {'role': 'system', 'content': 'You are URI Step-1 Semantic Decoder. Output JSON matching the schema. If candidate references clearly refer to active artifacts, resolve them in references or prompt_supplied_context.'},
        {'role': 'user', 'content': mode_c_prompt}
    ],
    'temperature': 0.0,
    'max_tokens': 800,
    'response_format': {
        'type': 'json_schema',
        'json_schema': {
            'name': QWEN_WIRE_SCHEMA_NAME,
            'schema': test_schema
        }
    }
}
body = json.dumps(payload).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:1234/v1/chat/completions', data=body, headers={'Content-Type': 'application/json'})
start = time.perf_counter()
with urllib.request.urlopen(req, timeout=120) as resp:
    data = json.loads(resp.read().decode('utf-8'))
elapsed = time.perf_counter() - start
print(f'Completed in {elapsed:.2f}s:')
choice = data['choices'][0]['message']
print('Content:', choice.get('content'))
print('Reasoning tokens:', data.get('usage', {}).get('completion_tokens_details', {}).get('reasoning_tokens'))
print('Total completion tokens:', data.get('usage', {}).get('completion_tokens'))
