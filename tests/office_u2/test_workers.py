"""Workers in Job Objects (AC-O2-20, AC-O2-5 for workers): the pypdf text worker and the WinRT raster worker run real
synthetic PDFs; hostile inputs kill only the worker; paths outside the work root are refused; a hang is killed."""
import os
import sys
import time

import pytest

from conftest import needs_windows, pdf_with_text
from uri_office import engines as E
from uri_office import jobobject as J
from uri_office.workerproc import Worker, WorkerFailed, powershell_exe, python_exe


def text_worker(state, root):
    def args():
        c = E.run_copy("pdf_text.py", state)
        return [python_exe(), "-I", str(c), str(root)], c.unlink
    return Worker("pdf_text", args, memory_limit=1024 * 2**20)


def raster_worker(state, root):
    def args():
        c = E.run_copy("winrt_raster.ps1", state)
        return [powershell_exe(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(c),
                str(root)], c.unlink
    return Worker("winrt_raster", args, memory_limit=1536 * 2**20)


def test_text_worker_info_spans_search(tmp_path, work):
    pdf = pdf_with_text(work / "a.pdf", ["Office order 41", "Annexure page two", "Notice of meeting"])
    w = text_worker(tmp_path / "state", work)
    try:
        info = w.request("info", pdf=str(pdf))
        assert info["ok"] and info["pages"] == 3 and info["encrypted"] is False
        assert info["fonts"] == [{"name": "Helvetica", "embedded": False}]
        sp = w.request("spans", pdf=str(pdf), page=1)
        assert sp["spans"][0]["size"] == 12 and "text" not in sp["spans"][0]      # no content in spans
        m = w.request("search", pdf=str(pdf), text="annexure")
        assert [x["page"] for x in m["matches"]] == [2]
        none = w.request("search", pdf=str(pdf), text="tender")
        assert none["matches"] == [] and none["text_pages"] == 3
    finally:
        w.stop()
    assert not list((tmp_path / "state" / "run").iterdir())                    # run copy removed


def test_text_worker_refuses_paths_outside_root(tmp_path, work):
    outside = pdf_with_text(tmp_path / "out.pdf", ["x"])
    w = text_worker(tmp_path / "state", work)
    try:
        assert w.request("info", pdf=str(outside))["error"] == "PATH_REFUSED"
    finally:
        w.stop()


@pytest.mark.parametrize("payload", [b"", b"%PDF-1.4\n" + os.urandom(5000), b"not a pdf at all"], ids=["empty", "random_body", "not_pdf"])
def test_malformed_pdf_fails_cleanly_and_worker_keeps_serving(tmp_path, work, payload):
    bad = work / "bad.pdf"
    bad.write_bytes(payload)
    good = pdf_with_text(work / "good.pdf", ["ok"])
    w = text_worker(tmp_path / "state", work)
    try:
        r = w.request("info", pdf=str(bad))
        assert r["ok"] is False or r.get("pages") in (0, None)
        assert w.request("info", pdf=str(good))["pages"] == 1
    finally:
        w.stop()


@needs_windows
def test_hung_worker_is_killed_with_everything_it_started(tmp_path):
    script = tmp_path / "hang.py"
    script.write_text(
        "import json,subprocess,sys,time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "print(json.dumps({'id': None, 'ok': True, 'ready': True, 'child': child.pid}), flush=True)\n"
        "time.sleep(120)\n")
    w = Worker("hang", lambda: [sys.executable, "-I", str(script)], memory_limit=256 * 2**20)
    t0 = time.monotonic()
    with pytest.raises(WorkerFailed) as e:
        w.request("info", timeout=1.5)
    assert e.value.code == "TIMEOUT" and time.monotonic() - t0 < 10
    assert not w.running


@needs_windows
def test_crashing_worker_reports_crash_and_restarts(tmp_path):
    script = tmp_path / "crash.py"
    script.write_text(
        "import json,os,sys\n"
        "print(json.dumps({'id': None, 'ok': True, 'ready': True}), flush=True)\n"
        "line = sys.stdin.readline()\n"
        "os._exit(7)\n")
    w = Worker("crash", lambda: [sys.executable, "-I", str(script)], memory_limit=256 * 2**20)
    for _ in range(2):
        with pytest.raises(WorkerFailed) as e:
            w.request("info", timeout=10)
        assert e.value.code == "CRASHED"
    assert w.starts == 2


@needs_windows
def test_job_close_kills_grandchildren():
    j = J.Job()
    code = ("import subprocess,sys,time;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
            "print(p.pid,flush=True);time.sleep(60)")
    import subprocess
    p = J.spawn([sys.executable, "-c", code], j, stdout=subprocess.PIPE, text=True)
    gc = int(p.stdout.readline())
    assert J.alive(p.pid) and J.alive(gc)
    j.close()
    deadline = time.monotonic() + 5
    while (J.alive(p.pid) or J.alive(gc)) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not J.alive(p.pid) and not J.alive(gc)


@needs_windows
def test_memory_limit_kills_only_the_worker(tmp_path):
    script = tmp_path / "hog.py"
    script.write_text(
        "import json,sys\n"
        "print(json.dumps({'id': None, 'ok': True, 'ready': True}), flush=True)\n"
        "sys.stdin.readline()\n"
        "x = bytearray(400 * 2**20)\n"
        "print(json.dumps({'id': 'never', 'ok': True}), flush=True)\n")
    w = Worker("hog", lambda: [sys.executable, "-I", str(script)], memory_limit=200 * 2**20)
    with pytest.raises(WorkerFailed) as e:
        w.request("info", timeout=20)
    assert e.value.code in ("CRASHED", "PROTOCOL")


@needs_windows
def test_raster_worker_renders_requested_pages(tmp_path, work):
    pdf = pdf_with_text(work / "a.pdf", ["one", "two", "three"])
    out = work / "out"
    out.mkdir()
    w = raster_worker(tmp_path / "state", work)
    try:
        info = w.request("info", pdf=str(pdf))
        assert info["ok"] and info["pages"] == 3 and info["sizes"][0] == [612, 792]
        r = w.request("render", pdf=str(pdf), out_dir=str(out), pages=[1, 3], width=440)
        assert r["ok"] and [x["page"] for x in r["rendered"]] == [1, 3]
        png = (out / "p3_w440.png").read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert w.request("render", pdf=str(pdf), out_dir=str(tmp_path), pages=[1], width=440)["error"] \
            == "PATH_REFUSED"
        assert w.request("render", pdf=str(pdf), out_dir=str(out), pages=[1], width=99999)["error"] == "BAD_REQUEST"
    finally:
        w.stop()


@needs_windows
@pytest.mark.parametrize("payload", [b"", b"garbage" * 1000, b"%PDF-1.4\n1 0 obj\n" + b"[" * 50000 + b"]" * 50000], ids=["empty", "garbage", "deep_nesting"])
def test_raster_worker_survives_or_dies_alone_on_malformed_pdf(tmp_path, work, payload):
    bad = work / "bad.pdf"
    bad.write_bytes(payload)
    good = pdf_with_text(work / "good.pdf", ["fine"])
    w = raster_worker(tmp_path / "state", work)
    try:
        try:
            r = w.request("info", pdf=str(bad), timeout=30)
            assert r["ok"] is False
        except WorkerFailed:
            pass                                    # killed alone; the service survives
        assert w.request("info", pdf=str(good), timeout=30)["pages"] == 1
    finally:
        w.stop()
