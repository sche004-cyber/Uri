"""Bakes the lunar surface to a reusable texture, with no game engine involved.

This exists to answer one question from the Unreal Engine brief directly:
"evaluate whether expensive effects can be baked into reusable assets while
preserving live state-driven animation".

The lunar albedo is the best candidate in the whole companion set, because it
is the only field that is genuinely static. The moon's surface does not move,
does not react to URI's state, and is sampled by every fragment inside the
disc. Everything animated - cloud advection, moonlight, petals, plasma - stays
procedural, so the live, state-driven part of the companion is untouched.

The point of doing it here rather than in Unreal is that the output is the same
kind of artifact an engine bake would produce (a tiled albedo map), for a 90
line script and no install. If this closes the quality gap, the engine is not
buying anything for this particular asset.

Writes a 1024x1024 single-channel PNG.
"""
import numpy as np
from PIL import Image

RES = 1024
rng = np.random.default_rng(20261009)


def _grads(n):
    a = rng.random((n, n)) * 2.0 * np.pi
    return np.cos(a), np.sin(a)


def gnoise(x, y, period):
    """Periodic gradient noise, so the baked tile has no visible seam."""
    gx, gy = _grads(period)
    xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
    xf, yf = x - xi, y - yi
    u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
    v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)

    def dot(ix, iy, dx, dy):
        i, j = (xi + ix) % period, (yi + iy) % period
        return gx[i, j] * dx + gy[i, j] * dy

    n00 = dot(0, 0, xf, yf)
    n10 = dot(1, 0, xf - 1, yf)
    n01 = dot(0, 1, xf, yf - 1)
    n11 = dot(1, 1, xf - 1, yf - 1)
    return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v


def fbm(X, Y, base, octaves, gain=0.5):
    total = np.zeros_like(X)
    amp, freq = 0.5, base
    for _ in range(octaves):
        total += amp * gnoise(X * freq, Y * freq, int(freq))
        freq *= 2
        amp *= gain
    return total


def craters(X, Y, cells, density, depth, seed):
    """Sparse craters, lit from -x.

    The first bake drew a full bright ring per crater and they read as bubbles.
    A real crater under low sun is a bright crescent on one rim, a dark
    crescent on the other, and a floor that is brighter on the far wall - it is
    almost entirely a directional effect, and symmetry is what kills it.
    """
    r = np.random.default_rng(seed)
    out = np.zeros_like(X)
    px, py = X * cells, Y * cells
    ix, iy = np.floor(px).astype(int), np.floor(py).astype(int)
    fx, fy = px - ix, py - iy
    have = r.random((cells, cells)) < density
    rad = 0.10 + r.random((cells, cells)) ** 2 * 0.34
    offx = r.random((cells, cells))
    offy = r.random((cells, cells))
    strength = 0.45 + r.random((cells, cells)) * 0.75
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            i, j = (ix + di) % cells, (iy + dj) % cells
            m = have[i, j]
            rr = np.maximum(rad[i, j], 1e-4)
            dx = (di + offx[i, j] - fx) / rr
            dy = (dj + offy[i, j] - fy) / rr
            d = np.sqrt(dx * dx + dy * dy)
            # Thin wall, split into a lit side and a shadowed side.
            wall = np.exp(-((d - 0.92) * 9.0) ** 2)
            side = np.clip(dx / np.maximum(d, 1e-4), -1, 1)
            inner = np.clip((0.86 - d) / 0.80, 0, 1) ** 1.3
            # Floor: shadowed on the near wall, catching light on the far one.
            floor = inner * (0.30 - 0.52 * side)
            val = (wall * side * 0.9 - floor) * depth * strength[i, j]
            out += np.where(m, val, 0.0)
    return out


def main():
    g = (np.arange(RES) + 0.5) / RES
    X, Y = np.meshgrid(g, g, indexing='xy')

    # Maria: large, smooth, dark basalt plains. These carry the recognition.
    maria_n = fbm(X, Y, 3, 5)
    maria = np.clip((0.10 - maria_n) / 0.26, 0, 1) ** 1.2
    base = 1.00 - 0.56 * maria

    # Highland mottling.
    base *= 0.88 + 0.24 * (fbm(X, Y, 8, 4) * 0.5 + 0.5)

    # Three crater scales. The shader could only afford two coarse ones and a
    # 3x3 neighbourhood each; here the count is free.
    base += craters(X, Y, 8, 0.40, 0.34, 11)
    base += craters(X, Y, 20, 0.26, 0.22, 23)
    base += craters(X, Y, 52, 0.16, 0.13, 37)
    base += craters(X, Y, 128, 0.09, 0.07, 41)

    # Fine regolith grain.
    base += (fbm(X, Y, 64, 3)) * 0.05

    img = np.clip(base, 0.04, 1.30) / 1.30
    out = (img * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(out, mode='L').save('moon_albedo.png', optimize=True)
    print('wrote moon_albedo.png', out.shape, 'min', out.min(), 'max', out.max())


if __name__ == '__main__':
    main()
