"""UI-CONTROLS-TYPO-20261018: put every literal fontSize in uri_ui/lib on the UriType scale.

Usage: python typo_migrate.py <uri_ui root> [--apply]   (dry run prints per-file counts and the value map)
"""
import re, sys, collections
from pathlib import Path

root = Path(sys.argv[1]); apply = '--apply' in sys.argv
TOK = {10: 'micro', 11: 'caption', 12: 'label', 13: 'body', 14: 'bodyLarge', 15: 'title', 17: 'titleLarge',
       20: 'heading', 24: 'headline', 28: 'headlineLarge', 34: 'display', 48: 'hero'}
# Explicit snapping (half steps up; others to the nearest step, ties up).
SNAP = {7.4: 10, 8: 10, 9: 10, 9.5: 10, 10: 10, 10.5: 11, 11: 11, 11.5: 12, 12: 12, 12.5: 13, 13: 13, 13.5: 14,
        14: 14, 15: 15, 16: 17, 18: 17, 19: 20, 20: 20, 22: 24, 23: 24, 24: 24, 26: 28, 30: 28, 34: 34, 38: 34,
        48: 48}
# Not migrated: the classic dashboard is a frozen, pixel-transcribed 1024x682 board scaled as a whole (its sizes are
# board units, not logical pixels; dashboard_manifest.dart says never hand-edit). uri_theme.dart is edited by hand.
# settings_shell.dart is PROTECTED (scripts/ws_frozen_check.py) and is never edited.
SKIP = {'lib/screens/settings/settings_shell.dart', 'lib/widgets/dashboard/reference_dashboard.dart', 'lib/theme/dashboard_manifest.dart', 'lib/theme/uri_theme.dart'}
NUM = r'(\d+(?:\.\d+)?)'
pat_simple = re.compile(r'(fontSize:\s*)' + NUM + r'(?![\d.]|\s*[*/+\-])')
pat_tern = re.compile(r'(fontSize:\s*[^,;\n?]+\?\s*)' + NUM + r'(\s*:\s*)' + NUM + r'(?![\d.])')


def tok(v):
    v = float(v)
    v = int(v) if v.is_integer() else v
    if v not in SNAP:
        raise SystemExit('unmapped size %r' % v)
    return 'UriType.' + TOK[SNAP[v]]


changes = collections.Counter(); per = {}
for f in sorted((root / 'lib').rglob('*.dart')):
    rel = f.relative_to(root).as_posix()
    if rel in SKIP:
        continue
    s = f.read_text(encoding='utf-8'); orig = s
    s = pat_tern.sub(lambda m: (changes.update([(m.group(2), 't'), (m.group(4), 't')]) or '')
                     + m.group(1) + tok(m.group(2)) + m.group(3) + tok(m.group(4)), s)
    s = pat_simple.sub(lambda m: (changes.update([(m.group(2), 's')]) or '') + m.group(1) + tok(m.group(2)), s)
    if s != orig:
        n = sum(1 for a, b in zip(orig.splitlines(), s.splitlines()) if a != b)
        per[rel] = n
        if 'uri_theme.dart' not in s.split('class ')[0] and 'part of' not in s[:400]:
            # add the theme import after the last import line
            lines = s.split('\n')
            last = max(i for i, l in enumerate(lines) if l.startswith('import '))
            lines.insert(last + 1, "import 'package:uri_ui/theme/uri_theme.dart';")
            s = '\n'.join(lines)
        if apply:
            f.write_text(s, encoding='utf-8', newline='')
for k, v in sorted(per.items()):
    print('%4d  %s' % (v, k))
print('files', len(per), 'lines', sum(per.values()))
print(sorted(changes.items(), key=lambda x: float(x[0][0])))
