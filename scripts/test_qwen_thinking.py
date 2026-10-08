import urllib.request
import json

def test_sys(sys_msg, extra_body=None):
    payload = {
        "model": "qwen3.5-2b",
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": "Respond with greeting hello."}
        ],
        "temperature": 0.0,
        "max_tokens": 600,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "res",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                    "additionalProperties": False
                }
            }
        }
    }
    if extra_body:
        payload.update(extra_body)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        msg = res["choices"][0]["message"]
        c = msg.get("content")
        r = msg.get("reasoning_content") or ""
        finish = res["choices"][0].get("finish_reason")
        print(f"Sys: {sys_msg[:40]:<40} | finish: {finish} | content: {repr(c)} | reasoning_len: {len(r)}")

if __name__ == "__main__":
    print("Testing prompt variants:")
    test_sys("Reply in JSON.")
    test_sys("Do not think. Immediately output JSON.")
    test_sys("/think off\nReply in JSON.")
