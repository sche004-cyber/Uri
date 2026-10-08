import httpx
import json
import time

user_content = 'Task: Calculate total revenue for Q3 from revenue.csv\nInstruction: Extract target filename from request.\nSchema: {"decision": "LOCAL", "intent": "CALCULATE", "target": "<filename>"}\nReturn ONLY valid JSON.'
system_content = "You are a tiny semantic worker. Output valid JSON only matching the schema. No explanations, no markdown."

# Test 1: /api/chat
payload_chat = {
    "model": "smollm2:360m",
    "messages": [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ],
    "format": "json",
    "stream": False,
    "options": {
        "temperature": 0.0,
        "num_predict": 150
    }
}

t0 = time.perf_counter()
res = httpx.post("http://127.0.0.1:11434/api/chat", json=payload_chat, timeout=20.0)
dur = (time.perf_counter() - t0) * 1000
print(f"Chat API Latency: {dur:.1f}ms")
print("Chat Response:", repr(res.json().get("message", {}).get("content")))

# Test 2: /api/generate without raw
payload_gen = {
    "model": "smollm2:360m",
    "system": system_content,
    "prompt": user_content,
    "format": "json",
    "stream": False,
    "options": {
        "temperature": 0.0,
        "num_predict": 150
    }
}
t0 = time.perf_counter()
res2 = httpx.post("http://127.0.0.1:11434/api/generate", json=payload_gen, timeout=20.0)
dur2 = (time.perf_counter() - t0) * 1000
print(f"Gen API Latency: {dur2:.1f}ms")
print("Gen Response:", repr(res2.json().get("response")))
