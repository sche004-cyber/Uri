import httpx
import json
import time

user_content = 'Task: Calculate total revenue for Q3 from revenue.csv\nInstruction: Extract target filename from request.\nSchema: {"decision": "LOCAL", "intent": "CALCULATE", "target": "<filename>"}\nReturn ONLY valid JSON.'
system_content = "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."

full_prompt = (
    f"<|im_start|>system\n{system_content}<|im_end|>\n"
    f"<|im_start|>user\n{user_content}<|im_end|>\n"
    f"<|im_start|>assistant\n"
)

payload = {
    "model": "smollm2:360m",
    "prompt": full_prompt,
    "format": "json",
    "raw": True,
    "stream": False,
    "options": {
        "temperature": 0.0,
        "num_predict": 150
    }
}

t0 = time.perf_counter()
res = httpx.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=20.0)
dur = (time.perf_counter() - t0) * 1000
data = res.json()
print("Status code:", res.status_code)
print(f"Latency: {dur:.1f}ms")
print("Response:", repr(data.get("response")))
