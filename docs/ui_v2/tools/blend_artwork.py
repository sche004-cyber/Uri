from pathlib import Path
p = Path(__file__).resolve().parents[3] / 'uri_ui/lib/living/screens/frost_dashboard.dart'
s = p.read_text(encoding='utf-8').replace('UriPortrait', 'UriArtwork')
s = s.replace('right: 212, bottom: 32', 'right: 232, bottom: 32').replace('width: 144,', 'width: 164,')
start = s.index('    return Semantics(', s.index('class UriArtwork'))
end = s.index('\n  }\n}', start)
s = s[:start] + '''    const feather = [Colors.transparent, Colors.black, Colors.black, Colors.transparent];
    return Semantics(
      label: 'URI artwork. The puppy who inspired this project.',
      image: true,
      child: IgnorePointer(child: RepaintBoundary(child: AspectRatio(
        aspectRatio: 2 / 3,
        child: ShaderMask(
          blendMode: BlendMode.dstIn,
          shaderCallback: (bounds) => const LinearGradient(
            colors: feather, stops: [0, .12, .88, 1],
          ).createShader(bounds),
          child: ShaderMask(
            blendMode: BlendMode.dstIn,
            shaderCallback: (bounds) => const LinearGradient(
              begin: Alignment.topCenter, end: Alignment.bottomCenter,
              colors: feather, stops: [0, .08, .90, 1],
            ).createShader(bounds),
            child: Opacity(opacity: .85, child: ColorFiltered(
              colorFilter: ColorFilter.matrix([
                ...row(c.ink.r, c.canvas.r), ...row(c.ink.g, c.canvas.g),
                ...row(c.ink.b, c.canvas.b), 0, 0, 0, 1, 0,
              ]),
              child: Image.asset('assets/uri_portrait_original.png',
                fit: BoxFit.contain, excludeFromSemantics: true),
            )),
          ),
        ),
      ))),
    );''' + s[end:]
s = s.replace("/// The owner's supplied portrait, in full; the source asset stays unchanged.",
    "/// The owner's supplied artwork; the source asset stays unchanged.")
s = s.replace('/// A theme-derived duotone maps the sketch to ink/paper without warm orange\n/// leaking into Snow/Ash. This portrait is not a Companion or an action.',
    '/// Theme-derived ink/paper and feathered edges blend the sketch into the\n/// canvas. This static artwork is not a Companion or an action.')
p.write_text(s, encoding='utf-8')
