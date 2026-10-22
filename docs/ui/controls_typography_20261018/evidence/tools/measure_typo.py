"""Count fontSize / fontFamily literals in uri_ui/lib at a git revision (or the work tree with WT).

python measure_typo.py <repo> <rev|WT>
"""
import collections, json, re, subprocess, sys
from pathlib import Path

repo, rev = Path(sys.argv[1]), sys.argv[2]
EXEMPT = {'uri_ui/lib/widgets/dashboard/reference_dashboard.dart', 'uri_ui/lib/theme/dashboard_manifest.dart',
          'uri_ui/lib/screens/settings/settings_shell.dart'}
if rev == 'WT':
    files = {p.relative_to(repo).as_posix(): p.read_text(encoding='utf-8') for p in (repo / 'uri_ui/lib').rglob('*.dart')}
else:
    names = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-r', '--name-only', rev, 'uri_ui/lib'], text=True).split()
    files = {n: subprocess.check_output(['git', '-C', str(repo), 'show', '%s:%s' % (rev, n)]).decode('utf-8')
             for n in names if n.endswith('.dart')}
size = re.compile(r'fontSize:\s*(\d+(?:\.\d+)?)')
tern = re.compile(r'fontSize:[^,;\n]*?\?\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)')
fam = re.compile(r"fontFamily:\s*'([^']+)'")
out = {}
for scope in ('all', 'excluding_frozen_board_and_protected'):
    sizes, fams, files_with = collections.Counter(), collections.Counter(), set()
    for n, s in files.items():
        if scope != 'all' and n in EXEMPT:
            continue
        found = size.findall(s) + [v for pair in tern.findall(s) for v in pair]
        if found:
            files_with.add(n)
        sizes.update(found)
        fams.update(fam.findall(s))
    out[scope] = {'fontSize_literals': sum(sizes.values()), 'distinct_fontSize_values': len(sizes),
                  'values': dict(sorted(sizes.items(), key=lambda x: float(x[0]))),
                  'files_with_fontSize_literals': len(files_with),
                  'fontFamily_literals': dict(fams), 'distinct_fontFamily_literals': len(fams)}
print(json.dumps({'rev': rev, **out}, indent=1))
