import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

/// UIV2-F3: a Column with fixed parts (header, tags, toolbar, banners) and
/// one flexible scrolling body never overflows while the window shrinks into
/// Companion or stays very short. At or above [minHeight] (and with unbounded
/// height) [child] is laid out exactly as before. Below it, [child] fills the
/// height when its fixed parts fit and otherwise scrolls as a whole at its
/// smallest useful height. Mark the flexible body with [ShortIntrinsic] so its
/// own (possibly long or unmeasurable) content does not count as needed height.
class ScrollWhenShort extends StatelessWidget {
  const ScrollWhenShort({super.key, required this.minHeight, this.minHeightForWidth, required this.child});
  final double minHeight;

  /// When given, replaces [minHeight] for content whose fixed parts wrap onto
  /// more lines when narrow. Overshooting only switches to scroll mode early.
  final double Function(double width)? minHeightForWidth;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, box) {
        final min = minHeightForWidth != null && box.maxWidth.isFinite ? minHeightForWidth!(box.maxWidth) : minHeight;
        if (!box.maxHeight.isFinite || box.maxHeight >= min) return child;
        return CustomScrollView(
          key: const ValueKey('scroll-when-short'),
          slivers: [SliverFillRemaining(hasScrollBody: false, child: child)],
        );
      },
    );
  }
}

/// Reports [height] as the intrinsic height of a flexible scrolling body
/// (its smallest useful size) without measuring its content; layout is
/// unchanged. See [ScrollWhenShort].
class ShortIntrinsic extends SingleChildRenderObjectWidget {
  const ShortIntrinsic({super.key, this.height = 96, required Widget super.child});
  final double height;

  @override
  RenderObject createRenderObject(BuildContext context) => RenderShortIntrinsic(height);

  @override
  void updateRenderObject(BuildContext context, RenderShortIntrinsic renderObject) {
    renderObject.height = height;
  }
}

class RenderShortIntrinsic extends RenderProxyBox {
  RenderShortIntrinsic(this._height);
  double _height;
  set height(double v) {
    if (v == _height) return;
    _height = v;
    markNeedsLayout();
  }

  @override
  double computeMinIntrinsicHeight(double width) => _height;

  @override
  double computeMaxIntrinsicHeight(double width) => _height;
}
