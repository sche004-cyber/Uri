"""LibreOffice headless probe: private profile, convert DOCX/PPTX to PDF, rasterize, measure time + peak RSS."""
import json, subprocess, sys, time, tempfile, shutil, os
from pathlib import Path
import psutil, pymupdf
SOFFICE = os.path.join(os.environ["LOCALAPPDATA"], "URI", "engines", "libreoffice-26.8.1", "program", "soffice.com")
here = Path(sys.argv[1]); out = here / "lo_out"; shutil.rmtree(out, ignore_errors=True); out.mkdir()
prof = Path(tempfile.mkdtemp(prefix="lo_prof_"))
R = {"soffice": SOFFICE, "version": subprocess.run([SOFFICE, "--version"], capture_output=True, text=True, timeout=120).stdout.strip()}
def convert(src, label):
    cmd = [SOFFICE, f"-env:UserInstallation={prof.as_uri()}", "--headless", "--norestore", "--nolockcheck",
           "--convert-to", "pdf", "--outdir", str(out), str(here / src)]
    t0 = time.perf_counter(); p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE); peak = 0
    while p.poll() is None:
        try:
            procs = [psutil.Process(p.pid)] + psutil.Process(p.pid).children(recursive=True)
            peak = max(peak, sum(x.memory_info().rss for x in procs if x.is_running()))
        except psutil.Error: pass
        time.sleep(0.05)
    dt = time.perf_counter() - t0
    pdf = out / (Path(src).stem + ".pdf"); d = pymupdf.open(pdf) if pdf.exists() else None
    if d:
        for i in range(min(3, d.page_count)): d[i].get_pixmap(dpi=70).save(out / f"{Path(src).stem}_p{i+1}.png")
    R[label] = {"rc": p.returncode, "seconds": round(dt, 2), "peak_rss_mb": round(peak / 2**20, 1),
                "pages": d.page_count if d else None, "stderr": p.stderr.read().decode(errors="replace")[-300:]}
convert("order.docx", "docx_cold"); convert("order.docx", "docx_warm_profile"); convert("deck.pptx", "pptx")
shutil.rmtree(prof, ignore_errors=True)
print(json.dumps(R, indent=1))
