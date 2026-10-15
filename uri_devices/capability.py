"""Reusable, transport-free capability descriptors for devices (owner OD-U12, contract §7).

The Office service's routes call these today. A later registration with the Brain and wider orchestration would wrap
the same descriptors (for example as a Core external-capability descriptor that calls the Office service) without a
redesign. That registration touches frozen Core and needs separate owner authorization; nothing here registers.
`effects` and `approval` use the same closed vocabularies as the Office capability registry.
"""
from __future__ import annotations

DESCRIPTORS = (
    {"id": "list_printers", "title": "List printers", "inputs": [], "effects": [], "approval": "none",
     "requires_device_kind": "printer",
     "summary": "Read the installed printers, the default, their status and capabilities. Local and read-only."},
    {"id": "print_document", "title": "Print", "inputs": ["pdf"], "effects": ["reads_files", "sends_to_printer"],
     "approval": "print_job", "requires_device_kind": "printer",
     "summary": "Print approved pages of one document with approved settings, after the owner approves a print "
                "card. Every kind becomes a PDF first."},
    {"id": "cancel_print", "title": "Cancel a print job", "inputs": [], "effects": [], "approval": "none",
     "requires_device_kind": "printer", "summary": "Cancel the one job URI submitted. Never touches other jobs."},
)

FUTURE = ({"id": "scan_document", "status": "not planned in O2P", "requires_device_kind": "scanner"},)


def get(cid: str) -> dict | None:
    return next((d for d in DESCRIPTORS if d["id"] == cid), None)
