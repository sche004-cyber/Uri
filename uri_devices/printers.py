"""Printer provider: Windows winspool through ctypes only (A1 §A6). Read-only listing, capabilities and status, plus
reading and cancelling ONE job the Office service submitted (found by its unique document name). Nothing here adds,
removes or configures a printer, changes the default, or touches any other job.
"""
from __future__ import annotations

import ctypes
import os
import time

from .model import Device, device_id

PRINTER_ENUM_LOCAL, PRINTER_ENUM_CONNECTIONS = 0x2, 0x4
ATTR_NETWORK, ATTR_WORK_OFFLINE = 0x10, 0x400
ST_PAUSED, ST_ERROR, ST_PAPER_JAM, ST_PAPER_OUT, ST_OFFLINE = 0x1, 0x2, 0x8, 0x10, 0x80
ST_BUSY, ST_PRINTING, ST_NOT_AVAILABLE, ST_USER_INTERVENTION, ST_DOOR_OPEN = 0x200, 0x400, 0x1000, 0x100000, 0x400000
DC_PAPERS, DC_PAPERSIZE, DC_DUPLEX, DC_PAPERNAMES, DC_ORIENTATION, DC_COPIES = 2, 3, 7, 16, 17, 18
DC_COLLATE, DC_COLORDEVICE = 22, 32
JOB_CONTROL_DELETE = 5
JOB_STATUS = {0x1: "paused", 0x2: "error", 0x4: "deleting", 0x8: "spooling", 0x10: "printing", 0x20: "offline",
              0x40: "paper_out", 0x80: "printed", 0x100: "deleted", 0x400: "user_intervention", 0x800: "restarting",
              0x1000: "complete"}
VIRTUAL_PORTS = ("PORTPROMPT:", "NUL:", "FILE:", "XPSPORT:", "NE00:")


def _status(attrs: int, status: int) -> tuple[str, str]:
    if attrs & ATTR_WORK_OFFLINE or status & (ST_OFFLINE | ST_NOT_AVAILABLE):
        return "offline", "The printer is offline."
    if status & ST_PAPER_OUT:
        return "error", "The printer is out of paper."
    if status & ST_PAPER_JAM:
        return "error", "Paper is jammed."
    if status & ST_DOOR_OPEN:
        return "error", "A printer door is open."
    if status & (ST_ERROR | ST_USER_INTERVENTION):
        return "error", "The printer needs attention."
    if status & ST_PAUSED:
        return "error", "The printer is paused."
    if status & (ST_BUSY | ST_PRINTING):
        return "busy", "The printer is busy."
    return "ready", ""


def _connection(port: str, attrs: int, server: str) -> str:
    p = (port or "").upper()
    if attrs & ATTR_NETWORK or server or p.startswith(("\\\\", "WSD", "IP_", "TCP")) or ":9100" in p:
        return "network"
    if p.startswith("USB") or p.startswith("DOT4"):
        return "usb"
    if p in VIRTUAL_PORTS or p.endswith(".PDF") or p.startswith("PORTPROMPT"):
        return "virtual"
    return "unknown"


if os.name == "nt":
    import ctypes.wintypes as W

    _ws = ctypes.WinDLL("winspool.drv", use_last_error=True)

    class PRINTER_INFO_2(ctypes.Structure):
        _fields_ = [("pServerName", W.LPWSTR), ("pPrinterName", W.LPWSTR), ("pShareName", W.LPWSTR),
                    ("pPortName", W.LPWSTR), ("pDriverName", W.LPWSTR), ("pComment", W.LPWSTR),
                    ("pLocation", W.LPWSTR), ("pDevMode", ctypes.c_void_p), ("pSepFile", W.LPWSTR),
                    ("pPrintProcessor", W.LPWSTR), ("pDatatype", W.LPWSTR), ("pParameters", W.LPWSTR),
                    ("pSecurityDescriptor", ctypes.c_void_p), ("Attributes", W.DWORD), ("Priority", W.DWORD),
                    ("DefaultPriority", W.DWORD), ("StartTime", W.DWORD), ("UntilTime", W.DWORD),
                    ("Status", W.DWORD), ("cJobs", W.DWORD), ("AveragePPM", W.DWORD)]

    class SYSTEMTIME(ctypes.Structure):
        _fields_ = [(n, W.WORD) for n in ("y", "mo", "dow", "d", "h", "mi", "s", "ms")]

    class JOB_INFO_1(ctypes.Structure):
        _fields_ = [("JobId", W.DWORD), ("pPrinterName", W.LPWSTR), ("pMachineName", W.LPWSTR),
                    ("pUserName", W.LPWSTR), ("pDocument", W.LPWSTR), ("pDatatype", W.LPWSTR),
                    ("pStatus", W.LPWSTR), ("Status", W.DWORD), ("Priority", W.DWORD), ("Position", W.DWORD),
                    ("TotalPages", W.DWORD), ("PagesPrinted", W.DWORD), ("Submitted", SYSTEMTIME)]

    _ws.EnumPrintersW.argtypes = (W.DWORD, W.LPWSTR, W.DWORD, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD),
                                  ctypes.POINTER(W.DWORD))
    _ws.GetDefaultPrinterW.argtypes = (W.LPWSTR, ctypes.POINTER(W.DWORD))
    _ws.DeviceCapabilitiesW.argtypes = (W.LPCWSTR, W.LPCWSTR, W.WORD, ctypes.c_void_p, ctypes.c_void_p)
    _ws.DeviceCapabilitiesW.restype = ctypes.c_int
    _ws.OpenPrinterW.argtypes = (W.LPWSTR, ctypes.POINTER(W.HANDLE), ctypes.c_void_p)
    _ws.ClosePrinter.argtypes = (W.HANDLE,)
    _ws.EnumJobsW.argtypes = (W.HANDLE, W.DWORD, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD,
                              ctypes.POINTER(W.DWORD), ctypes.POINTER(W.DWORD))
    _ws.SetJobW.argtypes = (W.HANDLE, W.DWORD, W.DWORD, ctypes.c_void_p, W.DWORD)


def _enum_printers() -> list:
    flags = PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    need, count = W.DWORD(0), W.DWORD(0)
    _ws.EnumPrintersW(flags, None, 2, None, 0, ctypes.byref(need), ctypes.byref(count))
    if need.value == 0:
        return []
    buf = ctypes.create_string_buffer(need.value)
    if not _ws.EnumPrintersW(flags, None, 2, buf, need, ctypes.byref(need), ctypes.byref(count)):
        raise OSError(ctypes.get_last_error(), "EnumPrintersW failed")
    arr = ctypes.cast(buf, ctypes.POINTER(PRINTER_INFO_2))
    out = []
    for i in range(count.value):
        p = arr[i]
        out.append({"name": p.pPrinterName or "", "port": p.pPortName or "", "server": p.pServerName or "",
                    "driver": p.pDriverName or "", "attributes": int(p.Attributes), "status": int(p.Status),
                    "jobs": int(p.cJobs)})
    return out


def _default_printer() -> str:
    n = W.DWORD(0)
    _ws.GetDefaultPrinterW(None, ctypes.byref(n))
    if n.value == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n.value)
    return buf.value if _ws.GetDefaultPrinterW(buf, ctypes.byref(n)) else ""


def _caps(name: str, port: str) -> dict:
    def count(cap):
        return _ws.DeviceCapabilitiesW(name, port, cap, None, None)
    out: dict = {}
    n = count(DC_PAPERNAMES)
    if n > 0:
        buf = ctypes.create_unicode_buffer(64 * n)
        count_ = _ws.DeviceCapabilitiesW(name, port, DC_PAPERNAMES, buf, None)
        raw = ctypes.wstring_at(ctypes.addressof(buf), 64 * max(count_, 0))
        names = [raw[i * 64:(i + 1) * 64].split("\x00", 1)[0] for i in range(max(count_, 0))]
        ids = (ctypes.c_ushort * n)()
        _ws.DeviceCapabilitiesW(name, port, DC_PAPERS, ids, None)
        sizes = (ctypes.c_long * (2 * n))()
        _ws.DeviceCapabilitiesW(name, port, DC_PAPERSIZE, sizes, None)
        out["papers"] = [{"id": int(ids[i]), "name": names[i][:64], "width_mm": sizes[2 * i] / 10.0,
                          "height_mm": sizes[2 * i + 1] / 10.0} for i in range(len(names))][:200]
    out["duplex"] = count(DC_DUPLEX) == 1
    out["color"] = count(DC_COLORDEVICE) == 1
    out["max_copies"] = max(1, count(DC_COPIES))
    out["collate"] = count(DC_COLLATE) == 1
    out["landscape"] = count(DC_ORIENTATION) in (90, 270)
    return out


class PrinterProvider:
    """The `printer` provider. `enum` and `caps` can be replaced in tests (fake status bits, PR-8)."""
    kind = "printer"

    def __init__(self, known=None, enum=None, default=None, caps=None):
        self.known = known
        self._enum = enum or _enum_printers
        self._default = default or _default_printer
        self._caps = caps or _caps
        self._cache: dict[str, Device] = {}

    def list(self) -> list[Device]:
        if os.name != "nt" and self._enum is _enum_printers:
            return []
        default = self._default()
        out = []
        for p in self._enum():
            st, detail = _status(p["attributes"], p["status"])
            d = Device(id=device_id("printer", p["name"]), kind="printer", name=p["name"],
                       connection=_connection(p["port"], p["attributes"], p["server"]),
                       is_default=(p["name"] == default), status=st, status_detail=detail, port=p["port"],
                       server=p["server"])
            out.append(d)
        if self.known is not None:
            self.known.mark(out)
        self._cache = {d.id: d for d in out}
        return out

    def get(self, did: str) -> Device | None:
        if did not in self._cache:
            self.list()
        return self._cache.get(did)

    def capabilities(self, did: str) -> dict:
        d = self.get(did)
        if d is None:
            return {}
        try:
            caps = self._caps(d.name, d.port)
        except OSError:
            caps = {}
        d.capabilities = caps
        return caps

    def status(self, did: str) -> tuple[str, str]:
        self.list()
        d = self._cache.get(did)
        return (d.status, d.status_detail) if d else ("unknown", "The printer is no longer installed.")


# ---- the one job URI submitted ----------------------------------------------------------------------------------
def _open(name: str):
    h = W.HANDLE()
    if not _ws.OpenPrinterW(name, ctypes.byref(h), None):
        raise OSError(ctypes.get_last_error(), "OpenPrinterW failed")
    return h


def find_job(printer: str, document_name: str) -> dict | None:
    """The job whose document name is exactly `document_name` (a unique token per job), or None."""
    if os.name != "nt":
        return None
    h = _open(printer)
    try:
        need, count = W.DWORD(0), W.DWORD(0)
        _ws.EnumJobsW(h, 0, 999, 1, None, 0, ctypes.byref(need), ctypes.byref(count))
        if need.value == 0:
            return None
        buf = ctypes.create_string_buffer(need.value)
        if not _ws.EnumJobsW(h, 0, 999, 1, buf, need, ctypes.byref(need), ctypes.byref(count)):
            return None
        arr = ctypes.cast(buf, ctypes.POINTER(JOB_INFO_1))
        for i in range(count.value):
            j = arr[i]
            if (j.pDocument or "") == document_name:
                states = [v for k, v in JOB_STATUS.items() if j.Status & k]
                return {"job_id": int(j.JobId), "status": states or ["queued"], "pages_total": int(j.TotalPages),
                        "pages_printed": int(j.PagesPrinted), "user": j.pUserName or ""}
        return None
    finally:
        _ws.ClosePrinter(h)


def cancel_job(printer: str, document_name: str) -> bool:
    """Delete exactly the job with this unique document name. Returns False when it is no longer in the queue."""
    j = find_job(printer, document_name)
    if j is None:
        return False
    h = _open(printer)
    try:
        return bool(_ws.SetJobW(h, j["job_id"], 0, None, JOB_CONTROL_DELETE))
    finally:
        _ws.ClosePrinter(h)


def now() -> float:
    return time.time()
