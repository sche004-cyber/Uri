from common import *
import time, subprocess, sys
SRC = 'C:/Users/cheta/AppData/Local/Temp/r6rev_b148t_ld/src'
m = new()
st = m.store
with st.locked():
    for i in range(500):
        st.append("MILESTONE_CREATED", {"id": f"MM-{i}", "title": f"t{i}", "objective": "o" * 200, "status": "PLANNED",
                                        "phase": "RESEARCH", "depends_on": []}, actor="a", base={f"MM-{i}": 0})
    k = 500
    while k < 10000:
        i = k % 500
        if k % 3 == 0:
            st.append("REVIEW_RECORDED", {"id": f"RV-{k}", "subject": f"MM-{i}", "commit": C1,
                                          "reviewer": {"kind": "subagent", "id": "r"}, "assurance": "SUBAGENT",
                                          "verdict": "REVISE", "blocking_open": 1, "findings_total": 1,
                                          "result_class": "COMPLETED_WITH_RESULT", "summary": "s" * 300,
                                          "evidence": []}, actor="a")
        elif k % 3 == 1:
            st.append("MILESTONE_UPDATED", {"id": f"MM-{i}", "fields": {"next_action": "n" * 200}}, actor="a",
                      base={f"MM-{i}": 0})
        else:
            st.append("DECISION_RECORDED", {"id": f"DEC-{k:05d}", "title": "t", "decision": "d" * 300, "date": "2026",
                                            "evidence_class": "OTHER", "source": {"text": "x"}}, actor="a")
        k += 1
    st.write_anchors(st.read_all())
size = st.segment_path.stat().st_size
for _ in range(3):
    t = time.perf_counter(); p = m.projection(); t1 = time.perf_counter() - t
    t = time.perf_counter(); views.status_json(p); views.status_lines(p); t2 = time.perf_counter() - t
    print("events", p["events"], "MB", round(size / 1e6, 2), "rebuild s", round(t1, 3), "status views s", round(t2, 3),
          "conflicts", len(p["conflicts"]))
for cmd in (["status", "--no-tasks"], ["status", "--json", "--no-tasks"], ["status"], ["rebuild"]):
    for _ in range(2):
        t = time.perf_counter()
        r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", str(m.home), *cmd],
                           cwd=SRC, capture_output=True)
        print(cmd, "rc", r.returncode, "wall s", round(time.perf_counter() - t, 3))
t = time.perf_counter(); m.create_milestone("MM-NEW", "n"); print("one write at 10k events s", round(time.perf_counter() - t, 3))
