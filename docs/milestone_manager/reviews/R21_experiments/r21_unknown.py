from common import *
m=new(); m.create_milestone("MM-1","a"); m.store.anchors_path.unlink()
p=m.projection(); print("errs", p["integrity_errors"][:1])
info=m.store.reanchor("impl:a","anchors file lost","s",True); print("reanchor anchor_problems", info["anchor_problems"][:1], "unknown", info["unknown_previous"])
p=m.projection(); print("conflicts rows", [(r["type"], r["recorded_by"], r["detail"]) for r in views.conflict_rows(p)])
print("status issue", views.indicator(p,p["milestones"]["MM-1"])["issue"])
