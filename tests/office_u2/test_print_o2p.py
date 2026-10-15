"""O2P printing through the real service: PR-3 preview, PR-4 card binding (stale on a changed setting, printer or
capability; replay refused), PR-8 offline refused (fake status), PR-11 nothing prints without approval, and PR-5 a real
job to Microsoft Print to PDF under the owner's standing OD-U13 approval (synthetic document, dedicated temporary
folder, no overwrite, no dialog, output validated, then removed). Never a physical printer.

PR-5 counts as virtual-printer evidence only. It never counts as physical print qualification (A8 rule)."""
from __future__ import annotations

import http.client
import json
import os
import threading
import time
from pathlib import Path

import pytest

from conftest import needs_windows
from uri_office.service import Office, serve

VIRTUAL = "Microsoft Print to PDF"


def bars_pdf(path: Path, pages: int) -> Path:
    """Page N shows N thick black bars, so a printed page can be identified by counting bars."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None]
    kids = []
    for n in range(1, pages + 1):
        ops = " ".join(f"0 0 0 rg {72 + i * 90} 300 50 300 re f" for i in range(n))
        content = ops.encode()
        objs.append(f"<< /Length {len(content)} >>\nstream\n{ops}\nendstream")
        cid = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {cid} 0 R /Resources << >> >>")
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


def count_bars(png: Path) -> int:
    from PIL import Image
    with Image.open(png) as im:
        g = im.convert("L")
        w, h = g.size
        row = h // 2
        px = g.load()
        bars, inside = 0, False
        for x in range(w):
            dark = px[x, row] < 128
            if dark and not inside:
                bars += 1
            inside = dark
        return bars


def call(port, token, method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    c.request(method, path, body=json.dumps(body).encode() if body is not None else None,
              headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    r = c.getresponse()
    out = (r.status, json.loads(r.read() or b"{}"))
    c.close()
    return out


def card_action(messages, button="apply"):
    sid = messages[0]["createSurface"]["surfaceId"]
    bound = messages[2]["updateDataModel"]["value"]["bound"]
    name = "office.apply_change" if button == "apply" else "office.reject_change"
    return {"name": name, "surfaceId": sid, "sourceComponentId": button,
            "context": {"surface_digest": bound["surface"]["digest"], "change_sha256": bound["change_sha256"]}}


def svc(tmp_path, printing=True):
    office = Office(tmp_path / "state", allowed_roots=[tmp_path], printing=printing)
    srv, token = serve(office, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return office, srv, token


@pytest.fixture
def running(tmp_path):
    office, srv, token = svc(tmp_path)
    yield office, srv.server_address[1], token, tmp_path
    srv.shutdown()
    srv.server_close()
    if office._hub is not None:
        office._hub.shutdown()


def open_pdf(port, token, path):
    st, v = call(port, token, "POST", "/open/document", {"path": str(path)})
    assert st == 200, v
    did = v["document_id"]
    for _ in range(100):
        v = call(port, token, "GET", f"/document/{did}")[1]
        if v["preview"]["state"] != "rendering":
            break
        time.sleep(0.2)
    assert v["preview"]["state"] == "ready", v
    return did


def test_printing_is_planned_until_enabled(tmp_path):
    office, srv, token = svc(tmp_path, printing=False)
    try:
        port = srv.server_address[1]
        st, r = call(port, token, "GET", "/devices/printers")
        assert st == 409 and r["error"] == "CAPABILITY_PLANNED"
        caps = {c["id"]: c for c in call(port, token, "GET", "/capabilities")[1]["capabilities"]}
        assert caps["print_document"]["status"] == "planned:O2P"
    finally:
        srv.shutdown()
        srv.server_close()


class FakeProvider:
    """Fake printer list for binding and offline tests (PR-4, PR-8): no Windows printer is touched."""
    def __init__(self):
        from uri_devices.model import Device
        self.d = Device("f" * 16, "printer", "Office Laser", connection="network", is_default=True, status="ready",
                        port="IP_10.0.0.9", server=r"\\printsrv")
        self.caps = {"duplex": True, "color": False, "max_copies": 9, "collate": True,
                     "papers": [{"id": 9, "name": "A4"}]}

    def list(self):
        return [self.d]

    def get(self, did):
        return self.d if did == self.d.id else None

    def capabilities(self, did):
        self.d.capabilities = dict(self.caps)
        return self.d.capabilities

    def status(self, did):
        return self.d.status, self.d.status_detail


@needs_windows
def test_card_binding_offline_and_no_print_without_approval(running, monkeypatch):
    office, port, token, root = running
    did = open_pdf(port, token, bars_pdf(root / "notice.pdf", 3))
    pr = office.printing
    fake = FakeProvider()
    pr.provider = fake
    submitted = []
    monkeypatch.setattr(pr, "_run_worker", lambda req, timeout, on_line=None: (
        submitted.append(req) or ([{"ok": True, "pages": 1}] if req["op"] == "print" else
                                  [{"ok": True, "printable_mm": [4, 4, 202, 289], "paper_mm": [210, 297]}])))
    body = {"source": {"document_id": did}, "printer_id": fake.d.id, "pages": [2],
            "settings": {"copies": 2, "duplex": "long", "paper": "A4", "color": False}}
    st, pv = call(port, token, "POST", "/print/preview", body)
    assert st == 200 and pv["pages"] == [2] and pv["printable_area"]["printable_mm"] == [4, 4, 202, 289]
    # settings the printer cannot do are refused before any card
    for bad in ({"color": True}, {"copies": 50}, {"paper": "Legal"}, {"duplex": "sideways"}):
        st, r = call(port, token, "POST", "/print/propose", {**body, "settings": {**body["settings"], **bad}})
        assert st == 409 and r["error"] == "SETTING_NOT_SUPPORTED", bad
    st, card = call(port, token, "POST", "/print/propose", body)
    assert st == 200
    text = json.dumps(card["messages"])
    assert "Office Laser" in text and "the pages leave this PC" in text and "2 copies" in text
    assert [r for r in submitted if r["op"] == "print"] == []           # PR-11: nothing printed without approval
    # PR-4: a capability change after the card makes it stale
    fake.caps["duplex"] = False
    st, r = call(port, token, "POST", "/a2ui/action", {"action": card_action(card["messages"])})
    assert st == 409 and r["error"] == "STALE_CHANGE"
    fake.caps["duplex"] = True
    st, card = call(port, token, "POST", "/print/propose", body)
    # PR-8: the printer goes offline before approval: nothing is submitted
    fake.d.status, fake.d.status_detail = "offline", "The printer is offline."
    st, r = call(port, token, "POST", "/a2ui/action", {"action": card_action(card["messages"])})
    assert st == 409 and r["error"] == "PRINTER_UNAVAILABLE"
    assert call(port, token, "POST", "/print/propose", body)[1]["error"] == "PRINTER_UNAVAILABLE"
    fake.d.status, fake.d.status_detail = "ready", ""
    st, card = call(port, token, "POST", "/print/propose", body)
    st, r = call(port, token, "POST", "/a2ui/action", {"action": card_action(card["messages"])})
    assert st == 200 and r["status"] == "applied" and r["state"] == "queued"
    st, r2 = call(port, token, "POST", "/a2ui/action", {"action": card_action(card["messages"])})
    assert st != 200                                                     # replay refused
    for _ in range(50):
        if [x for x in submitted if x["op"] == "print"]:
            break
        time.sleep(0.1)
    req = [x for x in submitted if x["op"] == "print"][0]
    assert req["pages"] == [2] and req["copies"] == 2 and req["duplex"] == "long" and req["output_file"] is None
    assert req["document_name"].startswith("URI Office ") and "notice" not in req["document_name"]
    # a declined card prints nothing
    st, card = call(port, token, "POST", "/print/propose", body)
    n = len(submitted)
    st, r = call(port, token, "POST", "/a2ui/action", {"action": card_action(card["messages"], "reject")})
    assert r["status"] == "declined" and len(submitted) == n


@needs_windows
def test_virtual_printer_job_writes_the_approved_pages(running):
    """PR-5 under OD-U13: a real job to Microsoft Print to PDF. Synthetic 3-page document; page 2 only, 2 bars on it;
    output in the pytest temporary folder, checked, then removed."""
    office, port, token, root = running
    pr = office.printing
    printers = {p["name"]: p for p in call(port, token, "GET", "/devices/printers")[1]["printers"]}
    if VIRTUAL not in printers:
        pytest.skip("Microsoft Print to PDF is not installed")
    pid = printers[VIRTUAL]["id"]
    test_dir = root / "o2p_virtual_print"
    test_dir.mkdir()
    did = open_pdf(port, token, bars_pdf(root / "bars.pdf", 3))
    out = test_dir / "printed.pdf"
    body = {"source": {"document_id": did}, "printer_id": pid, "pages": [2], "output_path": str(out),
            "settings": {"copies": 1, "paper": "A4", "fit": "fit", "dpi": 300}}
    st, card = call(port, token, "POST", "/print/propose", body)
    assert st == 200, card
    assert "writes a file" in json.dumps(card["messages"])
    assert not out.exists()                                              # nothing before approval
    st, r = call(port, token, "POST", "/a2ui/action", {"action": card_action(card["messages"])})
    assert st == 200 and r["state"] == "queued", r
    job = r["job"]
    for _ in range(240):
        v = call(port, token, "GET", f"/print/{job}")[1]
        if v["state"] not in ("queued", "printing"):
            break
        time.sleep(0.25)
    assert v["state"] == "sent" and v["output_written"] is True, v
    import pypdf
    assert len(pypdf.PdfReader(str(out)).pages) == 1
    # the printed page is page 2 (two bars), drawn by the raster worker
    png_dir = office.hub.work_root / "check"
    png_dir.mkdir()
    shutil_copy = __import__("shutil").copy2
    shutil_copy(out, png_dir / "printed.pdf")
    rr = office.hub.raster_request("render", pdf=str(png_dir / "printed.pdf"), out_dir=str(png_dir), pages=[1],
                                   width=440)
    assert count_bars(png_dir / rr["rendered"][0]["file"]) == 2
    # a second job to the same file is refused: an existing file is never replaced
    st, r = call(port, token, "POST", "/print/propose", body)
    assert st == 409 and r["error"] == "DESTINATION_EXISTS"
    assert not (office.hub.work_root / "print" / job / "print.pdf").exists()   # print copy removed
    out.unlink()                                                         # OD-U13: clean up the generated output
    assert list(test_dir.iterdir()) == []
