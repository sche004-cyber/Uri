"""OD-3 (plan 16): reading PDF pages that have no text layer with Tesseract, only when the owner asks for it.

Tesseract is not installed or downloaded by URI. It is used when it is already on this PC: the path in the
`tesseract` entry of `engines.json` when there is one, else the default install folder. Each page image comes from the
existing raster path (`EngineHub.page_png`); Tesseract runs on it in its own Job Object with a memory limit and a
timeout, so a hostile or huge page takes down only that process. Unlike LibreOffice, the Tesseract program is not
hash-pinned (no pin is recorded yet); that is stated in the plan's status note.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import engines as E
from . import jobobject as J
from .errors import OfficeError

DEFAULT_EXE = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
OCR_MEMORY = 1024 * 2**20
OCR_TIMEOUT_S = 90.0
OCR_LANG = "eng"
OCR_WIDTH = 1240                    # the largest page width the raster path renders (contracts.PAGE_WIDTHS)


def tesseract_exe() -> Path | None:
    pin = E.pins().get("tesseract") or {}
    for c in (pin.get("path"), DEFAULT_EXE):
        if c and Path(c).is_file():
            return Path(c)
    return None


def ocr_png(png: Path, exe: Path | None = None) -> str:
    """The text Tesseract reads from one page image. Raises OCR_UNAVAILABLE / OCR_TIMEOUT / OCR_FAILED."""
    exe = exe or tesseract_exe()
    if exe is None:
        raise OfficeError("OCR_UNAVAILABLE", "Tesseract is not installed on this PC", 503)
    job = J.Job(memory_limit=OCR_MEMORY)
    try:
        p = J.spawn([str(exe), str(png), "stdout", "-l", OCR_LANG], job, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=str(Path(png).parent))
        try:
            out, _ = p.communicate(timeout=OCR_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            job.close()                                   # kills Tesseract and anything it started
            p.communicate()
            raise OfficeError("OCR_TIMEOUT", "reading a scanned page took too long", 503) from None
    finally:
        job.close()
    if p.returncode != 0:
        raise OfficeError("OCR_FAILED", f"Tesseract exit {p.returncode}", 503)
    return out.decode("utf-8", "replace").replace("\x0c", "").strip()
