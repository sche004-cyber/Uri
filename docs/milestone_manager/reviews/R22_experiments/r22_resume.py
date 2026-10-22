from common import *
m=new(); m.create_milestone("MM-1","x", objective="o"*3000)
for i in range(10): m.record_handoff("MM-1","s"*1900)
p=m.projection()
for mx in (10, 40, 59, 60, 61, 0, -5):
    t=views.resume_brief(p,"MM-1",None,mx,False); print(mx, len(t))
