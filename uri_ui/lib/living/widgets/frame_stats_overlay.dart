import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../companion/companion_preferences.dart';
import '../companion/frame_clock.dart';

/// The optional performance statistics overlay (Companion Settings).
///
/// Every number is measured, none is a setting echoed back: companion frames
/// actually delivered by the clock, frames the engine actually produced, and
/// their build and raster times from `FrameTiming`. It refreshes once per
/// governor window (2 s), so showing it does not itself add frames.
class FrameStatsOverlay extends StatelessWidget {
  const FrameStatsOverlay({super.key, required this.governor});

  final CompanionFrameGovernor governor;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return IgnorePointer(
      child: ListenableBuilder(
        listenable: governor,
        builder: (context, _) {
          final prefs = governor.preferences;
          final w = governor.lastWindow;
          final cap = governor.effectiveCap;
          String ms(double v) => v.toStringAsFixed(1);
          final lines = <String>[
            'Companion ${governor.clock.deliveredFps.toStringAsFixed(0)} fps'
                ' · target ${cap.toStringAsFixed(0)}'
                ' (${prefs.frameRate.label})',
            if (w != null)
              'App ${w.fps.toStringAsFixed(0)} fps · build p90 ${ms(w.buildP90Ms)} ms'
                  ' · raster p90 ${ms(w.rasterP90Ms)} ms',
            if (w != null)
              'Over ${ms(w.budgetMs)} ms: ${(w.overBudget * 100).toStringAsFixed(1)} %'
                  ' · quality ${prefs.quality.label}'
                  ' · display ${governor.displayHz.toStringAsFixed(0)} Hz',
            if (w == null) 'Measuring…',
          ];
          return Semantics(
            label: 'Performance statistics. ${lines.join('. ')}',
            child: Container(
              key: const ValueKey('frame-stats-overlay'),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
              decoration: BoxDecoration(
                color: c.surfaceSunken.withValues(alpha: 0.9),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: c.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final l in lines)
                    Text(
                      l,
                      style: TextStyle(
                        fontSize: 11,
                        height: 1.35,
                        color: c.inkSoft,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
