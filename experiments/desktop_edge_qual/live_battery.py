import json,os,sys,time,urllib.request
S=os.environ["URI_TEST_ACCOUNT_DIR"]; R=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
a=json.load(open(os.path.join(S,"test_account.json"))); uid=a["user_id"]
usage=os.path.join(R,"uri_workspace/users",uid,"usage/2026-10.jsonl"); timing=os.path.join(R,"uri_workspace/logs/desktop_request_timing.jsonl")
def lines(p):
    try: return open(p,encoding="utf-8").read().splitlines()
    except FileNotFoundError: return []
def unload(m):
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate",data=json.dumps({"model":m,"keep_alive":0}).encode(),headers={"Content-Type":"application/json"}),timeout=60).read()
def ask(text,sid):
    nu,nt=len(lines(usage)),len(lines(timing))
    t=time.time()
    r=urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/ask",data=json.dumps({"session_id":sid,"text":text}).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+a["token"]}),timeout=600)
    d=json.loads(r.read()); total=time.time()-t
    calls=[json.loads(l) for l in lines(usage)[nu:]]; tim=[json.loads(l) for l in lines(timing)[nt:]]
    return {"text":text,"client_total_s":round(total,2),"backend_last_byte_s":round(tim[-1]["last_byte_ms"]/1000,2) if tim else None,
      "model_calls":[(c["role"],c["model"],c["prompt_tokens"]["value"],c["eval_tokens"]["value"],round(c["duration_seconds"]["value"],2)) for c in calls],
      "model_sum_s":round(sum(c["duration_seconds"]["value"] for c in calls),2),
      "ui_shown":(d.get("serving_model"),d.get("serving_prompt_tokens"),round(d.get("serving_duration_seconds") or 0,2)),
      "reply":((d.get("narrative") or (d.get("response") or {}).get("message") or "")[:120]).replace("\n"," "),
      "narrative_ok":d.get("narrative") is not None,
      "route":(d.get("harness_route") or {}).get("class"),"edge_src":(d.get("harness_route") or {}).get("reply_source"),
      "resp_calls":d.get("serving_call_count"),"turn_s":d.get("turn_duration_seconds"),"status":d.get("status"),"exec":(d.get("execution") or {}).get("capability")}
if __name__=="__main__":
    out=[]
    if "--cold" in sys.argv:
        for m in ("qwen3.5:9b","qwen3:0.6b"): unload(m)
    texts=sys.argv[3].split("|") if len(sys.argv)>3 else ["hi","hello","thanks","what can you do?","what is 17 times 23?","hi"]
    for i,t in enumerate(texts):
        r=ask(t,"cc-batt-"+sys.argv[1]); r["run"]=sys.argv[1]; out.append(r); print(json.dumps(r,ensure_ascii=False))
    json.dump(out,open(os.path.join(S,"battery_"+sys.argv[1]+".json"),"w"),indent=1)
