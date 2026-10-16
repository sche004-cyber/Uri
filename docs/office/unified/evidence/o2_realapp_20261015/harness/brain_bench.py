"""Timed Brain decode (B5: Brain speed with and without Office), same fixed prompt and length as the WS Brain host's
calibration (160 tokens, temperature 0, no thinking). Three decodes; records predicted tokens/s and wall time.

    python -B harness\\brain_bench.py <run-name> <tag> <brain-url>

Appends to evidence/live/<run>/brain_bench.json.
"""
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN, TAG, URL = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, str(ROOT / "candidate"))
from uri_operational_intelligence import brain_client as BC  # noqa: E402
from scripts.ws_brain_host import CALIBRATION_PROMPT, CALIBRATION_TOKENS  # noqa: E402

client = BC.BrainClient(URL)
rows = []
for i in range(3):
    body = {"model": "local", "messages": [{"role": "user", "content": CALIBRATION_PROMPT}], "temperature": 0.0,
            "max_tokens": CALIBRATION_TOKENS, "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.perf_counter()
    r = client.stream_chat(body, cancel=BC.CancelToken(), deadlines=BC.Deadlines(first_token_s=60, idle_s=30, total_s=120))
    rows.append(dict(i=i, status=r.status, wall_s=round(time.perf_counter() - t0, 2), ttft_s=r.ttft_s,
                     predicted_per_second=(r.timings or {}).get("predicted_per_second"),
                     predicted_n=(r.timings or {}).get("predicted_n")))
p = ROOT / f"evidence/live/{RUN}/brain_bench.json"
data = json.loads(p.read_text()) if p.exists() else []
data.append({"tag": TAG, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": rows})
p.write_text(json.dumps(data, indent=1))
print(json.dumps(data[-1]))
