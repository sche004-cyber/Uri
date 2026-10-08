import urllib.request
import json
import time

prompt = (
    "<|im_start|>system\n"
    "You are an intent extractor for URIv1. Reply in JSON.\n"
    "<|im_end|>\n"
    "<|im_start|>user\n"
    "Convert this to PDF.\n"
    "<|im_end|>\n"
    "<|im_start|>assistant\n"
    "<think>\n"
    "</think>\n"
)

payload = {
    "model": "qwen3.5-2b",
    "prompt": prompt,
    "temperature": 0.0,
    "max_tokens": 200,
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "res",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "requested_operations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["goal", "requested_operations"],
                "additionalProperties": False
            }
        }
    }
}

t0 = time.perf_counter()
data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:1234/v1/completions", data=data, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode("utf-8"))
lat_ms = (time.perf_counter() - t0) * 1000

print(f"Latency: {lat_ms:.1f}ms")
print("Response text:", repr(res["choices"][0]["text"]))
print("Usage:", res.get("usage"))
