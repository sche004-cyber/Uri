from common import *
import shutil, time
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
Manager(B,actor="impl:b").update_milestone("MM-X", next_action="b")
time.sleep(0.05); ma.update_milestone("MM-X", title="a2")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
ids = sorted({r["id"] for r in views.conflict_rows(Manager(A).projection())}); ma.resolve_conflict("MM-X","ok",ids)
print("open now", len(views.conflict_rows(Manager(A).projection())))
model.CONFLICT_DETAIL_KEYS = model.CONFLICT_DETAIL_KEYS + ("note_added_later",)   # a later code version lists one more key
print("open after a later code version adds one key to CONFLICT_DETAIL_KEYS:", [(r["id"], r["type"]) for r in views.conflict_rows(Manager(A).projection())])
