"""C1 Brain subset (plan §12 row C1): the 16 ambiguous requests of tests/office_u2/intent_corpus.json through the LIVE
Office service the app started in this run, with the real Runtime v1 Brain. Integration evidence (HTTP), not UI.

    python -B harness\\brain_corpus.py <run-name>

Reads the service address and token from the run's Office state folder (fixtures/<run>/local/URI/office). Records per
item: stage, result, intent, expected, seconds; and the Brain's tokens/s from the Brain host report before and after.
Writes evidence/live/<run>/brain_corpus.json.
"""
import json, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN = sys.argv[1]
state = ROOT / f"fixtures/{RUN}/local/URI/office"
svc = json.loads((state / "service.json").read_text(encoding="utf-8"))
token = (state / "api-token").read_text(encoding="utf-8").strip()
corpus = json.loads((ROOT / "candidate/tests/office_u2/intent_corpus.json").read_text(encoding="utf-8"))


def post(path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{svc['port']}{path}", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


rows = []
for item in corpus["ambiguous"]:
    t0 = time.perf_counter()
    body = {"text": item["text"], "history": []}
    if item.get("target"):
        body["target"] = {"kind": item["target"]}
    try:
        got = post("/request", body)
        err = None
    except Exception as e:  # noqa: BLE001
        got, err = {}, repr(e)
    secs = round(time.perf_counter() - t0, 2)
    intent = got.get("intent")
    exp = item["brain_expected"]
    agree = (intent == exp) if exp != "unclear" else (got.get("result") == "clarify")
    rows.append(dict(text=item["text"], target=item.get("target"), expected=exp, result=got.get("result"),
                     intent=intent, stage=got.get("stage"), seconds=secs, agrees=agree, error=err,
                     message=got.get("message") or got.get("question"), brain_outcome=got.get("brain_outcome")))
    print(json.dumps(rows[-1]), flush=True)
out = dict(run=RUN, items=rows, agree=sum(r["agrees"] for r in rows), total=len(rows),
           brain_calls=sum(1 for r in rows if r["stage"] == 2), median_s=sorted(r["seconds"] for r in rows)[len(rows) // 2],
           note="agreement with the corpus expectation is recorded, not used to change the expectation")
(ROOT / f"evidence/live/{RUN}/brain_corpus.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("agree", "total", "brain_calls", "median_s")}))
