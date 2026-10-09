"""Contact sheets for the voice/state captures.

Run: python rnd/voice/sheets.py <capture dir>
Writes sheet_*.png into the same directory.
"""
import os
import sys
from PIL import Image, ImageDraw

D = sys.argv[1]
IDS = ['solar', 'sakura', 'lunar', 'moonlit']


def sheet(out, rows, cw=300, label_h=22):
    """rows: list of lists of (file, label)."""
    first = Image.open(os.path.join(D, rows[0][0][0] + '.png'))
    ch = int(cw * first.height / first.width)
    cols = max(len(r) for r in rows)
    sh = Image.new('RGB', (cols * cw, len(rows) * (ch + label_h)), (10, 10, 14))
    d = ImageDraw.Draw(sh)
    for ri, row in enumerate(rows):
        for ci, (f, lab) in enumerate(row):
            p = os.path.join(D, f + '.png')
            x, y = ci * cw, ri * (ch + label_h)
            if os.path.exists(p):
                im = Image.open(p).convert('RGB').resize((cw, ch), Image.LANCZOS)
                sh.paste(im, (x, y + label_h))
            d.text((x + 6, y + 5), lab, fill=(226, 220, 210))
    sh.save(os.path.join(D, out))
    print(out, sh.size)


states = ['idle', 'listening', 'thinking', 'working', 'awaitingApproval',
          'awaitingApproval_pulse', 'success', 'error', 'unavailable']
sheet('sheet_states.png', [[(f'state_{i}_{s}', f'{i} / {s}') for s in states] for i in IDS])
sheet('sheet_voice_user.png', [[(f'voice_{i}_user_t{t:04d}', f'{i} user {t}ms') for t in [900, 1700, 2600, 3800, 5200]] for i in IDS])
sheet('sheet_voice_uri.png', [[(f'voice_{i}_uri_t{t:04d}', f'{i} URI {t}ms') for t in [600, 2100, 3900, 5600, 7800]] for i in IDS])
sheet('sheet_same_audio.png', [[(f'same_audio_as_user_t{t}', f'as user {t}ms') for t in [700, 1900, 3300, 5100, 7400]],
                               [(f'same_audio_as_uri_t{t}', f'as URI {t}ms') for t in [700, 1900, 3300, 5100, 7400]]], cw=360)
sheet('sheet_transition.png', [[(f'transition_sakura_v{v:03d}', f'blend {v}%') for v in [0, 20, 40, 60, 80, 100]]])
sheet('sheet_edges.png', [[('edge_approval_over_speech_moonlit', 'approval named over URI speech'),
                           ('edge_voice_failure_lunar', 'microphone failure notice'),
                           ('edge_reduced_effects_solar_user', 'reduced effects'),
                           ('edge_silence_before_speech_sakura', 'listening, before speech')]])
for kind in ['floating', 'workspace']:
    sheet(f'sheet_size_{kind}.png', [[(f'size_{kind}_solar_idle', f'{kind} idle'), (f'size_{kind}_solar_uri', f'{kind} URI speaking')]], cw=420)
