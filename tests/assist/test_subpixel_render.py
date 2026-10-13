"""ClearType evidence must bind each RGB subpixel to both independent paints."""
from collections import Counter

import pytest

from uri_assist import onscreen as O
from . import test_a0_r13_differential_render as R

PAL = [[146, 219, 9], [9, 219, 188], [82, 9, 219], [219, 9, 40]]
PAL2 = [[9, 93, 219], [219, 9, 198], [219, 135, 9], [9, 219, 30]]


def blend(colour, coverage):
    return tuple(round(255 + a * (p - 255)) for p, a in zip(colour, coverage))


@pytest.fixture
def capture(monkeypatch):
    monkeypatch.setattr(R, "PAL", PAL)
    monkeypatch.setattr(R, "PAL2", PAL2)

    def make(coverage=(0.4, 0.8, 1.0), *, mode="own"):
        def paint(palette):
            def draw(d, i, rect, colour):
                if i == 0 and mode == "foreign": colour = palette[1]
                if i == 0 and mode == "inconsistent" and palette is PAL2:
                    cov = (1.0, 0.4, 0.4)
                else:
                    cov = coverage
                if i == 0 and mode == "clipped":
                    x, y, w, h = rect
                    rect = (x, y, w // 3, h)
                R._glyphs(d, rect, blend(colour, cov))
            return draw
        base = lambda d, i, rect: R._glyphs(d, rect, blend((0, 0, 0), coverage))
        snap, probe = R.synthetic(R.TWO, base_ink=base, tint=paint(PAL), tint2=paint(PAL2))
        if mode == "undrawn": probe["plain"] = probe["base"] = probe["base2"] = R._png(lambda d: None)
        if mode == "decorated": probe["base"] = probe["base2"] = R._png(lambda d: None)
        return snap, probe
    return make


def test_subpixel_coverage_keeps_visible_own_glyphs(capture):
    assert R._kept(*capture()) == ([0, 1], Counter())


def test_subpixel_channels_are_fractional_pixels_not_three_whole_pixels(capture):
    snap, raw = capture((0.2, 0.6, 1.0))
    probe = O.load(raw, snap)
    tinted, inked, _, _, _ = probe._counts(*probe.where[0], probe.units[0]["r"][0])
    # 40 two-pixel strokes, 14 rows; only two of three channels meet unchanged MIN_ALPHA.
    assert tinted == pytest.approx(1120 * 2 / 3)
    assert inked == pytest.approx(tinted)
    assert R._kept(snap, raw) == ([0, 1], Counter())


@pytest.mark.parametrize("mode", ["foreign", "inconsistent", "clipped"])
def test_subpixel_branch_refuses_foreign_inconsistent_or_partially_drawn_units(capture, mode):
    assert R._kept(*capture(mode=mode)) == ([1], Counter({"no_ink": 1}))


@pytest.mark.parametrize("mode", ["undrawn", "decorated"])
def test_subpixel_tints_do_not_replace_actual_visible_undecorated_ink(capture, mode):
    reason = "decorated" if mode == "decorated" else "no_ink"
    assert R._kept(*capture(mode=mode)) == ([], Counter({reason: 2}))


def test_low_opacity_subpixels_cannot_meet_the_unchanged_alpha_bound(capture):
    assert R._kept(*capture((0.01, 0.1, 0.2))) == ([], Counter({"no_ink": 2}))


def test_subpixel_branch_requires_measurable_contrast_in_every_channel(capture):
    snap, raw = capture()
    probe = O.load(raw, snap)
    for palette in probe.palettes:
        palette[0] = (255, *palette[0][1:])  # no contrast against the white clear shot in R
    assert probe.verify(0) == O.NO_INK
