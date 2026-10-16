from pathlib import Path
p=Path('uri_ui/lib/living/widgets/living_composer.dart');s=p.read_text(encoding='utf-8').replace('this.minimal = false,', 'this.minimal = false,\n    this.floating = false,').replace('final bool minimal;', 'final bool minimal;\n  final bool floating;')
s=s.replace('filled: false,\n                          border: InputBorder.none,', '''filled: widget.floating,
                          fillColor: widget.floating ? c.surfaceSunken : null,
                          border: widget.floating ? OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none) : InputBorder.none,
                          enabledBorder: widget.floating ? OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none) : null,
                          focusedBorder: widget.floating ? OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide(color: c.accent, width: 1.5)) : null,''')
s=s.replace('contentPadding: const EdgeInsets.symmetric(\n                            vertical: 10,\n                          ),', 'contentPadding: EdgeInsets.symmetric(horizontal: widget.floating ? 12 : 0, vertical: 10),')
s=s.replace('color: sending ? glass.fill : glass.glow,', 'color: widget.floating ? Colors.transparent : sending ? glass.fill : glass.glow,');s=s.replace('width: 34,\n                          height: 34,', 'width: widget.floating ? 44 : 34,\n                          height: widget.floating ? 44 : 34,');s=s.replace(': Icons.arrow_upward_rounded,', ': widget.floating ? Icons.send_rounded : Icons.arrow_upward_rounded,');s=s.replace('color: sending ? c.inkFaint : c.canvas,', 'color: sending ? c.inkFaint : widget.floating ? c.accent : c.canvas,');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/screens/companion_mode_view.dart');s=p.read_text(encoding='utf-8').replace('minimal: true,\n            hint:', 'minimal: true,\n            floating: true,\n            hint:');s=s.replace('return ListView(\n          reverse: true,\n          padding: const EdgeInsets.only(top: 4),\n          children: messages.reversed.toList(),\n        );', '''return LayoutBuilder(builder: (context, box) => Align(alignment: Alignment.topCenter,
          child: ListView(shrinkWrap: true, reverse: true,
            padding: EdgeInsets.only(top: box.maxWidth > 350 ? 28 : 4),
            children: messages.reversed.toList(),
          ),
        ));''')
p.write_text(s,encoding='utf-8')
