"""Cut each reference panel into a straight-alpha RGBA layer stack.

Model: pixel = bg * (1 - a) + F * a. The background plate bg is estimated by
normalised convolution from the area around the character; the smallest
alpha that keeps F inside [0, 1] gives the luminous parts (flames, glow,
sparks) their soft painted transparency. Head, eyes and body are forced
opaque from the rig ellipses and the dark-body mask so they read as solid on
any app background. Output: work/<state>_layers.npz (rgba, masks, bg).
"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = f'{HERE}/../../docs/companions/fire/reference/uri_emotions_sheet.png'
RIG = json.load(open(f'{HERE}/rig.json'))


def nconv(c, m, s):
    res = None; ok_any = None
    for sg in (s, 2 * s, 4 * s, 8 * s):
        num = ndi.gaussian_filter(c * m[..., None], (sg, sg, 0), mode='nearest')
        den = ndi.gaussian_filter(m.astype(np.float32), sg, mode='nearest')
        est = num / np.maximum(den[..., None], 1e-6); ok = (den > 0.05)[..., None]
        res = est if res is None else np.where(ok_any, res, est)
        ok_any = ok if ok_any is None else (ok_any | ok)
    return res


def ellipse(h, w, e, grow=0.0):
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy, rx, ry = e
    return ((xx - cx) / (rx + grow)) ** 2 + ((yy - cy) / (ry + grow)) ** 2 <= 1


def erase(c, rects):
    for x0, y0, x1, y1 in rects:
        m = np.zeros(c.shape[:2], bool); m[y0:y1, x0:x1] = True
        ring = ndi.binary_dilation(m, iterations=6) & ~m
        fill = nconv(c, ring, 6)
        c[m] = fill[m]
    return c


def background(c):
    h, w, _ = c.shape
    bg = nconv(c, np.ones((h, w)), 60)
    keep = None
    for _ in range(3):
        d = np.sqrt(((c - bg) ** 2).sum(2))
        m = ndi.binary_dilation(ndi.gaussian_filter(d, 2) > 0.08, iterations=6)
        lab, n = ndi.label(m); sizes = ndi.sum(m, lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.where(sizes > 3000)[0])
        keep = ndi.binary_fill_holes(ndi.binary_dilation(keep, iterations=10))
        bg = np.where(keep[..., None], nconv(c, ~keep, 25), ndi.gaussian_filter(c, (4, 4, 0)))
        bg = ndi.gaussian_filter(bg, (6, 6, 0))
    return bg, keep


def cut(state):
    r = RIG[state]; x0, y0, x1, y1 = r['crop']
    im = np.asarray(Image.open(SHEET).convert('RGB')).astype(np.float32) / 255
    c = erase(im[y0:y1, x0:x1].copy(), r['erase'])
    h, w, _ = c.shape
    bg, keep = background(c)
    up = ((c - bg) / np.maximum(1 - bg, 1e-3)).max(2).clip(0, 1)
    dn = ((bg - c) / np.maximum(bg, 1e-3)).max(2).clip(0, 1)
    # Opaque parts: head ellipse, eyes, and the dark body below the head.
    head = ellipse(h, w, r['head'])
    body = (dn > 0.22) | (ndi.gaussian_filter(dn, 1.5) > 0.18)
    body &= ~ellipse(h, w, r['head'], grow=-4)
    nx, ny = r['neck']
    lab, n = ndi.label(ndi.binary_closing(body, iterations=1))
    # keep dark components that touch the region from neck to feet
    zone = np.zeros((h, w), bool)
    fy = max(f[1] for f in r['feet'])
    zone[ny - 6:fy + 6, :] = True
    ids = [i for i in range(1, n + 1) if (lab[zone] == i).sum() > 40]
    body = np.isin(lab, ids) & zone
    filled = ndi.binary_fill_holes(ndi.binary_closing(body, iterations=2))
    if r.get('solid_robe'):
        # The depleted robe is pale grey, close to the background: inside its
        # painted outline it is cloth, not glass (checkpoint 7: "ghostly").
        body = filled
    else:
        body = filled & (dn > 0.06)
    solid = head | body
    for e in r['eyes']:
        solid |= ellipse(h, w, e, grow=2)
    # "Darker than the background" is character only near the body and in
    # painted smoke (rig 'smoke' box); elsewhere it is background brush
    # texture, which on the app's near-black canvas turns into dark specks
    # and rings (checkpoint 2, defect 2).
    dark_ok = ndi.binary_dilation(solid, iterations=6)
    if 'smoke' in r:
        x0s, y0s, x1s, y1s = r['smoke']
        dark_ok[y0s:y1s, x0s:x1s] = True
    dark_ok = ndi.gaussian_filter(dark_ok.astype(np.float32), 3)
    a = np.maximum(up, dn * dark_ok)
    # Suppress background brush texture: soft floor, smooth the faint glow
    # (texture speckle lives there), fade with distance from the character.
    a = a * np.clip((a - 0.05) / 0.12, 0, 1)
    # ...but never on painted sparks: small bright blobs keep their full
    # alpha (checkpoint 7: joyful's chunky embers had become fine dust).
    lum = c.max(2)
    lab_s, n_s = ndi.label((up > 0.12) & (lum > 0.45))
    sizes = ndi.sum(np.ones_like(up), lab_s, range(1, n_s + 1)) if n_s else []
    spark = np.isin(lab_s, 1 + np.where((np.asarray(sizes) >= 3) & (np.asarray(sizes) <= 160))[0])
    spark = ndi.binary_dilation(spark, iterations=2)
    a = np.where((a < 0.3) & ~spark, np.minimum(a, ndi.gaussian_filter(a, 1.5)), a)
    near = ndi.gaussian_filter(keep.astype(np.float32), 12)
    a = a * np.clip(near * 1.6, 0, 1)
    # Never a hard edge at the crop border (checkpoint 2, defect 1).
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum.reduce([xx, w - 1 - xx, yy, h - 1 - yy]).astype(np.float32)
    a = a * np.clip(edge / 24.0, 0, 1)
    soft = ndi.gaussian_filter(solid.astype(np.float32), 0.8)
    alpha = np.maximum(a, soft).clip(0, 1)
    F = (c - bg * (1 - alpha[..., None])) / np.maximum(alpha[..., None], 1e-3)
    F = F.clip(0, 1)
    # Luminous weight: how much of each pixel is flame light (for flow warp,
    # flicker and bloom). Solid head core keeps a little so its rim glows.
    lum = (up * (1 - 0.85 * soft)).clip(0, 1)
    flame = lum * ~head * ~body
    return dict(rgba=np.dstack([F, alpha]).astype(np.float32), bg=bg.astype(np.float32),
                solid=soft.astype(np.float32), body=body, head=head, flame=flame.astype(np.float32), src=c)


if __name__ == '__main__':
    states = sys.argv[1:] or list(k for k in RIG if not k.startswith('_'))
    for s in states:
        L = cut(s)
        np.savez_compressed(f'{HERE}/work/{s}_layers.npz', **L)
        print(s, L['rgba'].shape, 'alpha>0.02:', round(float((L['rgba'][..., 3] > 0.02).mean()), 3))
