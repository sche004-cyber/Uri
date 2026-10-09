"""Measures what each companion state actually changes in the captured frames.

For every state frame: mean luminance of the companion body (inner disc),
mean luminance of its atmosphere (ring outside the body), and a detail score
(mean absolute Laplacian inside the body). The detail score is the check on
the brief's warning against "making the entire image uniformly darker or
brighter if doing so destroys important visual details": a state may change
brightness, but its body detail should stay close to idle's.

Run: python rnd/voice/state_metrics.py <capture dir> [scaled]
Pass `scaled` for captures made after the companion was enlarged to its box
(presenceScale in companion_presence.dart); the body then occupies
bodyRadius * scale of the layout half-side.
"""
import os
import sys
import numpy as np
from PIL import Image

D = sys.argv[1]
SCALED = len(sys.argv) > 2 and sys.argv[2] == 'scaled'
IDS = {'solar': 0.38, 'sakura': 0.30, 'lunar': 0.33, 'moonlit': 0.32}
STATES = ['idle', 'listening', 'thinking', 'working', 'awaitingApproval',
          'awaitingApproval_pulse', 'success', 'error', 'unavailable']


def metrics(path, body_r):
    im = np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255
    lum = im @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    h, w = lum.shape
    # The companion square is centred in the area above the status line.
    status = 46 * 2
    area = h - status
    s = min(w, area)
    cy, cx = area / 2, w / 2
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(yy - cy, xx - cx) / (s / 2)
    k = min(max(0.50 / body_r, 1.0), 1.4) if SCALED else 1.0
    body = r < body_r * k * 0.85
    atmo = (r > body_r * k * 1.15) & (r < 0.95)
    lap = np.abs(4 * lum[1:-1, 1:-1] - lum[:-2, 1:-1] - lum[2:, 1:-1]
                 - lum[1:-1, :-2] - lum[1:-1, 2:])
    return (lum[body].mean(), lum[atmo].mean(), lap[body[1:-1, 1:-1]].mean())


rows = []
for i, br in IDS.items():
    base = None
    for st in STATES:
        p = os.path.join(D, f'state_{i}_{st}.png')
        b, a, d = metrics(p, br)
        if base is None:
            base = (b, a, d)
        rows.append((i, st, b, a, d, b / base[0], a / base[1], d / base[2]))

print(f"{'identity':8} {'state':24} {'body':>6} {'atmo':>6} {'detail':>7}"
      f" {'body/idle':>9} {'atmo/idle':>9} {'detail/idle':>11}")
for r in rows:
    print(f'{r[0]:8} {r[1]:24} {r[2]:6.3f} {r[3]:6.3f} {r[4]:7.4f}'
          f' {r[5]:9.2f} {r[6]:9.2f} {r[7]:11.2f}')
