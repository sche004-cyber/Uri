import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';

/// UIV2-F3: a Column with fixed parts (header, tags, toolbar, banners) and
/// one flexible scrolling body never overflows while the window shrinks into
/// Companion or stays short. When the height is enough, [child] fills it
/// exactly as before; when the fixed parts alone do not fit, the whole
/// [child] scrolls at its smallest useful height. Mark the flexible body
/// with [ShortIntrinsic] so its own (possibly long or unmeasurable) content
/// does not count as needed height.
class ScrollWhenShort extends StatelessWidget {
  const ScrollWhenShort({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(
      key: const ValueKey('scroll-when-short'),
      slivers: [SliverFillRemaining(hasScrollBody: false, child: child)],
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
