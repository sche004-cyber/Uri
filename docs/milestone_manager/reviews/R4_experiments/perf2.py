import time, statistics, subprocess, sys
exec(open("n6b.py").read().split("size = st.segment_path")[0])
print("events file MB", round(st.segment_path.stat().st_size/1e6,2))
rb=[];sj=[];sl=[]
for i in range(5):
    t=time.perf_counter(); p=m.projection(); rb.append(time.perf_counter()-t)
    t=time.perf_counter(); p=m.projection(); views.status_json(p,None); sj.append(time.perf_counter()-t)
    t=time.perf_counter(); p=m.projection(); views.status_lines(p,True,None,None); sl.append(time.perf_counter()-t)
print("conflicts", len(p["conflicts"]), "events", p["events"])
print("in-process median rebuild", round(statistics.median(rb),3), "status_json", round(statistics.median(sj),3), "status_lines", round(statistics.median(sl),3))
for cmd in (["status","--no-tasks"],["status","--json","--no-tasks"],["rebuild"]):
    ws=[]
    for i in range(3):
        t=time.perf_counter(); r=subprocess.run([sys.executable,"-m","scripts.dev_workflow.milestones","--home",str(m.home),*cmd],cwd="C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/7930d870-1417-469b-b31b-e46354e768c5/scratchpad/src",capture_output=True); ws.append(time.perf_counter()-t)
    print(cmd, "rc", r.returncode, "CLI wall median", round(statistics.median(ws),3), [round(x,3) for x in ws])
