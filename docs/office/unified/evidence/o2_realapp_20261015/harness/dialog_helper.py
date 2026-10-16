"""Operates the REAL Windows file dialogs the URI app opens (file_picker's IFileDialog), for the O2 live runs.

    python -B -I harness\\dialog_helper.py <run-name>

The driver appends requests to fixtures/<run>/pick-queue.jsonl: {"title": <dialog title>, "path": <file or folder>}
or {"title": ..., "cancel": true}. For each, this helper waits for a visible top-level dialog (class #32770) with
that exact title owned by uri_ui.exe, writes the path into the dialog's file-name box (WM_SETTEXT) and presses its
OK button (BM_CLICK), or presses Cancel. Method recorded per action: Win32 messages to the real dialog controls, not
physical keyboard input. Every action is logged to evidence/live/<run>/dialog-actions.json. Stops on
fixtures/<run>/stop or evidence/live/<run>/ui-finished.json.
"""
import ctypes, ctypes.wintypes as W, datetime, json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUN = sys.argv[1]
FX, OUT = ROOT / f"fixtures/{RUN}", ROOT / f"evidence/live/{RUN}"
FX.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
QUEUE = FX / "pick-queue.jsonl"
u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
WM_SETTEXT, BM_CLICK, WM_GETTEXT = 0x000C, 0x00F5, 0x000D
EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
u32.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
u32.SendMessageW.restype = W.LPARAM


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, b, 256)
    return b.value


def text(h):
    b = ctypes.create_unicode_buffer(512)
    u32.GetWindowTextW(h, b, 512)
    return b.value


def proc_name(h):
    pid = W.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    hp = k32.OpenProcess(0x1000, False, pid.value)
    if not hp:
        return "", pid.value
    b = ctypes.create_unicode_buffer(1024)
    n = W.DWORD(1024)
    k32.QueryFullProcessImageNameW(hp, 0, b, ctypes.byref(n))
    k32.CloseHandle(hp)
    return pathlib.Path(b.value).name.lower(), pid.value


def top_dialogs():
    found = []

    def cb(h, _):
        if u32.IsWindowVisible(h) and cls(h) == "#32770":
            found.append(h)
        return True
    u32.EnumWindows(EnumProc(cb), 0)
    return found


def children(h):
    out = []

    def cb(c, _):
        out.append(c)
        return True
    u32.EnumChildWindows(h, EnumProc(cb), 0)
    return out


def name_box(dlg):
    # The file-name box of the common item dialog: ComboBoxEx32/ComboBox id 1148 (cmb13) holding an Edit, or a bare
    # Edit with id 1152 (edt1) in some layouts.
    for c in children(dlg):
        if u32.GetDlgCtrlID(c) in (1148, 1152) and u32.IsWindowVisible(c):
            if cls(c) == "Edit":
                return c
            for e in children(c):
                if cls(e) == "Edit":
                    return e
    return None


def button(dlg, cid):
    for c in children(dlg):
        if cls(c) == "Button" and u32.GetDlgCtrlID(c) == cid:
            return c
    return None


def main():
    done, actions = 0, []
    while not (FX / "stop").exists() and not (OUT / "ui-finished.json").exists():
        reqs = [json.loads(l) for l in QUEUE.read_text(encoding="utf-8").splitlines() if l.strip()] if QUEUE.exists() else []
        if done >= len(reqs):
            time.sleep(0.3)
            continue
        req = reqs[done]
        dlg = None
        end = time.monotonic() + 45
        while dlg is None and time.monotonic() < end:
            for h in top_dialogs():
                pn, pid = proc_name(h)
                if text(h) == req["title"] and pn in ("uri_ui.exe", "uri_ui_test.exe") or (text(h) == req["title"] and pn.startswith("uri_ui")):
                    dlg = h
            if dlg is None:
                time.sleep(0.2)
        row = dict(utc=now(), request=req, found=dlg is not None)
        if dlg is not None:
            time.sleep(0.6)                                          # let the dialog finish its layout
            if req.get("cancel"):
                b = button(dlg, 2)
                row["cancel_button"] = bool(b)
                if b:
                    u32.SendMessageW(b, BM_CLICK, 0, 0)
            else:
                box = name_box(dlg)
                row["name_box"] = bool(box)
                if box:
                    buf = ctypes.create_unicode_buffer(req["path"])
                    u32.SendMessageW(box, WM_SETTEXT, 0, ctypes.addressof(buf))
                    ok = button(dlg, 1)
                    row["ok_button"] = bool(ok)
                    if ok:
                        u32.SendMessageW(ok, BM_CLICK, 0, 0)
                        time.sleep(1.0)
                        # A folder dialog given a folder path may navigate into it first; press OK once more.
                        if u32.IsWindow(dlg) and u32.IsWindowVisible(dlg):
                            ok2 = button(dlg, 1)
                            row["second_ok"] = bool(ok2)
                            if ok2:
                                u32.SendMessageW(ok2, BM_CLICK, 0, 0)
            time.sleep(0.5)
            row["dialog_closed"] = not (u32.IsWindow(dlg) and u32.IsWindowVisible(dlg))
        row["method"] = "Win32 WM_SETTEXT + BM_CLICK to the real dialog controls (not physical input)"
        actions.append(row)
        (OUT / "dialog-actions.json").write_text(json.dumps(actions, indent=1))
        done += 1


if __name__ == "__main__":
    main()
