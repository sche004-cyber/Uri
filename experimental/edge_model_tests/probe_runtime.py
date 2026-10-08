"""Validation of Qwen3.5-0.8B raw mode JSON generation."""
import json
import time
import httpx

def test_json_extraction():
    url = "http://127.0.0.1:11434/api/generate"
    prompt = (
        "<|im_start|>system\n"
        "You are a strict JSON extractor. Respond ONLY with a valid JSON object matching this schema:\n"
        "{\"intent\": string, \"entity\": string}\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        "Send sales report to Alice\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
        "<think>\n</think>\n"
    )
    payload = {
        "model": "qwen3.5:0.8b",
        "prompt": prompt,
        "format": "json",
        "raw": True,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 100
        }
    }
    t0 = time.perf_counter()
    res = httpx.post(url, json=payload, timeout=30.0)
    dur = (time.perf_counter() - t0) * 1000
    data = res.json()
    print("JSON Extraction:")
    print("  Status code:", res.status_code)
    print("  Duration ms:", round(dur, 1))
    print("  Raw response:", repr(data.get("response")))
    try:
        parsed = json.loads(data.get("response", ""))
        print("  Parsed JSON:", parsed)
    except Exception as e:
        print("  JSON Parse Error:", e)
    print("  Prompt tokens:", data.get("prompt_eval_count"))
    print("  Eval tokens:", data.get("eval_count"))
    print("  Eval duration ms:", round(data.get("eval_duration", 0) / 1e6, 1))

if __name__ == "__main__":
    test_json_extraction()
