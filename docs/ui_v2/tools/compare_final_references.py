"""Read-only final frame comparison. No image files are modified or generated."""
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

root = Path(__file__).resolve().parents[1]
out = root / 'evidence/final'


def score(a, b):
    a, b = [np.asarray(x, dtype=np.float64) @ np.array([.2126, .7152, .0722])
            for x in (a, b)]
    blur = lambda x: gaussian_filter(x, sigma=1.5, truncate=3.333333333)
    ma, mb = blur(a), blur(b)
    va, vb = blur(a*a) - ma*ma, blur(b*b) - mb*mb
    cov = blur(a*b) - ma*mb
    result = ((2*ma*mb + 6.5025)*(2*cov + 58.5225)) / (
        (ma*ma + mb*mb + 6.5025)*(va + vb + 58.5225))
    return float(result[5:-5, 5:-5].mean())


def compare(reference, candidate, regions, name, transparent=False):
    ref = Image.open(reference).convert('RGB')
    image = Image.open(candidate)
    original_size = ref.size
    if transparent:
        # Gray exists only on the comparison page, never in the application.
        bg = Image.new('RGBA', image.size, '#72726f')
        bg.alpha_composite(image.convert('RGBA'))
        image = bg
    image = image.convert('RGB')
    ref = ref.resize(image.size, Image.Resampling.LANCZOS)
    scores = {k: score(ref.crop(v), image.crop(v)) for k, v in regions.items()}
    mean = sum(scores.values()) / len(scores)
    report = {
        'method': 'Equal-weight regional luminance SSIM, sigma 1.5, 11px window',
        'reference': str(reference.relative_to(root)),
        'candidate': str(candidate.relative_to(root)),
        'reference_size': original_size,
        'comparison_size': image.size,
        'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
        'regions': {k: {'bounds': regions[k], 'ssim': v} for k, v in scores.items()},
        'mean_ssim': mean,
        'checkpoint': .8,
        'meets_screenshot_checkpoint': mean >= .8,
        'limits': [
            'Not a literal percentage of design accuracy or owner acceptance.',
            'Luminance-only: theme token contrast is tested separately.',
            'Actual Solar phase, filaments and halo differ from the reference.',
            'Fixture audio level is injected, not recorded user audio.',
            'Native compositor, runtime, devices and performance not verified.',
        ],
    }
    (out / name).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return mean


companion = compare(
    root / 'evidence/reference/companion-approved.jpg',
    out / 'companion-approved-828.png',
    {
        'solar': (190, 165, 638, 605),
        'chat_button': (80, 325, 186, 437),
        'dashboard_button': (643, 325, 751, 437),
        'voice_button': (360, 592, 468, 724),
        'waveform': (270, 710, 558, 818),
        'detached_chat': (190, 840, 640, 1120),
    },
    'companion_comparison.json',
    transparent=True,
)
dashboard = compare(
    root / 'evidence/reference/owner-current.jpg',
    out / 'dashboard-snowArchive-1440.png',
    {
        'navigation': (0, 0, 208, 1000),
        'heading_and_review': (208, 0, 1440, 250),
        'left_function_regions': (244, 336, 568, 696),
        'right_function_regions': (1080, 336, 1404, 696),
        'actual_solar_renderer': (638, 264, 1010, 638),
        'state_and_details': (624, 638, 1024, 760),
        'composer': (244, 780, 1208, 968),
        'puppy_engraving': (1240, 722, 1404, 968),
    },
    'dashboard_comparison.json',
)
print(json.dumps({'companion_mean_ssim': companion, 'dashboard_mean_ssim': dashboard}))
