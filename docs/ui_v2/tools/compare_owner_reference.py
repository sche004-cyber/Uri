"""Read-only image comparison; writes metrics, never modified image assets.

Reference is resampled in memory to the Flutter capture's viewport. The
region-balanced score avoids weighting the large plain canvas as one region.
This measures screenshot structure, not functionality or owner acceptance.
"""
from pathlib import Path
import hashlib, json
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

root = Path(__file__).resolve().parents[1]
reference = root / 'evidence/reference/owner-current.jpg'
candidate = root / 'evidence/engraving-final/dashboard-snowArchive-1440.png'
ref = Image.open(reference).convert('RGB')
image = Image.open(candidate).convert('RGB')
original_size = ref.size
ref = ref.resize(image.size, Image.Resampling.LANCZOS)
# Standard local luminance SSIM constants, L=255, sigma=1.5, 11px window.
def score(a, b):
    a, b = [np.asarray(x, dtype=np.float64) @ np.array([.2126, .7152, .0722])
            for x in (a, b)]
    blur = lambda x: gaussian_filter(x, sigma=1.5, truncate=3.333333333)
    ma, mb = blur(a), blur(b)
    va, vb = blur(a*a) - ma*ma, blur(b*b) - mb*mb
    cov = blur(a*b) - ma*mb
    result = ((2*ma*mb + 6.5025)*(2*cov + 58.5225)) / (
        (ma*ma + mb*mb + 6.5025)*(va + vb + 58.5225))
    return float(np.mean(result[5:-5,5:-5]))

regions = {
    'navigation': (0,0,208,1000),
    'heading_and_review': (208,0,1440,250),
    'left_function_regions': (244,336,568,696),
    'right_function_regions': (1080,336,1404,696),
    'actual_solar_renderer': (638,264,1010,638),
    'state_and_details': (624,638,1024,760),
    'composer': (244,780,1208,968),
    'puppy_engraving': (1240,722,1404,968),
}
scores = {k:score(ref.crop(v),image.crop(v)) for k,v in regions.items()}
result = {
    'method':'Equal-weight regional luminance SSIM, Gaussian sigma 1.5, 11px window, population covariance',
    'reference_size':original_size, 'comparison_size':image.size,
    'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
    'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),
    'regions':{k:{'bounds':regions[k], 'ssim':v} for k,v in scores.items()},
    'region_balanced_ssim':sum(scores.values())/len(scores),
    'target':.8,
    'meets_screenshot_target':sum(scores.values())/len(scores)>=.8,
    'limits':[
        'A screenshot metric is not a literal percentage of design accuracy or owner acceptance.',
        'Luminance-only: theme colour tokens are checked separately.',
        'Latest reference is JPEG; compression/resampling lower similarity.',
        'Solar animation phase and the requested stronger artwork fade intentionally differ.',
        'No native transparency, hit testing, audio, backend or independent audit claims.',
    ],
}
(root/'evidence/engraving-final/reference_comparison.json').write_text(
    json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
