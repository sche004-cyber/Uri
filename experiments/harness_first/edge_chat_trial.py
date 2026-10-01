"""Edge conversational specialist trial: which local model gives natural social replies fast enough?

For each candidate (<=1B unless marked as the Main Brain baseline): one warm-up call, then every
social turn x REPEATS through uri_core.core.harness_first.edge_chat.generate (the same code the app
seam uses), recording latency, validation result and the reply. A local judge (qwen3.5:9b, disclosed;
not independent) scores each accepted reply 1-5 for appropriateness and naturalness.

Usage: python edge_chat_trial.py --out runs/edge_chat_r1.jsonl [--models a,b] [--repeats 2] [--no-judge]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from uri_core.core.harness_first.edge_chat import generate  # noqa: E402
from uri_core.core.harness_first.social import social_intent  # noqa: E402

MODELS = ["qwen3:0.6b", "gemma3:270m", "granite4:350m-h", "smollm2:360m", "qwen3.5:0.8b", "qwen3.5:9b"]
EXTRA = ["helo", "hii URI", "good morning! how's it going?", "thanks so much, that helped", "ok cool",
         "namaste URI", "thank you, bye", "see you tomorrow", "nice to meet you", "hey, you there?",
         "great thanks", "good night URI", "what's your name?", "alright, got it"]
JUDGE = ("Rate the assistant's reply to a user's short social message. Return JSON "
         '{"score": 1-5, "issue": "<short>"}. 5 = natural, warm, fitting, concise; 3 = acceptable but stiff '
         "or slightly off; 1 = wrong, odd, rude, or claims to have done something.")


def judge(user, reply):
    body = {"model": "qwen3.5:9b", "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0, "seed": 1, "num_predict": 60},
            "messages": [{"role": "system", "content": JUDGE},
                         {"role": "user", "content": f"User: {user}\nAssistant: {reply}"}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(json.loads(r.read())["message"]["content"])
    return out.get("score"), out.get("issue")


def ps():
    with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=10) as r:
        return [(m["name"], m.get("size_vram"), m.get("size")) for m in json.loads(r.read()).get("models", [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--no-judge", action="store_true")
    a = ap.parse_args()
    corpus = json.loads((HERE / "corpus" / "hf_dev.json").read_text(encoding="utf-8"))
    turns = [c["text"] for c in corpus if c["expected"]["outcome"] == "REPLY"] + EXTRA
    with open(a.out, "a", encoding="utf-8") as fh:
        for m in a.models.split(","):
            t = time.perf_counter()
            w = generate("hello", "greeting", model=m, timeout_s=120)
            fh.write(json.dumps({"type": "warmup", "model": m, "ms": (time.perf_counter() - t) * 1000,
                                 "source": w.source, "reason": w.reject_reason, "resident": ps()}) + "\n")
            for rep in range(a.repeats):
                for u in turns:
                    intent = social_intent(u) or "greeting"
                    r = generate(u, intent, model=m, timeout_s=10)
                    rec = {"type": "turn", "model": m, "rep": rep, "user": u, "admitted": social_intent(u) is not None,
                           "intent": intent, "reply": r.text, "source": r.source, "reject": r.reject_reason,
                           "ms": r.latency_ms, "eval_count": r.eval_count, "prompt_chars": r.prompt_chars}
                    if not a.no_judge and r.source == "edge_model":
                        rec["judge_score"], rec["judge_issue"] = judge(u, r.text)
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
            fh.write(json.dumps({"type": "resident", "model": m, "resident": ps()}) + "\n")
            print(m, "done", flush=True)


if __name__ == "__main__":
    main()
