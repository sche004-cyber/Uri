from pathlib import Path
p=Path(__file__).resolve().parents[3]/'uri_ui/lib/living/screens/frost_dashboard.dart'
s=p.read_text(encoding='utf-8')
start=s.index('            child: DecoratedBox(',s.index('class UriArtwork'))
end=s.index('\n          ),\n        ),\n      ),\n    );',start)
s=s[:start]+'''            child: Opacity(
              opacity: .46,
              child: ColorFiltered(
                colorFilter: ColorFilter.matrix([
                  ...row(engraving.r, c.canvas.r),
                  ...row(engraving.g, c.canvas.g),
                  ...row(engraving.b, c.canvas.b), 0, 0, 0, 1, 0,
                ]),
                child: Image.asset('assets/uri_engraving_cutout_v2.png',
                  fit: BoxFit.contain, excludeFromSemantics: true),
              ),
            ),'''+s[end:]
start=s.index('class _SteelEtching')
end=s.index('class _Conduits',start)
s=s[:start]+s[end:]
s=s.replace('/// Theme-derived etched ink, matte steel and calibration details form a flush\n/// inlay. This static artwork is not a Companion or an action.',
  '/// Theme-derived etched tones blend directly into the matte canvas, with no\n/// visible plate border. This static artwork is not a Companion or an action.')
p.write_text(s,encoding='utf-8')
