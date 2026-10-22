"""FB4 e16: concurrency stress - W writer processes x N writes + R reader processes; then verify chain/count."""
import sys, os, time, json, multiprocessing as mp
SRC, HOME = sys.argv[1], sys.argv[2]
sys.path.insert(0, SRC)
W, N, R = 4, 120, 3
def writer(i):
    from scripts.dev_workflow.milestones.service import Manager
    m = Manager(HOME, actor=f"w:{i}", session=f"s{i}"); errs = 0
    for k in range(N):
        try: m.record_handoff("MM-A", f"writer {i} note {k}")
        except Exception as e: errs += 1; print("WERR", i, k, type(e).__name__, str(e)[:120], flush=True)
    return errs
def reader(i, stop):
    from scripts.dev_workflow.milestones.service import Manager
    m = Manager(HOME, actor=f"r:{i}"); reads = alarms = 0
    while not stop.is_set():
        try:
            p = m.projection(); reads += 1
            if p["integrity_errors"]: alarms += 1; print("RALARM", p["integrity_errors"][:1], flush=True)
        except Exception as e: alarms += 1; print("RERR", type(e).__name__, str(e)[:120], flush=True)
    return reads, alarms
if __name__ == "__main__":
    from scripts.dev_workflow.milestones.store import EventStore
    from scripts.dev_workflow.milestones.service import Manager
    EventStore.init(HOME, "h1"); Manager(HOME, actor="setup").create_milestone("MM-A", "A")
    mgr = mp.Manager(); stop = mgr.Event(); t0 = time.time()
    with mp.Pool(W + R) as pool:
        rs = [pool.apply_async(reader, (i, stop)) for i in range(R)]
        ws = [pool.apply_async(writer, (i,)) for i in range(W)]
        werr = sum(w.get(timeout=900) for w in ws); stop.set()
        rres = [r.get(timeout=120) for r in rs]
    v = EventStore(HOME).verify()
    print(json.dumps({"seconds": round(time.time() - t0, 1), "writer_errors": werr, "events": v["events"],
                      "expected": 1 + W * N, "verify_ok": v["ok"], "errors": v["errors"][:2],
                      "reads": sum(r[0] for r in rres), "reader_alarms": sum(r[1] for r in rres)}))
