"""uri_devices (A1 §A6): status and connection classification from winspool bits (PR-8 fake status), New badge,
provider protocol and registry, OD-U12 descriptors, and a read-only listing of this PC's real printers (PR-1)."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from uri_devices import capability as CAP  # noqa: E402
from uri_devices import printers as P  # noqa: E402
from uri_devices.known import Known  # noqa: E402
from uri_devices.model import Device  # noqa: E402
from uri_devices.provider import Registry  # noqa: E402


def fake(rows, default=""):
    return P.PrinterProvider(enum=lambda: rows, default=lambda: default,
                             caps=lambda name, port: {"duplex": True, "color": False, "max_copies": 99,
                                                      "papers": [{"id": 9, "name": "A4"}]})


@pytest.mark.parametrize("attrs,status,expected", [
    (0, 0, "ready"),
    (P.ATTR_WORK_OFFLINE, 0, "offline"),
    (0, P.ST_OFFLINE, "offline"),
    (0, P.ST_PAPER_OUT, "error"),
    (0, P.ST_PAPER_JAM, "error"),
    (0, P.ST_DOOR_OPEN, "error"),
    (0, P.ST_PAUSED, "error"),
    (0, P.ST_PRINTING, "busy"),
], ids=["ready", "work_offline", "offline", "paper_out", "jam", "door", "paused", "printing"])
def test_status_bits(attrs, status, expected):
    pp = fake([{"name": "Office printer", "port": "USB001", "server": "", "driver": "d", "attributes": attrs,
                "status": status, "jobs": 0}])
    d = pp.list()[0]
    assert d.status == expected and (expected == "ready") == (d.status_detail == "")


@pytest.mark.parametrize("port,attrs,server,conn", [
    ("USB001", 0, "", "usb"), ("WSD-123", 0, "", "network"), ("IP_10.0.0.5", 0, "", "network"),
    ("LPT1:", P.ATTR_NETWORK, "", "network"), ("x", 0, r"\\printsrv", "network"),
    ("PORTPROMPT:", 0, "", "virtual"), ("nul:", 0, "", "virtual"), ("COM1:", 0, "", "unknown"),
])
def test_connection_classification(port, attrs, server, conn):
    pp = fake([{"name": "p", "port": port, "server": server, "driver": "d", "attributes": attrs, "status": 0,
                "jobs": 0}])
    assert pp.list()[0].connection == conn


def test_new_badge_only_after_first_look(tmp_path):
    rows = [{"name": "A", "port": "USB001", "server": "", "driver": "d", "attributes": 0, "status": 0, "jobs": 0}]
    pp = P.PrinterProvider(known=Known(tmp_path), enum=lambda: rows, default=lambda: "A",
                           caps=lambda n, p: {})
    first = pp.list()
    assert first[0].new is False and first[0].is_default
    rows.append({"name": "B", "port": "WSD-1", "server": "", "driver": "d", "attributes": 0, "status": 0, "jobs": 0})
    second = {d.name: d for d in pp.list()}
    assert second["B"].new is True and second["A"].new is False
    assert "SENTINEL" not in (tmp_path / "devices" / "known.json").read_text()


def test_untrusted_printer_name_is_kept_as_text():
    evil = "Printer\n\"; rm -rf /‮"
    pp = fake([{"name": evil, "port": "USB001", "server": "", "driver": "d", "attributes": 0, "status": 0,
                "jobs": 0}])
    d = pp.list()[0]
    assert d.name == evil and len(d.id) == 16


def test_registry_and_descriptors():
    r = Registry()
    r.register(P.PrinterProvider(enum=lambda: [], default=lambda: "", caps=lambda n, p: {}))
    assert r.kinds() == ["printer"] and r.get("scanner") is None
    pd = CAP.get("print_document")
    assert pd["approval"] == "print_job" and pd["effects"] == ["reads_files", "sends_to_printer"]
    assert CAP.get("list_printers")["approval"] == "none" and CAP.get("list_printers")["effects"] == []
    with pytest.raises(ValueError):
        Device("x", "camera", "n")


def test_no_install_or_configuration_api_is_used():
    """A1 §A6: no AddPrinter, DeletePrinter, SetPrinter, SetDefaultPrinter or driver call anywhere in uri_devices."""
    banned = ("AddPrinter", "DeletePrinter", "SetPrinterW", "SetDefaultPrinter", "AddPrinterDriver",
              "InstallPrinterDriver", "PrintUIEntry", "printui", "Add-Printer", "Set-Printer")
    for p in (ROOT / "uri_devices").glob("*.py"):
        text = p.read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, (p.name, b)


@pytest.mark.skipif(os.name != "nt", reason="Windows printers")
def test_real_listing_on_this_pc_is_read_only_and_consistent(tmp_path):
    """PR-1/PR-2 (virtual printers only on this PC, 2026-10-15): the list has a default and every entry has a
    status; capabilities read without changing anything."""
    pp = P.PrinterProvider(known=Known(tmp_path))
    devs = pp.list()
    if not devs:
        pytest.skip("no printers installed")
    assert sum(d.is_default for d in devs) <= 1
    for d in devs:
        caps = pp.capabilities(d.id)
        assert d.status in ("ready", "offline", "error", "busy", "unknown")
        assert isinstance(caps.get("max_copies"), int)
