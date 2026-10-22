r"""EMBER-V21-INTEG Win32 probe for the companion window (answers the live driver's probe-<step>.json files).

    python -B -I tools\win_probe.py <run-label>

For each request it finds the driver's top-level window by process id and measures, with real Windows APIs:
  * borderless: GWL_STYLE / GWL_EXSTYLE (no caption, no sizing frame, no border), DWM extended frame bounds equal to
    the window rect (no invisible shadow frame), window region kind;
  * per-pixel transparency: a backdrop window of a known colour is placed directly behind the companion window and
    the composited screen is captured (PIL ImageGrab, BitBlt with CAPTUREBLT). With magenta and green backdrops the
    window's own alpha is recovered per pixel: C = a*E + (1-a)*B, so |C_magenta - C_green| = (1-a)*255 on every
    channel. Region clipping alone gives only a in {0, 1}; per-pixel alpha shows intermediate values. Black and
    white backdrops give the dark- and light-desktop screenshots;
  * click-through: a real OS click (SendInput) at a transparent point of the window rect must reach the backdrop;
    a click on Ember must not (WindowFromPoint is the companion window);
  * drag: press on Ember, move, release (SendInput); the window rect must move.
The cursor position is restored after input steps. Nothing else on the desktop is touched.
"""
import ctypes, ctypes.wintypes as W, json, pathlib, sys, threading, time

from PIL import Image, ImageGrab
import tkinter as tk

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = sys.argv[1]
OUT = ROOT / f"live/{LABEL}"
OUT.mkdir(parents=True, exist_ok=True)
u32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2: physical pixels everywhere
GWL_STYLE, GWL_EXSTYLE = -16, -20
WS = dict(CAPTION=0x00C00000, BORDER=0x00800000, DLGFRAME=0x00400000, THICKFRAME=0x00040000, SYSMENU=0x00080000,
          POPUP=0x80000000)
WS_EX = dict(DLGMODALFRAME=0x1, CLIENTEDGE=0x200, WINDOWEDGE=0x100, STATICEDGE=0x20000, LAYERED=0x80000, TOPMOST=0x8,
             NOREDIRECTIONBITMAP=0x00200000, TRANSPARENT=0x20)
COLORS = {"magenta": (255, 0, 255), "green": (0, 255, 0), "black": (0, 0, 0), "white": (255, 255, 255)}


def find_window(pid):
    found = []

    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, _):
        p = W.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h):
            r = W.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
            found.append((h, (r.right - r.left) * (r.bottom - r.top)))
        return True
    u32.EnumWindows(cb, 0)
    return max(found, key=lambda x: x[1])[0] if found else None


def rect(h):
    r = W.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def window_facts(h):
    style = u32.GetWindowLongW(h, GWL_STYLE) & 0xFFFFFFFF
    ex = u32.GetWindowLongW(h, GWL_EXSTYLE) & 0xFFFFFFFF
    ext = W.RECT()
    dwm.DwmGetWindowAttribute(h, 9, ctypes.byref(ext), ctypes.sizeof(ext))  # DWMWA_EXTENDED_FRAME_BOUNDS
    rgn = ctypes.windll.gdi32.CreateRectRgn(0, 0, 0, 0)
    kind = u32.GetWindowRgn(h, rgn)
    ctypes.windll.gdi32.DeleteObject(rgn)
    cls = ctypes.create_unicode_buffer(256); u32.GetClassNameW(h, cls, 256)
    flags = {k: bool(style & v) for k, v in WS.items()}
    exflags = {k: bool(ex & v) for k, v in WS_EX.items()}
    r = rect(h)
    ext_t = (ext.left, ext.top, ext.right, ext.bottom)
    cr = W.RECT(); u32.GetClientRect(h, ctypes.byref(cr))
    client_size = (cr.right - cr.left, cr.bottom - cr.top)
    style_borderless = not (flags["CAPTION"] or flags["THICKFRAME"] or flags["BORDER"] or flags["DLGFRAME"]
                      or exflags["DLGMODALFRAME"] or exflags["CLIENTEDGE"] or exflags["WINDOWEDGE"] or exflags["STATICEDGE"])
    return dict(hwnd=int(h), class_name=cls.value, style=hex(style), exstyle=hex(ex), style_flags=flags, ex_flags=exflags,
                rect=r, dwm_extended_frame=ext_t, shadow_frame_px=[ext_t[i] - r[i] for i in range(4)],
                region_kind={0: "ERROR", 1: "NULLREGION", 2: "SIMPLEREGION", 3: "COMPLEXREGION"}.get(kind, kind),
                style_borderless=style_borderless, client_size=client_size,
                window_size=(r[2] - r[0], r[3] - r[1]),
                no_nonclient_area=client_size == (r[2] - r[0], r[3] - r[1]))


class Backdrop:
    """A borderless solid-colour window directly behind the companion window. Records clicks."""

    def __init__(self):
        self.ready = threading.Event()
        self.clicks = []
        threading.Thread(target=self._run, daemon=True).start()
        self.ready.wait(10)

    def _run(self):
        self.tk = tk.Tk()
        self.tk.overrideredirect(True)
        self.tk.withdraw()
        self.tk.bind("<Button-1>", lambda e: self.clicks.append((e.x_root, e.y_root, time.time())))
        self.ready.set()
        self.tk.mainloop()

    def call(self, fn):
        ev = threading.Event(); box = {}
        def run():
            try:
                box["v"] = fn()
            finally:
                ev.set()
        self.tk.after(0, run); ev.wait(10)
        return box.get("v")

    def show(self, color, r, companion, margin=60):
        x, y = r[0] - margin, r[1] - margin
        w, h = r[2] - r[0] + 2 * margin, r[3] - r[1] + 2 * margin

        def go():
            self.tk.configure(bg="#%02x%02x%02x" % COLORS[color])
            self.tk.geometry(f"{w}x{h}+{x}+{y}")
            self.tk.deiconify()
            self.tk.update()
            return self.tk.winfo_id()
        self.call(go)
        hw = u32.GetAncestor(self.call(lambda: self.tk.winfo_id()), 2)  # GA_ROOT
        # Directly behind the companion window, without activating anything.
        u32.SetWindowPos(hw, companion, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE
        time.sleep(0.6)
        return hw

    def hide(self):
        self.call(lambda: self.tk.withdraw())


def grab(r):
    return ImageGrab.grab(bbox=r, all_screens=True).convert("RGB")


def alpha_map(img_m, img_g):
    w, h = img_m.size
    pm, pg = img_m.load(), img_g.load()
    a = Image.new("L", (w, h))
    pa = a.load()
    for yy in range(h):
        for xx in range(w):
            m, g = pm[xx, yy], pg[xx, yy]
            d = (abs(m[0] - g[0]) + abs(m[1] - g[1]) + abs(m[2] - g[2])) / 3
            pa[xx, yy] = max(0, min(255, round(255 - d)))
    return a


def summarize(a):
    w, h = a.size
    px = list(a.getdata())
    n = len(px)
    trans = sum(1 for v in px if v <= 5)
    opaque = sum(1 for v in px if v >= 250)
    blended = n - trans - opaque
    edge = [a.getpixel((x, y)) for x in range(w) for y in (0, 1, 2, h - 3, h - 2, h - 1)] + \
           [a.getpixel((x, y)) for y in range(h) for x in (0, 1, 2, w - 3, w - 2, w - 1)]
    bbox = a.point(lambda v: 255 if v > 128 else 0).getbbox()
    # Transparent pixels inside the visible silhouette's bounding box: transparency inside the drawn area, not only
    # outside a clipping region.
    inner_trans = 0
    if bbox:
        sub = list(a.crop(bbox).getdata())
        inner_trans = sum(1 for v in sub if v <= 5) / max(1, len(sub))
    return dict(size=[w, h], transparent_frac=round(trans / n, 4), opaque_frac=round(opaque / n, 4),
                blended_frac=round(blended / n, 4), edge_alpha_max=max(edge), edge_alpha_mean=round(sum(edge) / len(edge), 2),
                silhouette_bbox=bbox, transparent_frac_inside_bbox=round(inner_trans, 4))


def click(x, y, down_up=True):
    u32.SetCursorPos(int(x), int(y)); time.sleep(0.15)
    if down_up:
        u32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.05); u32.mouse_event(0x0004, 0, 0, 0, 0)


def root_at(x, y):
    return u32.GetAncestor(u32.WindowFromPoint(W.POINT(int(x), int(y))), 2)


def pick_points(a, r):
    """A transparent point far from the silhouette and an opaque Ember point near its centre (screen coords)."""
    w, h = a.size
    bbox = a.point(lambda v: 255 if v > 128 else 0).getbbox() or (0, 0, w, h)
    trans = None
    for (x, y) in [(6, 6), (w - 7, 6), (6, h - 7), (w - 7, h - 7), (w // 2, 6), (6, h // 2)]:
        if a.getpixel((x, y)) <= 5:
            trans = (r[0] + x, r[1] + y); break
    cx, cy = (bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2
    ember = None
    for d in range(0, 80, 2):
        for (x, y) in [(cx, cy + d), (cx, cy - d), (cx + d, cy), (cx - d, cy)]:
            if 0 <= x < w and 0 <= y < h and a.getpixel((x, y)) >= 250:
                ember = (r[0] + x, r[1] + y); break
        if ember:
            break
    return trans, ember


def raise_window(h):
    """Above every non-topmost window, without activating it (the owner's other apps may cover the companion)."""
    flags = 0x0001 | 0x0002 | 0x0010  # NOSIZE|NOMOVE|NOACTIVATE
    u32.SetWindowPos(h, W.HWND(-1), 0, 0, 0, 0, flags)   # HWND_TOPMOST
    u32.SetWindowPos(h, W.HWND(-2), 0, 0, 0, 0, flags)   # HWND_NOTOPMOST: stays on top of the normal band
    time.sleep(0.4)


def occluded(h):
    """True if any visible point of the window rect sampled on a grid belongs to a foreign window above it."""
    r = rect(h)
    bad = []
    for fx in (0.1, 0.5, 0.9):
        for fy in (0.1, 0.5, 0.9):
            x, y = int(r[0] + fx * (r[2] - r[0])), int(r[1] + fy * (r[3] - r[1]))
            root = root_at(x, y)
            if root not in (int(h),) and root != 0 and root not in BACKDROP_HWNDS:
                bad.append((x, y, int(root)))
    return bad


def measure(step, hwnd, bd, tag):
    raise_window(hwnd)
    r = rect(hwnd)
    shots = {}
    for c in ("magenta", "green", "black", "white"):
        BACKDROP_HWNDS.add(int(bd.show(c, r, hwnd)))
        raise_window(hwnd)
        occ = occluded(hwnd)
        if occ:
            raise RuntimeError(f"COMPANION_OCCLUDED {occ}")
        shots[c] = grab(r)
        shots[c].save(OUT / f"win-{tag}-{c}.png")
    bd.hide()
    a = alpha_map(shots["magenta"], shots["green"])
    a.save(OUT / f"win-{tag}-alpha.png")
    s = summarize(a)
    ok = (s["transparent_frac"] >= 0.2 and s["opaque_frac"] >= 0.005 and s["blended_frac"] >= 0.002
          and s["edge_alpha_max"] <= 12)
    return a, r, s, ok


def answer(step, req):
    hwnd = find_window(int(req["pid"]))
    if not hwnd:
        return dict(error="WINDOW_NOT_FOUND", pid=req["pid"])
    f = window_facts(hwnd)
    res = dict(window=f, borderless=f["no_nonclient_area"] and f["shadow_frame_px"] == [0, 0, 0, 0],
               borderless_detail=dict(no_nonclient_area=f["no_nonclient_area"], client_size=f["client_size"],
                                      window_size=f["window_size"], style_bits_borderless=f["style_borderless"],
                                      shadow_frame_px=f["shadow_frame_px"],
                                      style=f["style"], exstyle=f["exstyle"], region=f["region_kind"]))
    bd = BD
    tag = step.replace(".", "_")
    if step.startswith("transparent") or step in ("unavailable", "returning"):
        a, r, s, ok = measure(step, hwnd, bd, tag)
        res.update(alpha_summary=s, per_pixel_transparent=ok, rect=r)
        if step == "transparent-1.25":
            bbox = s["silhouette_bbox"]
            res["crop"] = dict(bbox=bbox, window=s["size"],
                               touches_window_edge=bool(bbox) and (bbox[0] <= 1 or bbox[1] <= 1 or bbox[2] >= s["size"][0] - 1 or bbox[3] >= s["size"][1] - 1))
    elif step == "click-through":
        a, r, s, _ = measure(step, hwnd, bd, tag + "-pre")
        trans, ember = pick_points(a, r)
        saved = W.POINT(); u32.GetCursorPos(ctypes.byref(saved))
        bh = bd.show("magenta", r, hwnd)
        n0 = len(bd.clicks)
        res.update(transparent_point=trans, ember_point=ember,
                   root_at_transparent=int(root_at(*trans)) if trans else None,
                   root_at_ember=int(root_at(*ember)) if ember else None, companion=int(hwnd), backdrop=int(bh))
        raise_window(hwnd)
        res.update(root_at_transparent=int(root_at(*trans)) if trans else None,
                   root_at_ember=int(root_at(*ember)) if ember else None)
        skipped = []
        if trans and res["root_at_transparent"] == int(bh):
            click(*trans); time.sleep(0.8)
        elif trans:
            skipped.append("transparent point not over our backdrop")
        n1 = len(bd.clicks)
        # A click on the backdrop activates it and Windows raises it above the companion: raise the companion again
        # and re-check what is under the Ember point before clicking it (run l5 artifact).
        raise_window(hwnd)
        res["root_at_ember"] = int(root_at(*ember)) if ember else None
        if ember and res["root_at_ember"] == int(hwnd):
            click(*ember); time.sleep(0.8)
        elif ember:
            skipped.append("ember point not over the companion window")
        res["input_skipped"] = skipped
        n2 = len(bd.clicks)
        u32.SetCursorPos(saved.x, saved.y)
        bd.hide()
        res.update(outside_reached_backdrop=bool(trans) and n1 > n0 and res["root_at_transparent"] == int(bh),
                   ember_click_reached_uri=bool(ember) and n2 == n1 and res["root_at_ember"] == int(hwnd),
                   backdrop_clicks=[n0, n1, n2])
    elif step == "input-diag":
        a, r, s, _ = measure(step, hwnd, bd, tag + "-pre")
        trans, ember = pick_points(a, r)
        saved = W.POINT(); u32.GetCursorPos(ctypes.byref(saved))
        bh = bd.show("magenta", r, hwnd)
        raise_window(hwnd)
        res.update(ember_point=ember, companion=int(hwnd), backdrop=int(bh))
        if ember and int(root_at(*ember)) in (int(hwnd),):
            lp = (ember[1] << 16) | (ember[0] & 0xFFFF)
            child = u32.WindowFromPoint(W.POINT(*ember))
            u32.SendMessageW.restype = ctypes.c_ssize_t
            res["nchittest_toplevel"] = int(u32.SendMessageW(hwnd, 0x0084, 0, lp))
            res["nchittest_child"] = int(u32.SendMessageW(child, 0x0084, 0, lp))
            res["child_at_point"] = int(child)
            fg_before = int(u32.GetForegroundWindow())
            n0 = len(bd.clicks)
            click(*ember); time.sleep(1.0)
            res["click"] = dict(backdrop_clicks_delta=len(bd.clicks) - n0, clicks=bd.clicks[n0:],
                                foreground_before=fg_before, foreground_after=int(u32.GetForegroundWindow()))
            raise_window(hwnd)
            before = rect(hwnd); n0 = len(bd.clicks)
            u32.SetCursorPos(*ember); time.sleep(0.2)
            u32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.3)
            for i in range(1, 21):
                u32.SetCursorPos(ember[0] - 6 * i, ember[1] + 3 * i); time.sleep(0.04)
            time.sleep(0.3); u32.mouse_event(0x0004, 0, 0, 0, 0); time.sleep(1.0)
            res["drag"] = dict(rect_before=before, rect_after=rect(hwnd), backdrop_clicks_delta=len(bd.clicks) - n0)
        else:
            res["input_skipped"] = "ember point not over the companion window"
        u32.SetCursorPos(saved.x, saved.y)
        bd.hide()
    elif step == "drag":
        a, r, s, _ = measure(step, hwnd, bd, tag + "-pre")
        _, ember = pick_points(a, r)
        saved = W.POINT(); u32.GetCursorPos(ctypes.byref(saved))
        raise_window(hwnd)
        before = rect(hwnd)
        res["root_at_ember"] = int(root_at(*ember)) if ember else None
        if ember and res["root_at_ember"] != int(hwnd):
            res["input_skipped"] = "ember point not over the companion window"
            ember = None
        if ember:
            u32.SetCursorPos(*ember); time.sleep(0.2)
            u32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.15)
            for i in range(1, 21):
                u32.SetCursorPos(ember[0] - 6 * i, ember[1] + 3 * i); time.sleep(0.03)
            time.sleep(0.2); u32.mouse_event(0x0004, 0, 0, 0, 0); time.sleep(1.0)
        after = rect(hwnd)
        u32.SetCursorPos(saved.x, saved.y)
        res.update(ember_point=ember, rect_before=before, rect_after=after,
                   moved=before[:2] != after[:2], delta=[after[0] - before[0], after[1] - before[1]])
    return res


BD = None
BACKDROP_HWNDS = set()


def main():
    global BD
    BD = Backdrop()
    handled = set()
    while not (OUT / "ui-finished.json").exists():
        for p in sorted(OUT.glob("probe-*.json")):
            if p.name.endswith(".done.json") or p.name in handled:
                continue
            req = json.loads(p.read_text())
            step = req["step"]
            try:
                res = answer(step, req)
            except Exception as exc:  # report, never hang the driver
                res = dict(error=repr(exc))
            res["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            (OUT / f"probe-{step}.done.json").write_text(json.dumps(res, indent=1, default=str))
            handled.add(p.name)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
