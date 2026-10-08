import urllib.request
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from uri_v1.turn.lfm_adaptive_feeds import (
    FEED_G_SCHEMA,
    FEED_G_SYSTEM_PROMPT,
    FEED_O_SCHEMA,
    FEED_O_SYSTEM_PROMPT,
    FEED_C_SCHEMA,
    FEED_C_SYSTEM_PROMPT,
    FEED_B_SCHEMA,
    FEED_B_SYSTEM_PROMPT,
    build_feed_g_prompt,
    build_feed_o_prompt,
    build_feed_c_prompt,
    build_feed_b_prompt,
    parse_feed_g_response,
    parse_feed_o_response,
    parse_feed_c_response,
    parse_feed_b_response,
)

turn_text = "Run tests on module A and lint module B, but do not push or commit to main."

def call_feed(sys_p, user_p, schema, name):
    prompt = (
        f"<|im_start|>system\n{sys_p}<|im_end|>\n"
        f"<|im_start|>user\n{user_p}<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n</think>\n"
    )
    payload = {
        "model": "qwen3.5-2b",
        "prompt": prompt,
        "temperature": 0.0,
        "max_tokens": 300,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": schema}
        }
    }
    t0 = time.perf_counter()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:1234/v1/completions", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    lat = (time.perf_counter() - t0) * 1000
    text = res["choices"][0]["text"]
    parsed = json.loads(text)
    return lat, parsed

print("Turn:", turn_text)

# Feed G
lat_g, res_g = call_feed(FEED_G_SYSTEM_PROMPT, build_feed_g_prompt(turn_text), FEED_G_SCHEMA, "feed_g")
print(f"\nFeed G ({lat_g:.1f}ms):", res_g)

# Feed O
lat_o, res_o = call_feed(FEED_O_SYSTEM_PROMPT, build_feed_o_prompt(turn_text), FEED_O_SCHEMA, "feed_o")
print(f"\nFeed O ({lat_o:.1f}ms):", res_o)

# Feed C
lat_c, res_c = call_feed(FEED_C_SYSTEM_PROMPT, build_feed_c_prompt(turn_text), FEED_C_SCHEMA, "feed_c")
print(f"\nFeed C ({lat_c:.1f}ms):", res_c)
