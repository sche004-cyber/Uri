exec(open("n6_perf.py").read().split("size = st.segment_path")[0])
import time
for i in range(3):
    t=time.perf_counter(); p=m.projection(); views.status_json(p, None); a=time.perf_counter()-t
    t=time.perf_counter(); p=m.projection(); views.status_lines(p, True, None, None); b=time.perf_counter()-t
    print("in-process status_json s", round(a,3), "status_lines s", round(b,3))
import subprocess, sys
for i in range(3):
    t=time.perf_counter(); r=subprocess.run([sys.executable,"-m","scripts.dev_workflow.milestones","--home",str(m.home),"status","--no-tasks"],cwd="D:/uri-dev/uri-milestone-manager",capture_output=True); print("CLI status rc",r.returncode,"wall",round(time.perf_counter()-t,3))
t=time.perf_counter(); r=subprocess.run([sys.executable,"-c","pass"],capture_output=True); print("bare python start", round(time.perf_counter()-t,3))
