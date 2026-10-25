"""Contract o2.1 (docs/office/unified/O2_API_CONTRACT.md): C1, C2, C5, C7; capability registry (U4, AC-O2-11)."""
import re
from pathlib import Path

import pytest

from uri_office import capabilities as CAP
from uri_office import contracts as K

DOC = Path(__file__).resolve().parents[2] / "docs" / "office" / "unified" / "O2_API_CONTRACT.md"


def test_every_route_in_the_code_table_is_documented():
    text = DOC.read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `(/[^`]+)` \| (GET|POST) \|", text, re.M))
    for method, path in K.ROUTES:
        assert (path, method) in documented, (method, path)


def test_contract_version_is_served_and_documented():
    assert K.contract_view()["contract"] == K.CONTRACT_VERSION
    assert f"`{K.CONTRACT_VERSION}`" in DOC.read_text(encoding="utf-8")


def test_every_error_has_message_and_known_recovery():
    for code, info in K.ERRORS.items():
        assert code.isupper() and info.message.endswith(".")
        assert set(info.recovery) <= set(K.RECOVERY_ACTIONS), code
    v = K.error_view("ENCRYPTED", "x")
    assert v["message"] and v["recovery"] == ["open_other"]


def test_finding_rejects_bad_values_and_long_messages():
    fs = K.Findings()
    f = fs.add("blank_page", "visual", "warning", "Page 3 is blank.", page=3)
    assert f.view()["location"] == {"file": "output", "page": 3}
    with pytest.raises(ValueError):
        K.Finding("x", "c", "nonsense", "error", "m")
    with pytest.raises(ValueError):
        K.Finding("x", "c", "visual", "error", "m" * 301)
    with pytest.raises(ValueError):
        K.Finding("x", "c", "visual", "error", "m", file="C:\\a.docx")
    fs.add("archive", "structural", "error", "Damaged.")
    assert len(fs.errors) == 1 and len(fs.warnings) == 1


def test_registry_shapes_are_closed():
    reg = CAP.registry()
    ids = [c["id"] for c in reg["capabilities"]]
    assert len(ids) == len(set(ids))
    for c in reg["capabilities"]:
        assert set(c["effects"]) <= set(K.EFFECTS) and c["approval"] in K.APPROVALS


def test_planned_capabilities_are_never_ready_and_say_not_available():
    for c in CAP.registry()["capabilities"]:
        if c["status"] != "available":
            assert c["ready"] is False
            assert "not available yet" in CAP.planned_message(c["id"])
    assert CAP.get("print_document")["status"] == "planned:O2P"          # O2 does not print
    assert CAP.get("pdf_tables_to_excel")["status"] == "planned:deferred"  # OD-U11


def test_available_groups_in_o2_match_the_plan():
    reg = CAP.registry()
    avail = {}
    for c in reg["capabilities"]:
        if c["status"] == "available" and c["goal"]:
            avail.setdefault(c["goal"], []).append(c["id"])
    # OD-2 (plan 16, 2026-10-23): write_document became available through POST /authoring/draft.
    assert avail == {"pdfs": ["view_pdf", "save_as_pdf"], "data": ["open_workbook", "new_workbook_from_files"],
                     "write": ["write_document"]}


def test_engine_state_drives_readiness():
    reg = CAP.registry({"libreoffice": ("unavailable", "ENGINE_INTEGRITY")})
    by = {c["id"]: c for c in reg["capabilities"]}
    assert by["save_as_pdf"]["ready"] is False and by["save_as_pdf"]["unready_reason"] == "ENGINE_INTEGRITY"
    assert by["view_pdf"]["ready"] is True                    # needs no LibreOffice
    assert by["open_workbook"]["ready"] is True


def test_o2p_can_flip_print_without_editing_the_table():
    reg = CAP.registry(available_overrides={"print_document": "available"})
    assert {c["id"]: c for c in reg["capabilities"]}["print_document"]["status"] == "available"
    assert CAP.get("print_document")["status"] == "planned:O2P"


def test_no_office_module_imports_pymupdf():
    """AC-O2-22."""
    root = Path(__file__).resolve().parents[2]
    pat = re.compile(r"^\s*(import|from)\s+(fitz|pymupdf)\b", re.M)
    for folder in ("uri_office", "uri_devices", "tests/office_u2"):
        base = root / folder
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            assert not pat.search(p.read_text(encoding="utf-8")), p
