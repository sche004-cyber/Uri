from common import *
d = Path(tempfile.mkdtemp())/"decisions.md"
hdr = "| ID | Date | Title | Decision | Reasoning | Alt | Corrections | Scope | Approval | Related | Applicability | Sources | Evidence |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
r1 = "| DEC-001 | 2026-10-01 | one | do x | r | a | Superseded by DEC-002 after password: hunter2abc9 leaked | s | ap | — | SUPERSEDED | src | REPO-RECORD |\n"
r2 = "| DEC-002 | 2026-10-02 | two | do y | r | a | — | s | ap | — | ACTIVE | src | REPO-RECORD |\n"
d.write_text(hdr+r1+r2, encoding="utf-8")
m = new()
try:
    rep = importers.import_decisions(m, d); print("report", rep)
except ValidationError as e: print("WHOLE IMPORT REFUSED:", e)
print("decisions in ledger:", list(m.projection()["decisions"]))
