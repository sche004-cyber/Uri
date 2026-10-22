from common import *
import shutil
res = {}
def scenario(anchored):
    m = new(actor="impl:a")
    if anchored: m.create_milestone("MM-P","pre")   # anchored first write
    seg = m.store.segment_path; start = seg.stat().st_size if seg.exists() else 0
    with m.store.locked():
        m.store.append_many([("MILESTONE_CREATED", {"id": f"MM-B{i}", "title": "b", "status": "PLANNED", "phase": "RESEARCH", "depends_on": []}, {}) for i in range(3)], actor="impl:a")
    full = seg.read_bytes()
    return m.home, start, full
out = {}
for anchored in (True, False):
    home0, start, full = scenario(anchored)
    stats = {"reads_err": 0, "recover_fail": 0, "loss": 0, "noloss": 0, "verify_after_bad": 0, "partial_applied": 0}
    step = 7
    for cut in range(start + 1, len(full), step):
        home = Path(tempfile.mkdtemp())/"l"; shutil.copytree(home0, home)
        seg = home/"events/h1.jsonl"; seg.write_bytes(full[:cut])
        m = Manager(home, actor="impl:a")
        try:
            p = m.projection()
            if p["integrity_errors"]: stats["reads_err"] += 1
            if any(k.startswith("MM-B") for k in p["milestones"]): stats["partial_applied"] += 1
        except Exception as e: stats["reads_err"] += 1
        try:
            r = m.store.recover("impl:a")
            p = Manager(home).projection()
            n = len([c for c in p["conflicts"] if c["type"] == "ANCHOR_LOSS" and not c["resolved"]])
            stats["loss" if n else "noloss"] += 1
            if not m.store.verify()["ok"]: stats["verify_after_bad"] += 1
        except Exception as e:
            stats["recover_fail"] += 1; stats.setdefault("fail_codes", set()).add(getattr(e, "code", type(e).__name__))
    print("anchored" if anchored else "unanchored", "cuts", len(range(start+1, len(full), step)), stats)
