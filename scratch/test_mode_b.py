import json
import urllib.request
from scratch.test_lfm_prompt2 import schema, sys_prompt

# Test Mode B with TurnFrame + RAR anchors
user_msg_mode_b = """[User Message]
Don't send it. Just draft the email.

[TurnFrame]
- Candidate action verbs: draft, send
- Negation spans: Don't send it
- Referring expressions: it

[Deterministic RAR Anchors]
- resolved_anchors:
  'it' -> x1 (Hostel_Order_21Sep.docx)
- unresolved: none
- ambiguous: none"""

payload = {
    "model": "lfm2.5-350m",
    "messages": [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg_mode_b},
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
    print("=== Mode B with TurnFrame + RAR ===")
    print(content)
