import urllib.request
import json

def test_chat(messages, extra=None):
    payload = {
        "model": "qwen3.5-2b",
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 100,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "greeting",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"greeting": {"type": "string"}},
                    "required": ["greeting"],
                    "additionalProperties": False
                }
            }
        }
    }
    if extra:
        payload.update(extra)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            msg = res["choices"][0]["message"]
            print(f"Content: {repr(msg.get('content'))} | Reasoning: {len(msg.get('reasoning_content') or '')}")
    except Exception as e:
        print("Error:", e)

print("Test 1: Normal system + user")
test_chat([
    {"role": "system", "content": "You are a test helper."},
    {"role": "user", "content": "Say hello."}
])

print("Test 2: Assistant prefix with empty think")
test_chat([
    {"role": "system", "content": "You are a test helper."},
    {"role": "user", "content": "Say hello."},
    {"role": "assistant", "content": "<think>\n</think>\n", "prefix": True}
])

print("Test 3: Assistant message without prefix")
test_chat([
    {"role": "system", "content": "You are a test helper."},
    {"role": "user", "content": "Say hello."},
    {"role": "assistant", "content": "<think>\n</think>"}
])
