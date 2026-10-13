"""ClearType evidence must bind each RGB subpixel to both independent paints."""
from collections import Counter

import pytest

from uri_assist import onscreen as O
from . import test_a0_r13_differential_render as R

PAL = [[146, 219, 9], [9, 219, 188], [82, 9, 219], [219, 9, 40]]
PAL2 = [[9, 93, 219], [219, 9, 198], [219, 135, 9], [9, 219, 30]]


def blend(colour, coverage):
    # Independent gamma-2.2 renderer fixture, close to sRGB but not a copy of
    # the production transfer function. Coverage is in light, not encoded bytes.
    return tuple(round(255 * (1 - a + a * (p / 255) ** 2.2) ** (1 / 2.2)) for p, a in zip(colour, coverage))


@pytest.fixture
def capture(monkeypatch):
    monkeypatch.setattr(R, "PAL", PAL)
    monkeypatch.setattr(R, "PAL2", PAL2)

    def make(coverage=(0.4, 0.8, 1.0), *, mode="own", first_red=None, arbitrary_red=None, secondary=None):
        first = [list(c) for c in PAL]
        second = [list(c) for c in PAL2]
        if first_red is not None: first[0][0] = first_red
        if mode == "alias":
            first[1] = [9, first[0][1], first[0][2]]
            second[1] = [219, second[0][1], second[0][2]]
        monkeypatch.setattr(R, "PAL", first)
        monkeypatch.setattr(R, "PAL2", second)
        def paint(palette):
            def draw(d, i, rect, colour):
                if i == 0 and mode in ("foreign", "alias"): colour = palette[1]
                if i == 0 and mode == "inconsistent" and palette is second:
                    cov = (1.0, 0.4, 0.4)
                else:
                    cov = secondary if i == 1 and secondary is not None else coverage
                if i == 0 and mode == "clipped":
                    x, y, w, h = rect
                    rect = (x, y, w // 3, h)
                pixel = list(blend(colour, cov))
                if i == 0 and palette is first and arbitrary_red is not None:
                    pixel[0] = arbitrary_red
                R._glyphs(d, rect, pixel)
            return draw
        base = lambda d, i, rect: R._glyphs(d, rect, blend((0, 0, 0), secondary if i == 1 and secondary is not None else coverage))
        snap, probe = R.synthetic(R.TWO, base_ink=base, tint=paint(first), tint2=paint(second))
        if mode == "undrawn": probe["plain"] = probe["base"] = probe["base2"] = R._png(lambda d: None)
        if mode == "decorated": probe["base"] = probe["base2"] = R._png(lambda d: None)
        return snap, probe
    return make


def test_subpixel_coverage_keeps_visible_own_glyphs(capture):
    assert R._kept(*capture()) == ([0, 1], Counter())


def test_subpixel_channels_are_fractional_pixels_not_three_whole_pixels(capture):
    snap, raw = capture((0.2, 0.6, 1.0), secondary=(0.4, 0.8, 1.0))
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


@pytest.mark.parametrize("first_red", [255, 254, 246, 242])
def test_one_flat_or_low_contrast_paint_cannot_absorb_arbitrary_residual_data(capture, first_red):
    # Exact independent-review reproduction: the first red paint may be flat
    # against white, yet the old joint-energy test admitted arbitrary delta -28.
    # Also cover near-flat data and a measurable but low-contrast paint, whose
    # residual allowance must scale down rather than retain the full 28 bytes.
    assert R._kept(*capture(first_red=first_red, arbitrary_red=227)) == ([1], Counter({"no_ink": 1}))


def test_lower_contrast_paint_must_still_supply_correlated_coverage(capture):
    # Contrast 13 can supply a measured response of 13, with independently
    # agreeing gamma-corrected coverage. It cannot absorb arbitrary delta -28.
    assert R._kept(*capture((1.0, 0.8, 0.4), first_red=242)) == ([0, 1], Counter())


@pytest.mark.parametrize("first_red_pixel", [227, 255])
def test_independent_review_zero_contrast_reproduction_is_refused(monkeypatch, first_red_pixel):
    # Preserve the reviewer's exact encoded-byte counterexample independently of
    # the gamma-rendered positive fixture. Both arbitrary -28 and flat 0 fail.
    monkeypatch.setattr(R, "PAL", [[255, 219, 9], *PAL[1:]])
    monkeypatch.setattr(R, "PAL2", PAL2)
    cov = (0.4, 0.8, 1.0)
    def paint(palette):
        def draw(d, i, rect, colour):
            pixel = [round(255 + a * (p - 255)) for p, a in zip(colour, cov)]
            if i == 0 and palette is R.PAL: pixel[0] = first_red_pixel
            R._glyphs(d, rect, pixel)
        return draw
    snap, raw = R.synthetic(R.TWO, tint=paint(R.PAL), tint2=paint(R.PAL2))
    probe = O.load(raw, snap)
    assert probe is not None
    assert probe.verify(0) == O.NO_INK
    assert 0 not in R._kept(snap, raw)[0]


def test_weak_channel_has_zero_weight_without_erasing_two_proved_channels(capture):
    snap, raw = capture((0.2, 0.6, 1.0), first_red=242, secondary=(0.4, 0.8, 1.0))
    probe = O.load(raw, snap)
    tinted, inked, _, _, _ = probe._counts(*probe.where[0], probe.units[0]["r"][0])
    assert tinted == pytest.approx(1120 * 2 / 3)  # unmeasurable red supplies NO weight
    assert inked == pytest.approx(tinted)
    assert R._kept(snap, raw) == ([0, 1], Counter())


def test_foreign_colour_cannot_hide_behind_an_unmeasured_channel(capture):
    # Competing colours alias on G/B but differ in weak, uncredited R. They
    # remain ambiguous: the unmeasured channel cannot make the match unique.
    assert R._kept(*capture((0.01, 0.6, 1.0), mode="alias", secondary=(0.4, 0.8, 1.0))) == ([1], Counter({"no_ink": 1}))


def test_subpixel_visibility_cannot_be_borrowed_from_an_uncredited_channel(capture):
    snap, raw = capture((0.2, 0.6, 1.0), first_red=242, secondary=(0.4, 0.8, 1.0))
    def base(d):
        for i, (rect, _) in enumerate(R.TWO):
            colour = blend((0, 0, 0), (0.2, 0, 0) if i == 0 else (0.4, 0.8, 1.0))
            R._glyphs(d, rect, colour)
    raw["base"] = raw["base2"] = raw["plain"] = R._png(base)
    assert R._kept(snap, raw) == ([1], Counter({"no_ink": 1}))


def test_uninked_tint_evidence_stays_in_the_visibility_fraction_denominator(capture):
    snap, raw = capture()
    def partly_visible(d):
        for rect, _ in R.TWO:
            x, y, w, h = rect
            for at in range(x, x + w - 1, 12):  # only one third of the full glyph-like mask is visible
                d.rectangle([at, y + 2, at + 1, y + h - 3], fill=blend((0, 0, 0), (0.4, 0.8, 1.0)))
    raw["base"] = raw["base2"] = raw["plain"] = R._png(partly_visible)
    assert R._kept(snap, raw) == ([], Counter({"no_ink": 2}))


@pytest.fixture(scope="module")
def r13_high_value_palette(tmp_path_factory):
    # Captured f64db040 omission in BOTH selection modes. These HSV values
    # are within the unchanged original random driver's permitted range.
    # Pin only the palette draw; keep its page, capture flow and assertions.
    original = "const h0 = crypto.randomInt(360), s = 0.85 + crypto.randomInt(16) / 100, v = 0.8 + crypto.randomInt(16) / 100;"
    runner = R.RUNNER.replace(original, "const h0 = 0, s = 0.85, v = 0.95;")
    assert runner != R.RUNNER
    return R.run_chromium(tmp_path_factory.mktemp("r13_high_value"), R.PAGE, runner)


@pytest.mark.parametrize("mode", ["no_selection", "ctrl_a"])
def test_original_r13_keeps_visible_underlay_with_independently_proved_similar_coverages(r13_high_value_palette, mode):
    R.test_r13_01_hidden_text_over_visible_ink_never_reaches_the_brain(r13_high_value_palette, mode)
