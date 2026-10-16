from pathlib import Path

page = Path(__file__).resolve().parents[1] / 'companion-options.html'
source = page.read_text(encoding='utf-8')
source = source.replace('width:92px;min-height:44px;height:44px',
    'width:max-content;min-width:44px;max-width:100px;min-height:44px;height:44px')
source = source.replace('padding:0 4px;white-space:nowrap',
    'padding:10px 12px;line-height:24px;white-space:nowrap;touch-action:manipulation')
source = source.replace('w/2-56','w/2-58')
# Conservative bounds include the widest allowed label, not the old fixed pill.
source = source.replace('-46,0','-50,0').replace('p.x-46<8','p.x-50<8').replace('p.x+46>width-8','p.x+50>width-8')
source = source.replace('<100&&','<108&&')
source = source.replace('position:absolute;width:max-content', 'position:absolute;width:max-content')
source = source.replace('width:36px;height:36px;border-radius:50%', 'width:44px;height:44px;border-radius:50%')
source = source.replace('width:32px;height:32px', 'width:44px;height:44px')
source = source.replace('<main class="options">', '<main id="options" class="options">')
source = source.replace('<body><header>', '<body><a href="#options">Skip to Companion options</a><header>')
source = source.replace('alt="Recorded frame of URI Solar Companion"', 'width="440" height="680" alt="Recorded frame of URI Solar Companion"')
source = source.replace('<input aria-label="Message URI"', '<input name="message" autocomplete="off" aria-label="Message URI"')
page.write_text(source, encoding='utf-8')
