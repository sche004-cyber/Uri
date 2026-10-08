import urllib.request
import json
import time
import concurrent.futures

prompt = (
    "<|im_start|>system\n"
    "Extract goal in JSON: {\"goal\": \"...\"}<|im_end|>\n"
    "<|im_start|>user\n"
    "Run tests.<|im_end|>\n"
    "<|im_start|>assistant\n"
    "<think>\n"
    "</think>\n"
)

schema = {
    "type": "object",
    "properties": {"goal": {"type": "string"}},
    "required": ["goal"],
    "additionalProperties": False
}

def call_one(idx):
    t0 = time.perf_counter()
    payload = {
        "model": "qwen3.5-2b",
        "prompt": prompt,
        "temperature": 0.0,
        "max_tokens": 100,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "res", "strict": True, "schema": schema}
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:1234/v1/completions", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        lat = (time.perf_counter() - t0) * 1000
        return idx, lat, res["choices"][0]["text"]

t_all = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(call_one, i) for i in range(4)]
    results = [f.result() for f in futs]
tot_lat = (time.perf_counter() - t_all) * 1000

print(f"4 parallel calls total wall clock: {tot_lat:.1f}ms")
for idx, lat, text in results:
    print(f"  Call {idx}: {lat:.1f}ms -> {text.strip()}")
