"""Render Ember V2 clips (expressions.json) to frames.

Usage: python render_clips.py [clip ...] [--preview]
  frames -> work/frames/<clip>/NNN.npz (premultiplied RGBA in panel pixels,
  plus the per-frame eye offsets for the blink overlay)
  --preview -> work/preview_<clip>.jpg (8 frames on the app canvas colour)
"""
import json, math, os, sys
import numpy as np
from PIL import Image
from animate import Panel, HERE, TWO_PI

EXPR = json.load(open(f'{HERE}/expressions.json'))
CANVAS = np.array([0x13, 0x0F, 0x0B], np.float32) / 255  # Solar Ember surface


def face_at(face, t):
    f = dict(face)
    if 'talk' in f and 'mouth' in f:
        cyc = f.pop('talk')
        v = sum(abs(math.sin(math.pi * c * t + i)) for i, c in enumerate(cyc)) / len(cyc)
        m = dict(f['mouth']); m['open'] = 0.15 + 0.85 * v
        f['mouth'] = m
    return f


PANELS = {}


def render(name, store=True, every=1):
    c = EXPR['clips'][name]
    pn = PANELS.get(c['panel']) or PANELS.setdefault(c['panel'], Panel(c['panel']))
    n = c['loop']
    frames = []
    for i in range(0, n, every):
        t = i / n
        fr = pn.frame(t, c['motion'], face_at(c.get('face', {}), t))
        dx, dy = pn.last_field
        eyes = [[float(dx[int(e[1]), int(e[0])]), float(dy[int(e[1]), int(e[0])])] for e in pn.r['eyes']]
        frames.append((fr, eyes))
        if store:
            d = f'{HERE}/work/frames/{name}'; os.makedirs(d, exist_ok=True)
            np.savez_compressed(f'{d}/{i:03d}.npz', pm=fr.astype(np.float16), eyes=np.array(eyes))
    return frames


def preview(name, frames):
    tiles = []
    for fr, _ in frames:
        rgb = fr[..., :3] + CANVAS * (1 - fr[..., 3:])
        tiles.append((rgb.clip(0, 1) * 255).astype(np.uint8))
    sheet = np.concatenate(tiles, 1)
    Image.fromarray(sheet).save(f'{HERE}/work/preview_{name}.jpg', quality=90)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    names = args or list(EXPR['clips'])
    for nm in names:
        if '--preview' in sys.argv:
            n = EXPR['clips'][nm]['loop']
            preview(nm, render(nm, store=False, every=n // 4))
        else:
            render(nm)
        print(nm, 'ok', flush=True)
