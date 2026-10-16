"""S11 re-run (review round 3: m8, m9, M2) under OD-U13: Microsoft Print to PDF only, synthetic documents, a dedicated
temporary folder, no overwrite, outputs checked then removed, print queue checked empty.

Measures, for the pinned print worker (run copy checked against engines.json): memory, time, output size at 300 and
600 dpi, the worker's dedicated GPU memory and GPU engine use (sampled every 200 ms), and the fit-to-page result
(leftmost ink as a fraction of the page width) against the previous worker from commit 63e0e73f (1-inch margins).

    python s11_rerun.py <out.json>
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests" / "office_u2"))
from test_print_o2p import bars_pdf, ink_left_fraction  # noqa: E402
from uri_office import engines as E  # noqa: E402
from uri_office import jobobject as J  # noqa: E402
from uri_office.workerproc import powershell_exe  # noqa: E402

out_json = Path(sys.argv[1])
test_dir = Path(tempfile.mkdtemp(prefix="uri_o2p_s11_rerun_"))
work = test_dir / "work"
work.mkdir()
pdf = bars_pdf(work / "bars.pdf", 6)
state = test_dir / "state"
state.mkdir()
old = test_dir / "print_job_63e0e73f.ps1"
old.write_bytes(subprocess.run(["git", "-C", str(REPO), "show", "63e0e73f:uri_office/workers/print_job.ps1"],
                               capture_output=True).stdout)


def gpu(pid, stop, samples):
    ps = (f"$ErrorActionPreference='SilentlyContinue'; "
          f"$m=((Get-Counter '\\GPU Process Memory(pid_{pid}_*)\\Dedicated Usage').CounterSamples|Measure-Object CookedValue -Sum).Sum; "
          f"$e=((Get-Counter '\\GPU Engine(pid_{pid}_*)\\Utilization Percentage').CounterSamples|Measure-Object CookedValue -Maximum).Maximum; "
          "Write-Output \"$m $e\"")
    while not stop.is_set():
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        parts = r.stdout.split()
        if len(parts) == 2:
            try:
                samples.append((float(parts[0] or 0), float(parts[1] or 0)))
            except ValueError:
                pass
        stop.wait(0.2)


def run(script: Path, dpi: int, out: Path, measure_gpu=False):
    req = {"op": "print", "pdf": str(pdf), "pages": [1, 2, 3, 4, 5, 6], "printer": "Microsoft Print to PDF",
           "document_name": "URI Office " + uuid.uuid4().hex[:16], "copies": 1, "collate": False, "landscape": False,
           "paper": "A4", "duplex": "simplex", "color": True, "fit": "fit", "dpi": dpi, "output_file": str(out)}
    assert not out.exists()
    job = J.Job(memory_limit=1536 * 2**20)
    t0 = time.time()
    p = J.spawn([powershell_exe(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
                 str(work)], job, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stop, samples = threading.Event(), []
    th = None
    if measure_gpu:
        th = threading.Thread(target=gpu, args=(p.pid, stop, samples), daemon=True)
        th.start()
    so, se = p.communicate(json.dumps(req) + "\n", timeout=300)
    stop.set()
    if th:
        th.join(10)
    peak = job.peak_process_memory()
    job.close()
    for _ in range(40):
        if out.exists() and out.stat().st_size > 0:
            break
        time.sleep(0.25)
    import pypdf
    res = {"rc": p.returncode, "wall_s": round(time.time() - t0, 2), "peak_job_mb": round(peak / 2**20, 1),
           "out_pages": len(pypdf.PdfReader(str(out)).pages), "out_bytes": out.stat().st_size,
           "last": [l for l in so.splitlines() if l.startswith("{")][-1:]}
    if measure_gpu:
        res["gpu_samples"] = len(samples)
        res["gpu_dedicated_max_mb"] = round(max((s[0] for s in samples), default=0) / 2**20, 1)
        res["gpu_engine_max_pct"] = max((s[1] for s in samples), default=0)
    # fit check on page 1 of the output
    png_dir = test_dir / ("png_" + out.stem)
    png_dir.mkdir()
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(REPO.parent / "uri-office-unified" / "docs" / "office" / "unified" / "evidence" /
                        "pdf_print_probe_20261015" / "winrt_pdf_render.ps1"), str(out), str(png_dir), "600"],
                   capture_output=True, timeout=120)
    res["left_ink_fraction_p1"] = round(ink_left_fraction(png_dir / "winrt_p1.png"), 3)
    return res


pinned = E.run_copy("print_job.ps1", state)            # the pinned bytes, hash-checked
R = {"run": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "authority": "owner OD-U13", "document": "synthetic 6-page bars PDF",
     "pinned_worker_sha256": E.pins()["workers"]["print_job.ps1"]}
R["pinned_300dpi"] = run(pinned, 300, test_dir / "p300.pdf", measure_gpu=True)
R["pinned_600dpi"] = run(pinned, 600, test_dir / "p600.pdf", measure_gpu=True)
R["old_63e0e73f_300dpi"] = run(old, 300, test_dir / "old300.pdf")
R["expected_left_fraction_fit_printable_area"] = round(72 / 612, 3)
q = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(Get-PrintJob -PrinterName 'Microsoft Print to PDF' | Measure-Object).Count"],
                   capture_output=True, text=True).stdout.strip()
R["print_queue_jobs_after"] = q
pinned.unlink()
shutil.rmtree(test_dir)
R["test_dir_removed"] = not test_dir.exists()
out_json.write_text(json.dumps(R, indent=1))
print(json.dumps(R, indent=1))
