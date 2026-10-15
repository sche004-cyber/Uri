"""Bring a cut-out reference panel to life (2.5D painted animation).

Input: work/<panel>_layers.npz from layers.py (straight-alpha RGBA cut from the
reference sheet) and the landmarks in rig.json. Every pixel the companion shows
comes from the painting; this module only moves, hides or re-composes them.

Per frame:
  1. Face: lids, gaze and eye scale are re-composed from the panel's own eye
     pixels over a skin plate inpainted from the surrounding head; a mouth can
     be borrowed from another panel of the same sheet (speaking, concern).
  2. One backward displacement field moves the painting:
     - flame flow: tileable turbulence scrolling upward a whole number of tiles
       per loop (seamless loops), weighted by the flame mask, growing toward the
       flame tips;
     - sway: a slow lateral wave travelling up the strands;
     - smoke drift (depleted): slower, wider curls above the head;
     - breathing/bob: everything above the feet rises and falls, feet planted;
     - head tilt: rotation of the head about the neck;
     - puppet handles: soft local offsets (hands).
  3. Light: flame flicker; brightness scale.
  4. Painted sparks are lifted off the panel and float upward, wrapping with a
     fade; extra procedural sparks can be added.
All periodic terms complete whole cycles in the loop, so frame N == frame 0.
"""
import json
import math
import os

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
RIG = json.load(open(f'{HERE}/rig.json'))
TWO_PI = 2 * math.pi


def tile_noise(h, w, scale, seed):
    """Smooth noise in [-1, 1] that tiles in both axes (FFT-filtered)."""
    rng = np.random.default_rng(seed)
    n = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-(fx ** 2 + fy ** 2) * (scale ** 2) * 2 * math.pi ** 2)
    out = np.real(np.fft.ifft2(np.fft.fft2(n) * g))
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def scroll(field, dy):
    """The tiling field shifted up by dy pixels (fractional, wraps)."""
    i = int(math.floor(dy))
    f = dy - i
    return np.roll(field, -i, 0) * (1 - f) + np.roll(field, -i - 1, 0) * f


def nconv(img, m, s):
    """Normalised convolution fill: estimate img where m is False from m."""
    res = None
    got = None
    m = m.astype(np.float32)
    for sg in (s, 2 * s, 4 * s):
        num = ndi.gaussian_filter(img * m[..., None], (sg, sg, 0), mode='nearest')
        den = ndi.gaussian_filter(m, sg, mode='nearest')
        est = num / np.maximum(den[..., None], 1e-6)
        ok = (den > 0.05)[..., None]
        res = est if res is None else np.where(got, res, est)
        got = ok if got is None else (got | ok)
    return res


def ell(xx, yy, cx, cy, rx, ry):
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2


def over(dst, src):
    """Premultiplied source-over."""
    return src + dst * (1 - src[..., 3:4])


class Panel:
    def __init__(self, panel, layers=None):
        self.name = panel
        self.r = RIG[panel]
        z = np.load(layers or f'{HERE}/work/{panel}_layers.npz')
        rgba = z['rgba'].astype(np.float32)
        self.pm = rgba.copy()
        self.pm[..., :3] *= self.pm[..., 3:]
        self.solid = z['solid'].astype(np.float32)
        self.h, self.w = rgba.shape[:2]
        h, w = self.h, self.w
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.yy, self.xx = yy, xx
        hx, hy, hrx, hry = self.r['head']
        q = np.sqrt(ell(xx, yy, hx, hy, hrx, hry))
        self.tip = np.clip((q - 0.85) / 1.2, 0, 1)
        self.nx = [tile_noise(h, w, 9, 11), tile_noise(h, w, 22, 13)]
        self.ny = [tile_noise(h, w, 9, 17), tile_noise(h, w, 22, 19)]
        self.flick = tile_noise(h, w, 30, 23)
        ny_ = self.r['neck'][1]
        fy = max(f[1] for f in self.r['feet'])
        self.lift = np.clip((fy - yy) / max(fy - ny_, 1), 0, 1) ** 1.2
        self.above_neck = np.clip((ny_ + 10 - yy) / 20, 0, 1)
        # everything but the ground light under the figure
        self.air = np.clip((fy + 12 - yy) / 10, 0, 1)
        self._sparks()
        flame = z['flame'].astype(np.float32)
        fl = ndi.gaussian_filter(flame, 2.0)
        solid_soft = ndi.gaussian_filter(self.solid, 2)
        self.flame_w = np.clip(fl * 2.2, 0, 1) * (1 - solid_soft)
        # No turbulence on the ground light around the feet: it dragged the
        # legs along and smeared the ground (checkpoint 2, defect 3).
        feet = np.full((h, w), 1e9, np.float32)
        for fx_, fy_ in self.r['feet']:
            feet = np.minimum(feet, np.hypot(xx - fx_, yy - fy_))
        calm = np.clip((feet - 30) / 40, 0, 1) * np.clip((fy - 8 - yy) / 30, 0, 1)
        self.flame_w *= calm
        a = self.pm[..., 3]
        # translucent, non-luminous matter above the neck: smoke
        self.smoke_w = np.clip(a * 1.5 - fl * 2, 0, 1) * (1 - solid_soft) * self.above_neck
        self.smoke_w = ndi.gaussian_filter(self.smoke_w, 3)
        self._eyes()
        self.bg = z['bg'].astype(np.float32)
        self._z = z
        self._backdrop = None

    @property
    def backdrop(self):
        """The painting behind the character, with its brush texture (V2.1).

        The cut model is src = bg * (1 - a) + F * a, but the cut suppresses
        faint alpha (background brush strokes, distant glow), so those live
        only in src. Solving for what is behind the layer keeps them:
        (src - F * a) / (1 - a). Under near-opaque parts (head, body) that is
        undefined, and the smooth plate bg is used instead. Straight RGB,
        panel pixels."""
        if self._backdrop is None:
            z = self._z
            src = z['src'].astype(np.float32)
            rgba = z['rgba'].astype(np.float32)
            a = rgba[..., 3:4]
            res = (src - rgba[..., :3] * a) / np.maximum(1 - a, 1e-3)
            w = np.clip((0.85 - a) / 0.25, 0, 1)
            self._backdrop = (res * w + self.bg * (1 - w)).clip(0, 1).astype(np.float32)
        return self._backdrop

    # ------------------------------------------------------------ sparks
    def _sparks(self):
        """Lift small isolated luminous blobs (painted sparks) off the base."""
        a = self.pm[..., 3]
        lum = self.pm[..., :3].max(2)
        bright = (a > 0.12) & (lum > 0.35) & (self.solid < 0.5)
        lab, n = ndi.label(bright)
        self.sparks = []
        if n == 0:
            return
        sizes = ndi.sum(bright, lab, range(1, n + 1))
        big = np.isin(lab, 1 + np.where(sizes > 250)[0])
        mass = ndi.binary_dilation(big | (self.solid > 0.5), iterations=7)
        for i in range(1, n + 1):
            if not (3 <= sizes[i - 1] <= 160):
                continue
            m = lab == i
            if (m & mass).any():
                continue
            ys, xs = np.nonzero(m)
            y0, y1 = max(ys.min() - 3, 0), min(ys.max() + 4, self.h)
            x0, x1 = max(xs.min() - 3, 0), min(xs.max() + 4, self.w)
            # The spark sits in painted glow. Only its own light moves; the
            # glow under it is filled from around it, so no hole is left
            # behind (checkpoint 2: dark specks where sparks had been).
            Y0, Y1 = max(y0 - 8, 0), min(y1 + 8, self.h)
            X0, X1 = max(x0 - 8, 0), min(x1 + 8, self.w)
            hole = ndi.binary_dilation(m, iterations=2)[Y0:Y1, X0:X1]
            local = self.pm[Y0:Y1, X0:X1]
            fill = nconv(local, ~hole, 2)
            mm = ndi.gaussian_filter(hole.astype(np.float32), 0.8)
            under = local * (1 - mm[..., None]) + fill * mm[..., None]
            sprite = np.clip(local - under, 0, None)
            self.pm[Y0:Y1, X0:X1] = under
            self.sparks.append((X0, Y0, sprite))

    # -------------------------------------------------------------- face
    def _eyes(self):
        """Skin plate under each eye, eye cut-outs."""
        xx, yy = self.xx, self.yy
        self.eyes = []
        for i, (cx, cy, rx, ry) in enumerate(self.r['eyes']):
            inner = ell(xx, yy, cx, cy, rx + 2, ry + 2) <= 1
            ring = (ell(xx, yy, cx, cy, rx + 9, ry + 9) <= 1) & ~(ell(xx, yy, cx, cy, rx + 4, ry + 4) <= 1)
            ring &= self.pm[..., 3] > 0.95
            skin = nconv(self.pm, ring, 5)
            soft = ndi.gaussian_filter(inner.astype(np.float32), 0.9)
            # side: +1 when the inner corner is at larger x (the left eye)
            other = self.r['eyes'][1 - i][0]
            side = 1.0 if other > cx else -1.0
            self.eyes.append(dict(c=(cx, cy, rx, ry), skin=skin, soft=soft, side=side))

    def face(self, base, f):
        """Re-compose eyes and mouth. f: dict of face params (may be empty)."""
        if not f:
            return base
        out = base
        xx, yy = self.xx, self.yy
        lids = f.get('lid', 0.0)
        tilt = f.get('lid_tilt', 0.0)
        gx, gy = f.get('gaze', (0.0, 0.0))
        es = f.get('eye_scale', 1.0)
        if lids > 0 or gx or gy or es != 1.0:
            for e in self.eyes:
                cx, cy, rx, ry = e['c']
                soft = e['soft']
                eye = out * soft[..., None]
                # plate the socket with skin, then put the (moved) eye back
                out = out * (1 - soft[..., None]) + e['skin'] * soft[..., None]
                if gx or gy or es != 1.0:
                    sx = cx + (xx - cx - gx) / es
                    sy = cy + (yy - cy - gy) / es
                    eye = np.dstack([ndi.map_coordinates(eye[..., c], [sy, sx], order=1) for c in range(4)])
                    ncx, ncy, nrx, nry = cx + gx, cy + gy, rx * es, ry * es
                else:
                    ncx, ncy, nrx, nry = cx, cy, rx, ry
                if lids > 0:
                    out = self._lid(out, eye, e, ncx, ncy, nrx, nry, lids, tilt)
                else:
                    out = over(out, eye)
        if 'mouth' in f:
            out = self.mouth(out, f['mouth'])
        return out

    def _lid(self, out, eye, e, cx, cy, rx, ry, b, tilt):
        xx, yy = self.xx, self.yy
        u = np.clip((xx - cx) / rx, -1, 1)
        top = cy - ry
        closed = b >= 0.999
        if closed:
            yl = np.full_like(xx, cy + 0.35 * ry) + 0.18 * ry * (1 - u ** 2)
        else:
            yl = (top + 2 * ry * b - tilt * e['side'] * u * 0.5 * ry
                  + 0.18 * ry * (1 - u ** 2) * min(b * 3, 1))
        inside = ell(xx, yy, cx, cy, rx + 2, ry + 2) <= 1
        show = np.clip((yy - yl) / 1.2, 0, 1) * (0 if closed else 1)
        out = over(out, eye * show[..., None])
        # lid crease shading just above the lid line, lash line on it
        d = yy - yl
        # lid surface: a light overall shade (it is a lid, not bare skin) and a
        # darker band towards its edge, as the depleted panel paints its lids
        lid = (d < 0) * inside
        shade = lid * (0.07 + 0.22 * np.exp(-np.clip(-d, 0, None) / 4.0))
        out[..., :3] *= (1 - shade[..., None])
        lash = np.exp(-(d ** 2) / (2 * 0.9 ** 2)) * (ell(xx, yy, cx, cy, rx + 1, ry + 1.5) <= 1)
        lash = ndi.gaussian_filter(lash, 0.4) * 0.92
        col = np.array([0.10, 0.06, 0.045], np.float32)
        out[..., :3] = out[..., :3] * (1 - lash[..., None]) + col * lash[..., None] * out[..., 3:4]
        return out

    def mouth(self, out, m):
        """Paste a mouth borrowed from a panel: m = dict(src, at, scale, open)."""
        src = MOUTHS.get(m['src'])
        if src is None:
            src = MOUTHS[m['src']] = mouth_patch(m['src'])
        patch, (pcx, pcy) = src
        mx, my = m['at']
        s = m.get('scale', 1.0)
        op = max(m.get('open', 1.0), 0.08)
        sx = pcx + (self.xx - mx) / s
        sy = pcy + (self.yy - my) / (s * op)
        layer = np.dstack([ndi.map_coordinates(patch[..., c], [sy, sx], order=1, cval=0) for c in range(4)])
        return over(out, layer * m.get('alpha', 1.0))

    # -------------------------------------------------------------- motion
    def field(self, t, p):
        """Backward displacement: content at p moves by (dx, dy)."""
        h, w = self.h, self.w
        dx = np.zeros((h, w), np.float32)
        dy = np.zeros((h, w), np.float32)
        amp = self.flame_w * (p.get('flow_base', 1.0) + p.get('flow_tip', 6.0) * self.tip)
        for i, k in enumerate(p.get('flow_tiles', [1, 2])):
            s = t * k * h
            g = 0.65 if i else 1.0
            dx += amp * scroll(self.nx[i], s) * g
            dy += amp * scroll(self.ny[i], s) * g * 0.6
        if p.get('smoke', 0) > 0:
            sa = self.smoke_w * p['smoke'] * (3 + 9 * self.tip)
            s = t * h
            dx += sa * scroll(self.nx[1], s)
            dy += sa * scroll(self.ny[1], s) * 0.5
        sp = p.get('sway_px', 4.0)
        if sp:
            dx += sp * self.flame_w * self.tip * np.sin(TWO_PI * t * p.get('sway_cycles', 1) + self.yy / 60.0)
        # Thin far strokes must not travel further than they are wide, or the
        # backdrop shows through and they change colour (checkpoint 3: the
        # fierce crest turned maroon). One cap over all flame motion
        # (turbulence, smoke and sway; checkpoint 6 measured 10-12 px when the
        # sway was added after the cap).
        mag = np.sqrt(dx * dx + dy * dy)
        cap = p.get('flow_cap', 6.0)
        k = np.minimum(1.0, cap / np.maximum(mag, 1e-6))
        dx *= k
        dy *= k
        # breathing / bob
        b = p.get('bob_px', 2.0)
        if b:
            cyc = p.get('bob_cycles', 1)
            if p.get('hop'):
                v = b * (1 - math.cos(TWO_PI * t * cyc)) / 2
            else:
                v = b * math.sin(TWO_PI * t * cyc)
            # airborne (joyful leaps): the whole figure moves as one, nothing
            # stretches; otherwise the feet stay planted and the body above
            # them breathes (checkpoint 6: leg stretch read as pose jumps)
            dy += -v * (self.air if p.get('airborne') else self.lift)
        # head tilt about the neck (static + oscillation)
        th = math.radians(p.get('tilt_deg', 0.0) + p.get('tilt_osc', 0.0) * math.sin(TWO_PI * t))
        if th:
            nx_, ny_ = self.r['neck']
            ang = th * self.above_neck
            qx = nx_ + np.cos(-ang) * (self.xx - nx_) - np.sin(-ang) * (self.yy - ny_)
            qy = ny_ + np.sin(-ang) * (self.xx - nx_) + np.cos(-ang) * (self.yy - ny_)
            dx += self.xx - qx
            dy += self.yy - qy
        for hd in p.get('handles', []):
            x, y = self.r['hands'][hd['hand']]
            ph = TWO_PI * (t * hd.get('cycles', 1) + hd.get('phase', 0))
            g = np.exp(-((self.xx - x) ** 2 + (self.yy - y) ** 2) / (2 * hd.get('sigma', 22) ** 2))
            dx += g * hd.get('dx', 0) * math.sin(ph)
            dy += g * hd.get('dy', 0) * math.sin(ph)
        return dx, dy

    def warp(self, img, dx, dy):
        coords = [self.yy - dy, self.xx - dx]
        if img.ndim == 2:
            return ndi.map_coordinates(img, coords, order=1, mode='constant')
        return np.dstack([ndi.map_coordinates(img[..., c], coords, order=1, mode='constant')
                          for c in range(img.shape[2])])

    def frame(self, t, p, face=None):
        """Premultiplied RGBA frame at loop phase t in [0, 1)."""
        base = self.face(self.pm.copy(), face or {})
        dx, dy = self.field(t, p)
        out = self.warp(base, dx, dy)
        fw = self.warp(self.flame_w, dx, dy)
        fl = 1 + p.get('flicker', 0.1) * scroll(self.flick, t * 2 * self.h) * fw
        gain = fl * (1 + (p.get('bright', 1.0) - 1) * fw)
        out[..., :3] *= gain[..., None]
        out = self.float_sparks(out, t, p)
        out = extra_sparks(out, t, p, self)
        self.last_field = (dx, dy)
        return np.clip(out, 0, None)

    def float_sparks(self, out, t, p):
        rise = p.get('spark_rise', 60.0)
        rng = np.random.default_rng(7)
        for (x0, y0, spr) in self.sparks:
            u0 = rng.uniform(0.2, 0.8)
            speed = rng.uniform(0.6, 1.4)
            wig = rng.uniform(2, 6)
            ph = rng.uniform(0, TWO_PI)
            u = (u0 + t * p.get('spark_cycles', 1)) % 1.0
            if rise == 0:
                oy, ox, a = 0.0, 0.0, 1.0
            else:
                a = min(u / 0.15, 1.0, (1 - u) / 0.15)
                oy = -rise * speed * (u - u0)
                ox = wig * math.sin(TWO_PI * u * 2 + ph) - wig * math.sin(TWO_PI * u0 * 2 + ph)
            hh, ww = spr.shape[:2]
            fx, fy = x0 + ox, y0 + oy
            ix, iy = int(math.floor(fx)), int(math.floor(fy))
            sh = ndi.shift(spr, (fy - iy, fx - ix, 0), order=1)
            ya, yb = max(iy, 0), min(iy + hh, self.h)
            xa, xb = max(ix, 0), min(ix + ww, self.w)
            if yb <= ya or xb <= xa:
                continue
            piece = sh[ya - iy:yb - iy, xa - ix:xb - ix] * a
            out[ya:yb, xa:xb] = over(out[ya:yb, xa:xb], piece)
        return out


MOUTHS = {}


def mouth_patch(panel):
    """Cut a panel's mouth: pixels that differ from the inpainted skin around it."""
    r = RIG[panel]
    z = np.load(f'{HERE}/work/{panel}_layers.npz')
    rgba = z['rgba'].astype(np.float32)
    pm = rgba.copy()
    pm[..., :3] *= pm[..., 3:]
    mx, my = r['mouth'][:2]
    rx, ry = (r['mouth'][2], r['mouth'][3]) if len(r['mouth']) > 2 else (11, 6)
    h, w = pm.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    inner = ell(xx, yy, mx, my, rx + 3, ry + 3) <= 1
    ring = (ell(xx, yy, mx, my, rx + 8, ry + 8) <= 1) & ~inner
    skin = nconv(pm, ring, 4)
    diff = np.sqrt(((pm[..., :3] - skin[..., :3]) ** 2).sum(2))
    m = np.clip((diff - 0.04) / 0.12, 0, 1) * (ell(xx, yy, mx, my, rx + 2, ry + 2) <= 1)
    m = ndi.gaussian_filter(m, 0.7)
    return pm * m[..., None], (mx, my)


def extra_sparks(pm, t, p, panel):
    n = p.get('sparks', 0)
    if n <= 0:
        return pm
    h, w = panel.h, panel.w
    rng = np.random.default_rng(101)
    hx, hy, hrx, hry = panel.r['head']
    for _ in range(n):
        ph = rng.random()
        life = 0.45 + 0.4 * rng.random()
        ang = rng.uniform(-2.7, -0.45)
        rr = rng.uniform(0.6, 1.25)
        drift = rng.uniform(-25, 25)
        sp = rng.uniform(0.6, 1.3)
        amp_a = rng.uniform(0.5, 1.0)
        rad = rng.uniform(0.7, 1.5)
        u = ((t * p.get('spark_cycles', 1) + ph) % 1.0) / life
        if u >= 1:
            continue
        x = hx + math.cos(ang) * hrx * rr + drift * u + 5 * math.sin(6 * u + ph * 6)
        y = hy + math.sin(ang) * hry * rr - p.get('spark_rise', 60) * 1.4 * u * sp
        a = math.sin(math.pi * u) ** 1.5 * amp_a
        x0i, x1i = int(max(x - 4, 0)), int(min(x + 5, w))
        y0i, y1i = int(max(y - 4, 0)), int(min(y + 5, h))
        if x1i <= x0i or y1i <= y0i:
            continue
        yy, xx = np.mgrid[y0i:y1i, x0i:x1i]
        g = (np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * rad ** 2)) * a).astype(np.float32)
        col = np.array([1.0, 0.70, 0.32], np.float32) * g[..., None]
        pm[y0i:y1i, x0i:x1i] = over(pm[y0i:y1i, x0i:x1i], np.dstack([col, g * 0.85]))
    return pm
