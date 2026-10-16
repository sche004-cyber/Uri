from pathlib import Path
import re
root=Path(r'C:\Users\cheta\Development\uri-design-planning\2026-10-12-frost-engine')
s=(root/'URI_FROST_ENGINE_PREVIEW.html').read_text(encoding='utf-8-sig')
s=re.sub(r'data:[^\s"\']+', '[embedded asset]', s)
for term in ['companion-chat"', 'overlay-actions', 'tablist', 'overlay-context']:
    start=0
    print('\nTERM',term)
    for _ in range(4):
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-120):i+1000])
        start=i+len(term)
