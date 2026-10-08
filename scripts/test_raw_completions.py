import urllib.request
import json

prompt = """<|im_start|>system
You are a helpful assistant. Reply in JSON: {"msg": "..."}<|im_end|>
<|im_start|>user
Say hello.<|im_end|>
<|im_start|>assistant
<think>
</think>
"""

payload = {
    "model": "qwen3.5-2b",
    "prompt": prompt,
    "temperature": 0.0,
    "max_tokens": 100,
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:1234/v1/completions", data=data, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("Completions response:", res["choices"][0]["text"])
except Exception as e:
    print("Error:", e)
