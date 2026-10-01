"""Judge pass for edge_chat_trial runs (run after generation, so judging never contends with timing).

Judge: local qwen3.5:9b, temperature 0, scoring 1-5 against a fixed rubric that also checks the reply
fits the social intent (a farewell answered with a greeting scores <=2). Disclosed limitation: the judge
is a model, not a person, and is the same family as one candidate.
Usage: python edge_chat_judge.py runs/edge_chat_r2.jsonl --out runs/edge_chat_r2_judged.jsonl
"""
from __future__ import annotations

import argparse
import json
import urllib.request

RUBRIC = ("You grade a desktop assistant's reply to a user's short social message (greeting, thanks, goodbye, "
          "acknowledgement, or asking who the assistant is). Return JSON {\"score\": 1-5, \"fits_intent\": true/false, "
          "\"issue\": \"<short>\"}. 5 = natural, warm, fits the message, concise. 4 = good, slightly generic. "
          "3 = acceptable but stiff or a bit off. 2 = does not fit (e.g. answers a goodbye with a greeting), "
          "odd or overlong. 1 = wrong, rude, or claims to have done something.")


def judge(user, reply):
    body = {"model": "qwen3.5:9b", "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0, "seed": 1, "num_predict": 80, "num_ctx": 2048},
            "messages": [{"role": "system", "content": RUBRIC}, {"role": "user", "content": f"User: {user}\nAssistant: {reply}"}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        o = json.loads(json.loads(r.read())["message"]["content"])
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cache = {}
    with open(a.out, "w", encoding="utf-8") as fh:
        for line in open(a.run, encoding="utf-8"):
            o = json.loads(line)
            if o.get("type") == "turn":
                key = (o["user"], o["reply"])
                if key not in cache:
                    try:
                        cache[key] = judge(*key)
                    except Exception as exc:
                        cache[key] = {"error": type(exc).__name__}
                o["judge"] = cache[key]
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
