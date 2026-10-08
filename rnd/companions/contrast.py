"""WCAG 2.1 relative-luminance contrast ratios for the companion palettes.

Checks the pairs that carry meaning, not decoration: body text, secondary
text, and each status colour against the surface it is actually drawn on.
"""
def lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def lum(h):
    r = (h >> 16) & 255; g = (h >> 8) & 255; b = h & 255
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

P = {
 'solarEmber': dict(ink=0xF6ECE3, inkSoft=0xB9A796, inkFaint=0x8B7C6F,
   canvas=0x0A0806, surface=0x130F0B, surfaceSunken=0x1B1511, border=0x2E241B,
   accent=0xFF9F45, accentSoft=0x33200E, accentInk=0xFFD79A,
   success=0x5FD6A0, successSoft=0x0F2E24, warning=0xF2D04C, warningSoft=0x332E10,
   danger=0xFF6B5E, dangerSoft=0x3A1714),
 'sakuraBloom': dict(ink=0xF7EAF0, inkSoft=0xC2A7B4, inkFaint=0x8E7585,
   canvas=0x0B060A, surface=0x150C13, surfaceSunken=0x1D121A, border=0x33202C,
   accent=0xFF77B4, accentSoft=0x331323, accentInk=0xFFBBD8,
   success=0x5BD3A6, successSoft=0x0F2E25, warning=0xE9B457, warningSoft=0x342713,
   danger=0xFF5A4E, dangerSoft=0x3A1613),
 'lunarSilver': dict(ink=0xEAEFF7, inkSoft=0xA7B2C4, inkFaint=0x78839A,
   canvas=0x070912, surface=0x0D1120, surfaceSunken=0x131829, border=0x222A42,
   accent=0xB9C6E8, accentSoft=0x1A2138, accentInk=0xE2E9F8,
   success=0x56CFA8, successSoft=0x0E2E26, warning=0xE3B35A, warningSoft=0x332912,
   danger=0xFF7A7A, dangerSoft=0x3A1C1C),
}

PAIRS = [
 ('body text on surface', 'ink', 'surface'),
 ('body text on canvas', 'ink', 'canvas'),
 ('secondary text on surface', 'inkSoft', 'surface'),
 ('faint text on surface', 'inkFaint', 'surface'),
 ('accent text on accentSoft', 'accentInk', 'accentSoft'),
 ('success on successSoft', 'success', 'successSoft'),
 ('warning on warningSoft', 'warning', 'warningSoft'),
 ('danger on dangerSoft', 'danger', 'dangerSoft'),
]

# Status colours must stay distinguishable from the brand accent, or a pill
# reads as branding rather than as a warning.
SEPARATION = [('accent vs warning', 'accent', 'warning'),
              ('accent vs danger', 'accent', 'danger'),
              ('accent vs success', 'accent', 'success'),
              ('warning vs danger', 'warning', 'danger')]

print(f"{'pair':34s} " + ' '.join(f'{n:>13s}' for n in P))
for label, a, b in PAIRS:
    print(f'{label:34s} ' + ' '.join(f'{ratio(P[n][a], P[n][b]):13.2f}' for n in P))
print()
print('Hue separation (contrast ratio between two foreground colours;')
print('a LOW number here means they look alike in luminance, which is why')
print('status is also carried by text labels, never colour alone):')
for label, a, b in SEPARATION:
    print(f'{label:34s} ' + ' '.join(f'{ratio(P[n][a], P[n][b]):13.2f}' for n in P))
