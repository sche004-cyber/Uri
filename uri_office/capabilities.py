"""Office capability registry (plan rev 3.1 §5, contract §3). A static table, no framework.

Each entry says what the capability does, which goal group shows it, which kinds it reads, its output, its steps
(D rule-based, E engine, B URI-written), the engines it needs, its status (`available` or `planned:<phase>`), the
approval it needs and its effects. The left pane builds goal groups from it (only `available` entries; empty groups
hidden, U4), intent routing maps phrases to its ids, and "planned" entries answer honestly "not available yet"
(AC-O2-11).

The descriptor shape (inputs, output, effects, approval) is transport-free so a later Brain registration can wrap it
without a redesign (owner OD-U12). Nothing here registers with Core.
"""
from __future__ import annotations

from . import contracts as K

GOALS = (
    {"id": "write", "title": "Write"},
    {"id": "present", "title": "Present"},
    {"id": "pdfs", "title": "PDFs"},
    {"id": "data", "title": "Data & Excel"},
    {"id": "combine", "title": "Combine files"},
)
PHASE_TITLES = {"O2P": "printing", "O3": "Word documents", "O4": "PDF reading", "O5": "presentations",
                "O7": "cross-file tasks", "deferred": "a later release"}


def _step(sid, kind, engine=None):
    return {"id": sid, "kind": kind, **({"engine": engine} if engine else {})}


_CAPS = (
    {"id": "open_document", "goal": None, "title": "Open a document", "inputs": ["docx", "pptx", "pdf"],
     "output": None, "steps": [_step("sanitize", "D"), _step("preview", "E", "libreoffice"),
                               _step("raster", "E", "winrt_pdf"), _step("outline", "D", "pdf_text")],
     "engines": ["libreoffice", "winrt_pdf", "pdf_text"], "status": "available", "approval": "none",
     "effects": ["reads_files"]},
    {"id": "view_pdf", "goal": "pdfs", "title": "Read a PDF", "inputs": ["pdf"], "output": None,
     "steps": [_step("raster", "E", "winrt_pdf"), _step("text", "D", "pdf_text")],
     "engines": ["winrt_pdf", "pdf_text"], "status": "available", "approval": "none", "effects": ["reads_files"]},
    {"id": "save_as_pdf", "goal": "pdfs", "title": "Make a PDF", "inputs": ["docx", "pptx", "xlsx"], "output": "pdf",
     "steps": [_step("sanitize", "D"), _step("convert", "E", "libreoffice"), _step("validate", "D", "pdf_text"),
               _step("preview", "E", "winrt_pdf")],
     "engines": ["libreoffice", "winrt_pdf", "pdf_text"], "status": "available", "approval": "plan_and_outputs",
     "effects": ["reads_files", "writes_new_file"]},
    {"id": "open_workbook", "goal": "data", "title": "Open a workbook", "inputs": ["xlsx"], "output": None,
     "steps": [_step("open", "D")], "engines": [], "status": "available", "approval": "none",
     "effects": ["reads_files"]},
    {"id": "new_workbook_from_files", "goal": "data", "title": "New workbook from files", "inputs": ["xlsx"],
     "output": "xlsx", "steps": [_step("plan", "B"), _step("build", "D")], "engines": [], "status": "available",
     "approval": "plan_and_outputs", "effects": ["reads_files", "writes_new_file", "uses_brain"]},
    # Planned: listed in help and answered honestly, never run.
    {"id": "print_document", "goal": "pdfs", "title": "Print", "inputs": ["docx", "pptx", "xlsx", "pdf"],
     "output": None, "steps": [_step("to_pdf", "E", "libreoffice"), _step("preview", "E", "winrt_pdf"),
                               _step("submit", "E", "print_worker")],
     "engines": ["libreoffice", "winrt_pdf", "print_worker"], "status": "planned:O2P", "approval": "print_job",
     "effects": ["reads_files", "sends_to_printer"]},
    # OD-2 (plan 16): available through POST /authoring/draft only (no workflow); the draft opens in the Word editor
    # and is written only through the Save as card.
    {"id": "write_document", "goal": "write", "title": "Write a letter or notice", "inputs": [], "output": "docx",
     "steps": [_step("layout", "D"), _step("draft", "B"), _step("facts", "D")], "engines": [],
     "status": "available", "approval": "plan_and_outputs", "effects": ["writes_new_file", "uses_brain"],
     "route": "/authoring/draft"},
    {"id": "edit_document", "goal": "write", "title": "Change a Word document", "inputs": ["docx"], "output": "docx",
     "steps": [], "engines": [], "status": "planned:O3", "approval": "plan_and_outputs",
     "effects": ["reads_files", "writes_new_file", "uses_brain"]},
    {"id": "ask_pdf", "goal": "pdfs", "title": "Ask about a PDF", "inputs": ["pdf"], "output": None, "steps": [],
     "engines": [], "status": "planned:O4", "approval": "none", "effects": ["reads_files", "uses_brain"]},
    {"id": "summarize_pdf", "goal": "pdfs", "title": "Summarize a PDF", "inputs": ["pdf"], "output": None,
     "steps": [], "engines": [], "status": "planned:O4", "approval": "none", "effects": ["reads_files", "uses_brain"]},
    {"id": "make_presentation", "goal": "present", "title": "Make a presentation", "inputs": [], "output": "pptx",
     "steps": [], "engines": [], "status": "planned:O5", "approval": "plan_and_outputs",
     "effects": ["writes_new_file", "uses_brain"]},
    {"id": "edit_presentation", "goal": "present", "title": "Change a presentation", "inputs": ["pptx"],
     "output": "pptx", "steps": [], "engines": [], "status": "planned:O5", "approval": "plan_and_outputs",
     "effects": ["reads_files", "writes_new_file", "uses_brain"]},
    {"id": "pdf_tables_to_excel", "goal": "data", "title": "PDF tables to Excel", "inputs": ["pdf"],
     "output": "xlsx", "steps": [], "engines": [], "status": "planned:deferred", "approval": "plan_and_outputs",
     "effects": ["reads_files", "writes_new_file"]},
    {"id": "combine_report", "goal": "combine", "title": "Report from several files",
     "inputs": ["docx", "xlsx", "pdf"], "output": "docx", "steps": [], "engines": [], "status": "planned:O7",
     "approval": "plan_and_outputs", "effects": ["reads_files", "writes_new_file", "uses_brain"]},
)

_READY_STATES = ("ready", "running", "idle_stopped")


def _check(c):
    assert c["status"] == "available" or c["status"].startswith("planned:")
    assert c["approval"] in K.APPROVALS and set(c["effects"]) <= set(K.EFFECTS)
    assert set(c["inputs"]) <= set(K.KINDS) and c["output"] in (None, *K.KINDS)
    assert all(s["kind"] in K.STEP_KINDS for s in c["steps"])
    assert c["goal"] in (None, *(g["id"] for g in GOALS))


for _c in _CAPS:
    _check(_c)
BY_ID = {c["id"]: c for c in _CAPS}
assert len(BY_ID) == len(_CAPS)


def get(cid: str) -> dict | None:
    return BY_ID.get(cid)


def phase_of(cid: str) -> str | None:
    c = BY_ID.get(cid)
    return c["status"].split(":", 1)[1] if c and c["status"].startswith("planned:") else None


def planned_message(cid: str) -> str:
    c = BY_ID[cid]
    ph = phase_of(cid)
    return f"{c['title']} is not available yet (planned for {PHASE_TITLES.get(ph, ph)})."


def registry(engine_states: dict | None = None, *, available_overrides: dict | None = None) -> dict:
    """`GET /capabilities`. `engine_states`: {engine id: (state, reason code)}; an engine missing from it counts as
    ready (workbook capabilities need none). `available_overrides` lets a qualified phase (O2P) flip its entries to
    available without editing this table; it is empty in O2."""
    engine_states = engine_states or {}
    out = []
    for c in _CAPS:
        status = (available_overrides or {}).get(c["id"], c["status"])
        ready, reason = True, None
        if status == "available":
            for e in c["engines"]:
                st, why = engine_states.get(e, ("ready", None))
                if st not in _READY_STATES:
                    ready, reason = False, why or "ENGINE_UNAVAILABLE"
                    break
        else:
            ready = False
        out.append({**c, "status": status, "ready": ready, "unready_reason": reason})
    return {"capabilities": out, "goals": list(GOALS)}
