from common import *
m = new()
m.create_milestone("MM-A","A")
m.update_milestone("MM-A", candidate_commit=C1)
c = json.loads(m.cache_path.read_text())
c["state"]["reviews"]["RV-99"] = {"id":"RV-99","subject":"MM-A","commit":C1,"reviewer":{"kind":"subagent","id":"ghost"},
  "assurance":"SUBAGENT","verdict":"ACCEPT","blocking_open":0,"findings_total":0,"result_class":"COMPLETED_WITH_RESULT",
  "summary":"forged","evidence":[],"recorded":{"seg":"h1","seq":99,"hash":"x","ts":"2026-01-01T00:00:00.000000Z","actor":"x"}}
m.cache_path.write_text(json.dumps(c))
m.set_status("MM-A","ACCEPTED","forged via cache")
print("verify ok:", m.store.verify()["ok"])
p = m.rebuild()
print("after rebuild status:", p["milestones"]["MM-A"]["status"], "basis:", p["milestones"]["MM-A"]["status_history"][-1]["basis"], "reviews in log:", list(p["reviews"]))
