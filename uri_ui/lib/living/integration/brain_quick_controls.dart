import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'oi_conversation.dart';

/// Brain quick controls (BRAIN-QUICK-CONTROLS): Thinking, Vision and Context
/// next to the Brain status line.
///
/// * Thinking Auto / Off / On is the per-turn depth (no reload).
/// * Vision and Context choose a measured Runtime v1 profile; a change is a
///   controlled Brain reload (about 30 s). The conversation is kept.
/// * Every label shows what RUNS (the live profile), never only what was
///   asked for: while a switch is under way the chips say so and are disabled.
class OiQuickControls extends StatelessWidget {
  const OiQuickControls({super.key, required this.conversation});
  final OiConversation conversation;

  static String contextLabel(int ctx) => '${ctx ~/ 1024}K';

  static String thinkingLabel(OiDepth d) => switch (d) {
        OiDepth.auto => 'Thinking: Auto',
        OiDepth.fast => 'Thinking: Off',
        OiDepth.normal => 'Thinking: On',
        OiDepth.deep => 'Thinking: stronger tool',
      };

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final conv = conversation;
    final active = conv.activeProfile;
    final options = [
      for (final o in (conv.profileOffer['options'] as List? ?? const []))
        if (o is Map) o.cast<String, dynamic>(),
    ];
    final hasProfiles = options.isNotEmpty;
    final switching = conv.profileSwitching;
    final locked = conv.busy || conv.restarting || switching || active == null;
    final style = TextStyle(color: c.ink, fontSize: 12);

    Widget chip({required Key key, required IconData icon, required String label, String? tooltip,
        bool on = false, VoidCallback? onTap}) {
      return Tooltip(
        message: tooltip ?? '',
        child: InkWell(
          key: key,
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: on ? c.accentSoft : c.surfaceSunken,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: on ? c.accent : c.border),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(icon, size: 13, color: onTap == null ? c.inkFaint : (on ? c.accent : c.inkSoft)),
              const SizedBox(width: 4),
              Flexible(
                child: Text(label,
                    overflow: TextOverflow.ellipsis,
                    softWrap: false,
                    style: style.copyWith(color: onTap == null ? c.inkFaint : c.ink)),
              ),
            ]),
          ),
        ),
      );
    }

    final thinking = PopupMenuButton<OiDepth>(
      key: const ValueKey('oi-depth'),
      tooltip: 'Thinking: how much the Brain reasons before it answers. Applies to the next message, no reload.',
      initialValue: conv.depth,
      onSelected: conv.setDepth,
      itemBuilder: (_) => const [
        PopupMenuItem(value: OiDepth.auto, child: Text('Auto · URI decides per request')),
        PopupMenuItem(value: OiDepth.fast, child: Text('Off · fastest replies')),
        PopupMenuItem(value: OiDepth.normal, child: Text('On · reasons first (slower, more careful)')),
        PopupMenuItem(value: OiDepth.deep, child: Text('Deep · offer a stronger tool for this request')),
      ],
      child: IgnorePointer(
        child: chip(
          key: const ValueKey('oi-qc-thinking'),
          icon: Icons.psychology_alt_outlined,
          label: thinkingLabel(conv.depth),
          on: conv.depth == OiDepth.normal,
          onTap: () {},
        ),
      ),
    );

    if (!hasProfiles) return thinking;

    final vision = active?['vision'] == true;
    final ctx = (active?['context'] as num?)?.toInt();
    final String visionText;
    if (switching) {
      visionText = 'Vision: switching…';
    } else if (active == null) {
      visionText = 'Vision: unknown';
    } else if (vision && !conv.visionLive) {
      visionText = 'Vision: starting…';
    } else {
      visionText = vision ? 'Vision: On' : 'Vision: Off';
    }
    final visionChip = chip(
      key: const ValueKey('oi-qc-vision'),
      icon: vision ? Icons.visibility_outlined : Icons.visibility_off_outlined,
      label: visionText,
      on: vision && conv.visionLive && !switching,
      tooltip: vision
          ? 'Vision lets the Brain see images you attach. Turning it off reloads the Brain (about 30 s) and '
              'frees GPU memory. Your conversation is kept.'
          : 'Turn Vision on to ask about images. The Brain reloads (about 30 s); your conversation is kept.',
      onTap: locked ? null : () => _switch(context, vision: !vision, context_: _contextFor(options, !vision, ctx)),
    );

    final contexts = [
      for (final o in options)
        if (o['vision'] == vision && o['speed'] == (active?['speed'] == true)) o,
    ];
    final contextChip = PopupMenuButton<int>(
      key: const ValueKey('oi-qc-context-menu'),
      enabled: !locked,
      tooltip: 'Context: how much of the conversation and documents the Brain can keep in view. '
          'Changing it reloads the Brain (about 30 s).',
      initialValue: ctx,
      onSelected: (v) => _switch(context, vision: vision, context_: v, speed: active?['speed'] == true),
      itemBuilder: (_) => [
        for (final o in contexts)
          PopupMenuItem(
            value: (o['context'] as num).toInt(),
            child: Text('${contextLabel((o['context'] as num).toInt())}'
                '${o['tight'] == true ? ' · tight on GPU memory' : ''}'),
          ),
      ],
      child: IgnorePointer(
        child: chip(
          key: const ValueKey('oi-qc-context'),
          icon: Icons.notes_rounded,
          label: ctx == null ? 'Context: unknown' : 'Context: ${contextLabel(ctx)}',
          onTap: locked ? null : () {},
        ),
      ),
    );

    return Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
      thinking,
      visionChip,
      contextChip,
      if (active?['speed'] == true)
        Text('Speed boost on', key: const ValueKey('oi-qc-speed-on'), style: TextStyle(color: c.inkSoft, fontSize: 11)),
      for (final img in conv.pendingImages)
        InputChip(
          key: ValueKey('oi-qc-image-${img.name}'),
          avatar: const Icon(Icons.image_outlined, size: 14),
          label: Text(img.name, style: const TextStyle(fontSize: 11), overflow: TextOverflow.ellipsis),
          onDeleted: () => conv.removeImage(img),
          visualDensity: VisualDensity.compact,
        ),
    ]);
  }

  /// The context to keep when Vision is toggled: the same if offered, else the
  /// largest offered context below it, else the smallest offered one.
  static int _contextFor(List<Map<String, dynamic>> options, bool vision, int? current) {
    final ctxs = [
      for (final o in options)
        if (o['vision'] == vision && o['speed'] == false) (o['context'] as num).toInt(),
    ]..sort();
    if (ctxs.isEmpty) return current ?? 32768;
    if (current != null && ctxs.contains(current)) return current;
    final below = ctxs.where((x) => current != null && x < current);
    return below.isNotEmpty ? below.last : ctxs.first;
  }

  Future<void> _switch(BuildContext context, {required bool vision, required int context_, bool speed = false}) async {
    final conv = conversation;
    final what = '${vision ? 'Vision on' : 'Vision off'}, ${contextLabel(context_)} context${speed ? ', speed boost' : ''}';
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const ValueKey('oi-qc-confirm'),
        title: Text('Switch the Brain to $what?'),
        content: const Text('The Brain reloads, which takes about 30 seconds. Your conversation stays; the first '
            'reply afterwards can take longer while the Brain reads it again.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          FilledButton(
            key: const ValueKey('oi-qc-confirm-yes'),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Switch'),
          ),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    var refusal = await conv.setProfile(vision: vision, context: context_, speed: speed);
    if (refusal == 'CONTEXT_SMALLER_THAN_CONVERSATION' && context.mounted) {
      final shrink = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          key: const ValueKey('oi-qc-shrink'),
          title: const Text('This conversation is longer than the new context'),
          content: const Text('URI keeps the whole conversation, but the Brain will only see its most recent part. '
              'Switch anyway?'),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Keep current context')),
            FilledButton(
              key: const ValueKey('oi-qc-shrink-yes'),
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('Switch anyway'),
            ),
          ],
        ),
      );
      if (shrink != true || !context.mounted) return;
      refusal = await conv.setProfile(vision: vision, context: context_, speed: speed, confirmShrink: true);
    }
    if (refusal != null && context.mounted) {
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text(profileRefusalText(refusal))));
    }
  }
}

/// Plain words for a refused Vision / Context change.
String profileRefusalText(String code) => switch (code) {
      'TURN_IN_PROGRESS' => 'Not switched: URI is still answering. Try again when it has finished.',
      'BRAIN_REQUEST_PENDING' => 'Not switched: the Brain is already reloading.',
      'BRAIN_HOST_NOT_RUNNING' => 'Not switched: the Brain host is not running. Restart URI.',
      'CONTEXT_SMALLER_THAN_CONVERSATION' => 'Not switched: the conversation is longer than that context.',
      'PROFILE_NOT_OFFERED' || 'SPEED_NEEDS_VISION_OFF' => 'Not switched: that combination does not fit the GPU.',
      _ => 'Not switched: URI could not change the Brain right now ($code).',
    };

/// Speed boost (MTP draft) in Settings: optional, offered only with Vision off
/// at the contexts where it was measured to fit. Vision always has priority.
class OiSpeedBoostTile extends StatelessWidget {
  const OiSpeedBoostTile({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final conv = conversation;
    final active = conv.activeProfile;
    final options = [
      for (final o in (conv.profileOffer['options'] as List? ?? const []))
        if (o is Map) o.cast<String, dynamic>(),
    ];
    if (options.isEmpty || active == null) return const SizedBox.shrink();
    final ctx = (active['context'] as num).toInt();
    final available = active['vision'] == false &&
        options.any((o) => o['vision'] == false && o['speed'] == true && o['context'] == ctx);
    final on = active['speed'] == true;
    final locked = conv.busy || conv.restarting || conv.profileSwitching;
    return SwitchListTile(
      key: const ValueKey('ws-speed-boost'),
      dense: true,
      contentPadding: EdgeInsets.zero,
      title: Text('Speed boost (MTP)', style: TextStyle(color: c.ink, fontSize: 13)),
      subtitle: Text(
        available || on
            ? 'Faster replies for structured work. It uses the GPU memory Vision needs, so it is only available '
                'with Vision off. Switching reloads the Brain (about 30 s).'
            : 'Available with Vision off at 16K or 32K context. Vision has priority for GPU memory.',
        style: TextStyle(color: c.inkSoft, fontSize: 12),
      ),
      value: on,
      onChanged: (available || on) && !locked
          ? (v) async {
              final refusal = await conv.setProfile(vision: false, context: ctx, speed: v);
              if (refusal != null && context.mounted) {
                ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text(profileRefusalText(refusal))));
              }
            }
          : null,
    );
  }
}

/// Image extensions the composer sends to the Brain (Vision On).
const oiImageTypes = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'};

String? oiImageMime(String filename) {
  final dot = filename.lastIndexOf('.');
  return dot < 0 ? null : oiImageTypes[filename.substring(dot + 1).toLowerCase()];
}

/// Scales a picture so a turn fits the worker's frame limit. A file already
/// small enough is sent unchanged; otherwise it is decoded, scaled to at most
/// [maxSide] pixels and re-encoded as PNG, shrinking until it fits [limit].
Future<OiImage?> prepareOiImage(String name, Uint8List bytes, {int limit = OiConversation.maxImageBytes,
    int maxSide = 1280}) async {
  final mime = oiImageMime(name);
  if (mime == null) return null;
  if (bytes.length <= limit) return OiImage(name: name, mime: mime, bytes: bytes);
  var side = maxSide;
  while (side >= 256) {
    final codec = await ui.instantiateImageCodec(bytes);
    final frame = await codec.getNextFrame();
    final w = frame.image.width, h = frame.image.height;
    frame.image.dispose();
    final scale = side / (w > h ? w : h);
    final scaled = await ui.instantiateImageCodec(bytes,
        targetWidth: scale < 1 ? (w * scale).round() : null, targetHeight: scale < 1 ? (h * scale).round() : null);
    final img = (await scaled.getNextFrame()).image;
    final png = await img.toByteData(format: ui.ImageByteFormat.png);
    img.dispose();
    if (png != null && png.lengthInBytes <= limit) {
      final base = name.contains('.') ? name.substring(0, name.lastIndexOf('.')) : name;
      return OiImage(name: '$base.png', mime: 'image/png', bytes: png.buffer.asUint8List());
    }
    side = (side * 0.75).round();
  }
  return null;
}

/// Composer hook: scales the picked picture and adds it to the next turn, or
/// says plainly why not (Vision off, too many, too large). Nothing is sent yet.
Future<void> attachOiImage(BuildContext context, OiConversation conv, String name, List<int> bytes) async {
  String? refusal;
  if (!conv.visionLive) {
    refusal = 'VISION_OFF';
  } else {
    final used = conv.pendingImages.fold<int>(0, (n, i) => n + i.bytes.length);
    final img = await prepareOiImage(name, Uint8List.fromList(bytes), limit: OiConversation.maxImageBytes - used);
    refusal = img == null ? 'IMAGES_TOO_LARGE' : conv.attachImage(img);
  }
  if (refusal == null || !context.mounted) return;
  final text = switch (refusal) {
    'VISION_OFF' => 'Vision is off, so the Brain cannot see images. Turn Vision on next to the Brain status first.',
    'IMAGES_INVALID' => 'At most ${OiConversation.maxImages} images can go with one message.',
    _ => 'That image is too large to send. Try a smaller one.',
  };
  ScaffoldMessenger.maybeOf(context)?.showSnackBar(SnackBar(content: Text(text)));
}
