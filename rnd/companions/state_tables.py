"""Single source of the companion expression tables.

Writes the same numbers into three places so they cannot drift:
  * uri_ui/lib/living/companion/companion_orb.dart  (the shipped widget)
  * rnd/companions/registry.js                     (the WebGL prototype)
  * rnd/companions/state_tables.json               (read by a Dart test that
                                                    fails if the widget and
                                                    this file disagree)

Run: python rnd/companions/state_tables.py

Column order: energy, turbulence, flare, particles, focus, exposure.

Revision 2 (voice and state phase, 2026-10-09). The brief for this phase asks
that ordinary states change the companion's state, not its character:

  listening  softer than idle: lower energy, calmer flow, slightly lower
             exposure. Nothing new appears.
  thinking   deeper shade and subdued glow (flare and particles well below
             idle, exposure down a little) with concentrated internal
             movement (turbulence up, focus high). Revision 1 made thinking
             brighter and busier than idle, which read as "working".
  working    steady and controlled: more energy than idle but low turbulence
             and high focus. Revision 1 used maximum turbulence and minimum
             focus, which read as alarm.
  approval   calm base; the attention pulse is added at runtime by the widget
             (CompanionParams.withAttention), not baked into the table.
  error      identity preserved: moderate values with low focus. The meaning
             is carried by the status label and its danger colour, not by
             making the companion look broken.
  speaking   only drives the small identity mark shown above the voice
             waveform while URI speaks.

Exposure never drops below 0.84 outside `unavailable`: a uniform darkening
removes the very detail (filaments, craters, petal veins) that makes each
companion recognisable. rnd/voice/state_metrics.py measures body luminance
and body detail per state against idle from real captures; the intended
ordering is thinking < listening < idle < working for body luminance, with
body detail staying within roughly 0.85-1.2 of idle.

Run 2 of the voice phase showed listening darker than thinking (solar body
0.90 vs 0.95 of idle), the reverse of the brief, so listening now softens
mainly through energy and flare and thinking carries the deeper shade.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))

STATES = ['unavailable', 'idle', 'listening', 'thinking', 'speaking',
          'working', 'awaitingApproval', 'success', 'error']

TABLES = {
    'solar': {
        'unavailable':      (0.06, 0.05, 0.00, 0.05, 0.95, 0.72),
        'idle':             (0.22, 0.16, 0.10, 0.28, 0.85, 1.00),
        'listening':        (0.15, 0.09, 0.05, 0.18, 0.95, 0.97),
        'thinking':         (0.30, 0.46, 0.04, 0.12, 0.97, 0.84),
        'speaking':         (0.40, 0.22, 0.28, 0.40, 0.92, 1.02),
        'working':          (0.56, 0.24, 0.36, 0.46, 0.94, 1.05),
        'awaitingApproval': (0.26, 0.10, 0.12, 0.24, 0.98, 1.00),
        'success':          (0.70, 0.18, 0.70, 0.70, 0.98, 1.12),
        'error':            (0.30, 0.42, 0.10, 0.16, 0.40, 0.90),
    },
    'sakura': {
        'unavailable':      (0.06, 0.05, 0.00, 0.06, 0.95, 0.74),
        'idle':             (0.24, 0.18, 0.10, 0.34, 0.80, 1.00),
        'listening':        (0.16, 0.10, 0.05, 0.26, 0.94, 0.98),
        'thinking':         (0.30, 0.42, 0.05, 0.24, 0.97, 0.85),
        'speaking':         (0.42, 0.22, 0.28, 0.44, 0.90, 1.02),
        'working':          (0.56, 0.26, 0.36, 0.56, 0.93, 1.05),
        'awaitingApproval': (0.28, 0.10, 0.12, 0.32, 0.98, 1.00),
        'success':          (0.72, 0.18, 0.70, 0.80, 0.96, 1.12),
        'error':            (0.30, 0.40, 0.10, 0.24, 0.40, 0.90),
    },
    'lunar': {
        'unavailable':      (0.05, 0.10, 0.00, 0.06, 0.30, 0.70),
        'idle':             (0.22, 0.24, 0.12, 0.30, 0.55, 1.00),
        'listening':        (0.15, 0.14, 0.07, 0.24, 0.80, 0.98),
        'thinking':         (0.28, 0.46, 0.05, 0.24, 0.44, 0.85),
        'speaking':         (0.38, 0.22, 0.32, 0.34, 0.72, 1.02),
        'working':          (0.50, 0.28, 0.38, 0.38, 0.70, 1.05),
        'awaitingApproval': (0.26, 0.14, 0.14, 0.28, 0.88, 1.00),
        'success':          (0.60, 0.12, 0.60, 0.40, 1.00, 1.10),
        'error':            (0.30, 0.48, 0.10, 0.22, 0.30, 0.88),
    },
}

DART_NAMES = {'solar': '_solar', 'sakura': '_sakura', 'lunar': '_lunar'}


def dart_table(fam):
    out = [f'  static const Map<CompanionState, CompanionParams> {DART_NAMES[fam]} =',
           '      <CompanionState, CompanionParams>{']
    for st in STATES:
        e, t, f, p, fo, x = TABLES[fam][st]
        out += [f'        CompanionState.{st}: CompanionParams(',
                f'          energy: {e:.2f}, turbulence: {t:.2f}, flare: {f:.2f},',
                f'          particles: {p:.2f}, focus: {fo:.2f}, exposure: {x:.2f},',
                '        ),']
    out.append('      };')
    return '\n'.join(out)


def write_dart():
    path = os.path.join(ROOT, 'uri_ui', 'lib', 'living', 'companion', 'companion_orb.dart')
    src = open(path, encoding='utf-8').read()
    for fam, name in DART_NAMES.items():
        pat = re.compile(
            r'  static const Map<CompanionState, CompanionParams> ' + name +
            r' =\n.*?\n      \};', re.S)
        src, n = pat.subn(lambda _m: dart_table(fam), src)
        assert n == 1, (fam, n)
    open(path, 'w', encoding='utf-8', newline='\n').write(src)


def write_js():
    path = os.path.join(HERE, 'registry.js')
    src = open(path, encoding='utf-8').read()
    for fam in TABLES:
        for st in STATES:
            vals = ', '.join(f'{v:.2f}' for v in TABLES[fam][st])
            pat = re.compile(r'(\n  ' + fam + r': \{.*?\n    ' + st +
                             r':\s+)S\([^)]*\)', re.S)
            src, n = pat.subn(lambda m: m.group(1) + f'S({vals})', src)
            assert n == 1, (fam, st, n)
    open(path, 'w', encoding='utf-8', newline='\n').write(src)


def write_json():
    path = os.path.join(HERE, 'state_tables.json')
    data = {'revision': 2, 'columns': ['energy', 'turbulence', 'flare',
                                       'particles', 'focus', 'exposure'],
            'tables': {f: {s: list(v) for s, v in t.items()}
                       for f, t in TABLES.items()}}
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, indent=1)
        fh.write('\n')


if __name__ == '__main__':
    write_dart()
    write_js()
    write_json()
    print('wrote companion_orb.dart, registry.js, state_tables.json')
