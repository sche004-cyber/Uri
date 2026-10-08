import json
from pathlib import Path
p = Path.cwd()
results = {}
for name, operation in [
    ('inside_write', lambda: (p / 'inside_unelevated.txt').write_text('probe')),
    ('outside_read', lambda: (p.parent / 'protected.txt').read_text()),
    ('outside_write', lambda: (p.parent / 'outside_unelevated.txt').write_text('probe')),
]:
    try:
        operation()
        results[name] = 'allowed'
    except (PermissionError, OSError):
        results[name] = 'denied'
print(json.dumps(results))
