import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../widgets/glass_panel.dart';
import 'a2ui_hub.dart';

/// Renders one validated A2UI surface with the active Living theme.
///
/// Only catalog components exist here (the hub has already refused anything
/// else). The surface cannot choose colours, fonts or URLs: tones map to the
/// theme's own colours. Inputs write the hub's local model; Buttons call
/// [A2uiHub.act]. Keys follow `a2ui.<surfaceId>.<componentId>` for tests.
class A2uiSurfaceView extends StatelessWidget {
  const A2uiSurfaceView({
    super.key,
    required this.hub,
    required this.surfaceId,
    this.compact = false,
    this.bare = false,
    this.rootId = 'root',
    this.hostIcon,
  });

  final A2uiHub hub;
  final String surfaceId;
  final bool compact;

  /// Host-selected presentation only; definitions cannot request this style.
  final bool bare;
  final String rootId;

  /// Local host presentation; never read from untrusted surface definitions.
  final IconData? hostIcon;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: hub,
      builder: (context, _) {
        final s = hub.surface(surfaceId);
        if (s == null || !s.ready) return const SizedBox.shrink();
        final c = UriColors.of(context);
        final err = hub.errors[surfaceId];
        final content = Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            _Node(hub: hub, s: s, id: rootId, compact: compact),
            if (hub.busy.contains(surfaceId))
              const Padding(
                padding: EdgeInsets.only(top: UriSpace.sm),
                child: LinearProgressIndicator(minHeight: 2),
              ),
            if (err != null)
              Padding(
                padding: const EdgeInsets.only(top: UriSpace.sm),
                child: Text(
                  err,
                  key: ValueKey('a2ui.$surfaceId.error'),
                  style: TextStyle(color: c.danger, fontSize: 13),
                ),
              ),
          ],
        );
        if (hostIcon != null) {
          return SizedBox.expand(
            child: _Node(
              hub: hub,
              s: s,
              id: rootId,
              compact: compact,
              hostIcon: hostIcon,
            ),
          );
        }
        if (bare) {
          return Theme(
            data: Theme.of(context).copyWith(
              outlinedButtonTheme: OutlinedButtonThemeData(
                style: OutlinedButton.styleFrom(
                  side: BorderSide.none,
                  backgroundColor: c.surface,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(22),
                  ),
                  minimumSize: const Size(0, 44),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 8,
                  ),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.standard,
                  textStyle: const TextStyle(fontSize: 14),
                ),
              ),
            ),
            child: content,
          );
        }
        return GlassPanel(
          key: ValueKey('a2ui.$surfaceId'),
          padding: EdgeInsets.all(compact ? UriSpace.md : UriSpace.lg),
          strong: true,
          child: content,
        );
      },
    );
  }
}

class _Node extends StatelessWidget {
  const _Node({
    required this.hub,
    required this.s,
    required this.id,
    required this.compact,
    this.scope,
    this.hostIcon,
  });

  final A2uiHub hub;
  final A2uiSurface s;
  final String id;
  final bool compact;
  final String? scope;
  final IconData? hostIcon;

  Object? _v(Object? prop) => (prop is Map && prop.containsKey('path'))
      ? s.read(prop['path'] as String, scope: scope)
      : prop;

  String _text(Object? prop) {
    final v = _v(prop);
    return v == null ? '' : '$v';
  }

  ValueKey<String> _key([String suffix = '']) =>
      ValueKey('a2ui.${s.id}.$id$suffix');

  List<Widget> _children(Map comp) {
    final ch = comp['children'];
    if (ch is List) {
      return [
        for (final k in ch)
          _Node(
            hub: hub,
            s: s,
            id: k as String,
            compact: compact,
            scope: scope,
          ),
      ];
    }
    if (ch is Map) {
      final list = s.read(ch['path'] as String);
      if (list is! List) return const [];
      return [
        for (var i = 0; i < list.length && i < 200; i++)
          _Node(
            hub: hub,
            s: s,
            id: ch['componentId'] as String,
            compact: compact,
            scope: '${ch['path']}/$i',
          ),
      ];
    }
    return const [];
  }

  double _gap(Object? g) => switch (g) {
    'none' => 0,
    'small' => UriSpace.sm,
    'large' => UriSpace.lg,
    _ => UriSpace.md,
  };

  @override
  Widget build(BuildContext context) {
    final comp = s.byId[id];
    if (comp == null) return const SizedBox.shrink();
    final c = UriColors.of(context);
    final type = comp['component'] as String;
    switch (type) {
      case 'Column':
      case 'List':
        final kids = _children(comp);
        final gap = _gap(comp['gap']);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < kids.length; i++) ...[
              if (i > 0) SizedBox(height: gap),
              kids[i],
            ],
          ],
        );
      case 'Row':
        return Wrap(
          spacing: _gap(comp['gap']),
          runSpacing: UriSpace.sm,
          alignment: switch (comp['align']) {
            'center' => WrapAlignment.center,
            'end' => WrapAlignment.end,
            'spaceBetween' => WrapAlignment.spaceBetween,
            _ => WrapAlignment.start,
          },
          children: _children(comp),
        );
      case 'Card':
        return GlassPanel(
          padding: const EdgeInsets.all(UriSpace.md),
          child: _Node(
            hub: hub,
            s: s,
            id: comp['child'] as String,
            compact: compact,
            scope: scope,
          ),
        );
      case 'Divider':
        return Divider(color: c.border, height: 1);
      case 'Text':
        final variant = comp['variant'] ?? 'body';
        return Text(
          _text(comp['text']),
          key: _key(),
          style: switch (variant) {
            'title' => TextStyle(
              fontSize: compact ? 16 : 18,
              fontWeight: FontWeight.w700,
              color: c.ink,
            ),
            'label' => TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: c.inkSoft,
            ),
            'caption' => TextStyle(
              fontSize: 12,
              color: c.inkSoft,
              height: 1.35,
            ),
            _ => TextStyle(fontSize: 14, color: c.ink, height: 1.4),
          },
        );
      case 'Badge':
        final (fg, bg) = switch (comp['tone']) {
          'success' => (c.success, c.successSoft),
          'warning' => (c.warning, c.warningSoft),
          'danger' => (c.danger, c.dangerSoft),
          'accent' => (c.accent, c.accentSoft),
          _ => (c.inkSoft, c.surfaceSunken),
        };
        return Align(
          alignment: Alignment.centerLeft,
          child: Container(
            key: _key(),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              _text(comp['text']),
              style: TextStyle(
                color: fg,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        );
      case 'Button':
        final enabled =
            (_v(comp['enabled']) ?? true) == true && !hub.busy.contains(s.id);
        final label = Text(_text(comp['label']), textAlign: TextAlign.center);
        if (hostIcon != null) {
          return LayoutBuilder(
            builder: (context, box) => OutlinedButton(
              key: _key(),
              style: OutlinedButton.styleFrom(
                shape: const CircleBorder(),
                side: BorderSide.none,
                backgroundColor: c.surface,
                foregroundColor: c.ink,
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                textStyle: TextStyle(
                  fontSize: box.maxWidth < 96 ? 13 : 16,
                  height: 1.2,
                ),
              ),
              onPressed: enabled ? () => hub.act(s.id, id, scope: scope) : null,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    hostIcon,
                    size: (box.maxWidth * .38).clamp(24.0, 38.0),
                    color: c.accent,
                  ),
                  const SizedBox(height: 5),
                  label,
                ],
              ),
            ),
          );
        }
        void onTap() => hub.act(s.id, id, scope: scope);
        return switch (comp['variant']) {
          'primary' => FilledButton(
            key: _key(),
            onPressed: enabled ? onTap : null,
            child: label,
          ),
          'danger' => OutlinedButton(
            key: _key(),
            style: OutlinedButton.styleFrom(
              foregroundColor: c.danger,
              side: BorderSide(color: c.danger),
            ),
            onPressed: enabled ? onTap : null,
            child: label,
          ),
          _ => OutlinedButton(
            key: _key(),
            onPressed: enabled ? onTap : null,
            child: label,
          ),
        };
      case 'CheckBox':
        final p = (comp['value'] as Map)['path'] as String;
        return CheckboxListTile(
          key: _key(),
          dense: true,
          contentPadding: EdgeInsets.zero,
          value: s.read(p, scope: scope) == true,
          title: Text(
            _text(comp['label']),
            style: TextStyle(color: c.ink, fontSize: 14),
          ),
          onChanged: (v) => hub.input(s.id, p, v == true, scope: scope),
        );
      case 'ChoicePicker':
        return _Choice(
          hub: hub,
          s: s,
          comp: comp,
          scope: scope,
          keyBase: 'a2ui.${s.id}.$id',
          compact: compact,
        );
      case 'DateTimeInput':
        return _DateTime(
          hub: hub,
          s: s,
          comp: comp,
          scope: scope,
          keyBase: 'a2ui.${s.id}.$id',
        );
      case 'TextField':
        return _Field(
          hub: hub,
          s: s,
          comp: comp,
          scope: scope,
          keyBase: 'a2ui.${s.id}.$id',
        );
      case 'ArtifactImage':
        return _Artifact(hub: hub, comp: comp, keyBase: 'a2ui.${s.id}.$id');
    }
    return const SizedBox.shrink();
  }
}

class _Choice extends StatelessWidget {
  const _Choice({
    required this.hub,
    required this.s,
    required this.comp,
    required this.scope,
    required this.keyBase,
    required this.compact,
  });
  final A2uiHub hub;
  final A2uiSurface s;
  final Map comp;
  final String? scope;

  final String keyBase;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final p = (comp['value'] as Map)['path'] as String;
    final multiple = comp['multiple'] == true;
    final cur = s.read(p, scope: scope);
    final selected = multiple
        ? {for (final x in (cur is List ? cur : const [])) '$x'}
        : {'${cur ?? ''}'};
    final options = (comp['options'] as List).cast<Map>();
    final chips = Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final o in options)
          FilterChip(
            key: ValueKey('$keyBase.${o['value']}'),
            label: Text('${o['label']}', style: const TextStyle(fontSize: 12)),
            selected: selected.contains(o['value']),
            showCheckmark: multiple,
            onSelected: (on) {
              if (multiple) {
                final next = [
                  for (final x in options)
                    if ((x['value'] == o['value'])
                        ? on
                        : selected.contains(x['value']))
                      x['value'] as String,
                ];
                hub.input(s.id, p, next, scope: scope);
              } else if (on) {
                hub.input(s.id, p, o['value'], scope: scope);
              }
            },
          ),
      ],
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '${comp['label']}',
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: c.inkSoft,
          ),
        ),
        const SizedBox(height: 6),
        if (options.length > 12)
          ConstrainedBox(
            constraints: BoxConstraints(maxHeight: compact ? 150 : 220),
            child: SingleChildScrollView(child: chips),
          )
        else
          chips,
      ],
    );
  }
}

class _DateTime extends StatelessWidget {
  const _DateTime({
    required this.hub,
    required this.s,
    required this.comp,
    required this.scope,
    required this.keyBase,
  });
  final A2uiHub hub;
  final A2uiSurface s;
  final Map comp;
  final String? scope;

  final String keyBase;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final p = (comp['value'] as Map)['path'] as String;
    final cur = '${s.read(p, scope: scope) ?? ''}';
    final isTime = comp['mode'] == 'time';
    return Row(
      children: [
        Expanded(
          child: Text(
            '${comp['label']}',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: c.inkSoft,
            ),
          ),
        ),
        OutlinedButton.icon(
          key: ValueKey(keyBase),
          icon: Icon(
            isTime ? Icons.schedule_rounded : Icons.event_rounded,
            size: 16,
          ),
          label: Text(cur.isEmpty ? 'Pick' : cur),
          onPressed: () async {
            if (isTime) {
              final parts = cur.split(':');
              final t = await showTimePicker(
                context: context,
                initialTime: TimeOfDay(
                  hour: int.tryParse(parts.first) ?? 9,
                  minute: parts.length > 1 ? int.tryParse(parts[1]) ?? 0 : 0,
                ),
              );
              if (t != null) {
                hub.input(
                  s.id,
                  p,
                  '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}',
                  scope: scope,
                );
              }
            } else {
              final now = DateTime.now();
              final d = await showDatePicker(
                context: context,
                initialDate: DateTime.tryParse(cur) ?? now,
                firstDate: DateTime(now.year - 1),
                lastDate: DateTime(now.year + 3),
              );
              if (d != null) {
                hub.input(
                  s.id,
                  p,
                  d.toIso8601String().substring(0, 10),
                  scope: scope,
                );
              }
            }
          },
        ),
      ],
    );
  }
}

class _Field extends StatefulWidget {
  const _Field({
    required this.hub,
    required this.s,
    required this.comp,
    required this.scope,
    required this.keyBase,
  });
  final A2uiHub hub;
  final A2uiSurface s;
  final Map comp;
  final String? scope;

  final String keyBase;

  @override
  State<_Field> createState() => _FieldState();
}

class _FieldState extends State<_Field> {
  late final TextEditingController _ctl;
  String get _path => (widget.comp['value'] as Map)['path'] as String;

  @override
  void initState() {
    super.initState();
    _ctl = TextEditingController(
      text: '${widget.s.read(_path, scope: widget.scope) ?? ''}',
    );
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final max = (widget.comp['maxLength'] as int?) ?? 500;
    return TextField(
      key: ValueKey(widget.keyBase),
      controller: _ctl,
      maxLength: max,
      maxLines: widget.comp['multiline'] == true ? 3 : 1,
      decoration: InputDecoration(
        labelText: '${widget.comp['label']}',
        isDense: true,
      ),
      onChanged: (v) =>
          widget.hub.input(widget.s.id, _path, v, scope: widget.scope),
    );
  }
}

class _Artifact extends StatefulWidget {
  const _Artifact({
    required this.hub,
    required this.comp,
    required this.keyBase,
  });
  final A2uiHub hub;
  final Map comp;
  final String keyBase;

  @override
  State<_Artifact> createState() => _ArtifactState();
}

class _ArtifactState extends State<_Artifact> {
  late Future<Uint8List> _bytes = widget.hub.artifact(
    widget.comp['artifactId'] as int,
    widget.comp['sha256'] as String,
  );

  @override
  void didUpdateWidget(_Artifact old) {
    super.didUpdateWidget(old);
    if (old.comp['sha256'] != widget.comp['sha256']) {
      _bytes = widget.hub.artifact(
        widget.comp['artifactId'] as int,
        widget.comp['sha256'] as String,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        FutureBuilder<Uint8List>(
          future: _bytes,
          builder: (context, snap) {
            if (snap.hasError) {
              return Text(
                'The image was not shown: its bytes do not match the reviewed version.',
                key: ValueKey('${widget.keyBase}.refused'),
                style: TextStyle(color: c.danger, fontSize: 13),
              );
            }
            if (!snap.hasData) {
              return const SizedBox(
                height: 120,
                child: Center(child: CircularProgressIndicator()),
              );
            }
            return ClipRRect(
              borderRadius: BorderRadius.circular(UriRadius.sm),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 320),
                child: Image.memory(
                  snap.data!,
                  key: ValueKey(widget.keyBase),
                  gaplessPlayback: true,
                ),
              ),
            );
          },
        ),
        if (widget.comp['caption'] != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '${widget.comp['caption']}',
              style: TextStyle(fontSize: 11, color: c.inkFaint),
            ),
          ),
      ],
    );
  }
}

/// The owner-visible notices of the hub (refusals, unavailable authority).
class A2uiNotices extends StatelessWidget {
  const A2uiNotices({super.key, required this.hub});
  final A2uiHub hub;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: hub,
      builder: (context, _) {
        if (hub.notices.isEmpty) return const SizedBox.shrink();
        final c = UriColors.of(context);
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < hub.notices.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Container(
                  key: ValueKey('a2ui.notice.$i'),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: c.warningSoft,
                    borderRadius: BorderRadius.circular(UriRadius.sm),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          hub.notices[i],
                          style: TextStyle(color: c.ink, fontSize: 13),
                        ),
                      ),
                      IconButton(
                        visualDensity: VisualDensity.compact,
                        icon: const Icon(Icons.close_rounded, size: 16),
                        onPressed: () => hub.dismissNotice(i),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}
