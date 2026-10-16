"""Direct probe of the Office Stage-2 classifier against the live Runtime v1 Brain (diagnosis for run r4, where every
ambiguous request became a clarification with no Stage-2 result).

    python -B harness\\classify_probe.py <run-name> <brain-url>

Calls uri_office.brain.OfficeBrain.classify from the candidate source with three corpus requests and records, per
call: the BrainClient status, the raw text, the parsed result, and any exception. Writes
evidence/live/<run>/classify_probe.json.
"""
import json, pathlib, sys, time, traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN, URL = sys.argv[1], sys.argv[2]
sys.path.insert(0, str(ROOT / "candidate"))
from uri_operational_intelligence import brain_client as BC  # noqa: E402
from uri_office import brain as B  # noqa: E402
from uri_office.intent import INTENTS  # noqa: E402

client = BC.BrainClient(URL)
ob = B.OfficeBrain(client)
rows = []
for text, kind in (("I need it in a format I can email", "docx"), ("make this ready to share", "pptx"),
                   ("what is this about", "pdf")):
    body = B.classify_body(text, kind, [], INTENTS)
    t0 = time.perf_counter()
    raw = client.stream_chat(body, cancel=BC.CancelToken(), deadlines=B.TIMEOUT)
    row = dict(text=text, kind=kind, status=raw.status, raw_text=(raw.text or "")[:600],
               error=getattr(raw, "error", None), http_status=getattr(raw, "http_status", None), seconds=round(time.perf_counter() - t0, 2))
    try:
        row["classify"] = ob.classify(text, target_kind=kind)
    except Exception as e:  # noqa: BLE001
        row["classify_error"] = f"{type(e).__name__}: {e}"
        row["trace"] = traceback.format_exc()[-800:]
    rows.append(row)
    print(json.dumps(row)[:700], flush=True)
(ROOT / f"evidence/live/{RUN}/classify_probe.json").write_text(json.dumps(rows, indent=1, default=str))
