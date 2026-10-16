#include "flutter_window.h"

#include <optional>
#include <algorithm>
#include <cmath>
#include <vector>
#include <flutter/standard_method_codec.h>

#include "flutter/generated_plugin_registrant.h"

FlutterWindow::FlutterWindow(const flutter::DartProject& project)
    : project_(project) {}

FlutterWindow::~FlutterWindow() {}

bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  // The size here must match the window dimensions to avoid unnecessary surface
  // creation / destruction in the startup path.
  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  // Ensure that basic setup of the controller was successful.
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  RegisterPlugins(flutter_controller_->engine());
  SetChildContent(flutter_controller_->view()->GetNativeWindow());

  companion_channel_ = std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
      flutter_controller_->engine()->messenger(), "uri/companion_window",
      &flutter::StandardMethodCodec::GetInstance());
  companion_channel_->SetMethodCallHandler([this](const auto& call, auto result) {
    const HWND hwnd = GetHandle();
    auto clamp = [hwnd]() {
      RECT r; GetWindowRect(hwnd, &r);
      MONITORINFO m = {}; m.cbSize = sizeof(m);
      if (!GetMonitorInfo(MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), &m)) return;
      const int w = std::min(r.right - r.left, m.rcWork.right - m.rcWork.left);
      const int h = std::min(r.bottom - r.top, m.rcWork.bottom - m.rcWork.top);
      const int x = std::clamp(static_cast<int>(r.left), static_cast<int>(m.rcWork.left), static_cast<int>(m.rcWork.right) - w);
      const int y = std::clamp(static_cast<int>(r.top), static_cast<int>(m.rcWork.top), static_cast<int>(m.rcWork.bottom) - h);
      if (x != r.left || y != r.top || w != r.right-r.left || h != r.bottom-r.top)
        SetWindowPos(hwnd, nullptr, x, y, w, h, SWP_NOACTIVATE | SWP_NOZORDER);
    };
    if (call.method_name() == "clamp") { clamp(); result->Success(); return; }
    if (call.method_name() == "cursor") {
      POINT pointer;
      if (!GetCursorPos(&pointer) || !ScreenToClient(hwnd, &pointer)) {
        result->Error("CURSOR_UNAVAILABLE"); return;
      }
      const double dpi = GetDpiForWindow(hwnd) / 96.0;
      result->Success(flutter::EncodableValue(flutter::EncodableList{
        flutter::EncodableValue(pointer.x / dpi), flutter::EncodableValue(pointer.y / dpi)})); return;
    }
    if (call.method_name() == "facts") {
      HRGN region = CreateRectRgn(0, 0, 0, 0);
      const int kind = GetWindowRgn(hwnd, region);
      RECT box = {}; GetRgnBox(region, &box);
      flutter::EncodableMap facts;
      facts[flutter::EncodableValue("dpi")] = flutter::EncodableValue(static_cast<int>(GetDpiForWindow(hwnd)));
      facts[flutter::EncodableValue("regionKind")] = flutter::EncodableValue(kind);
      facts[flutter::EncodableValue("cornerHit")] = flutter::EncodableValue(PtInRegion(region, 0, 0) != 0);
      facts[flutter::EncodableValue("regionWidth")] = flutter::EncodableValue(static_cast<int>(box.right-box.left));
      DeleteObject(region); result->Success(flutter::EncodableValue(facts)); return;
    }
    if (call.method_name() != "regions") { result->NotImplemented(); return; }
    const auto* args = std::get_if<flutter::EncodableMap>(call.arguments());
    if (!args) { result->Error("INVALID_LAYOUT"); return; }
    const auto active = args->find(flutter::EncodableValue("active"));
    if (active == args->end() || !std::holds_alternative<bool>(active->second)) {
      result->Error("INVALID_LAYOUT"); return;
    }
    if (!std::get<bool>(active->second)) {
      SetWindowRgn(hwnd, nullptr, TRUE); clamp(); result->Success(); return;
    }
    const double scale = GetDpiForWindow(hwnd) / 96.0;
    // A box is four finite logical coordinates [left, top, right, bottom] in a
    // sane range with right > left and bottom > top. A missing or null region
    // is absent; any malformed one rejects the whole layout (never ignored).
    bool malformed = false;
    auto box = [scale, &malformed](const flutter::EncodableValue& value, int v[4]) -> bool {
      const auto* values = std::get_if<flutter::EncodableList>(&value);
      if (!values || values->size() != 4) { malformed = true; return false; }
      for (size_t i = 0; i < 4; ++i) {
        const auto* number = std::get_if<double>(&(*values)[i]);
        if (!number || !std::isfinite(*number) || std::abs(*number) > 100000.0) { malformed = true; return false; }
        v[i] = static_cast<int>(std::lround(*number * scale));
      }
      if (v[2] <= v[0] || v[3] <= v[1]) { malformed = true; return false; }
      return true;
    };
    auto region = [args, scale, &box](const char* key, bool ellipse) -> HRGN {
      const auto it = args->find(flutter::EncodableValue(key));
      if (it == args->end() || std::holds_alternative<std::monostate>(it->second)) return nullptr;
      int v[4];
      if (!box(it->second, v)) return nullptr;
      return ellipse ? CreateEllipticRgn(v[0], v[1], v[2], v[3])
          : CreateRoundRectRgn(v[0], v[1], v[2], v[3], static_cast<int>(16 * scale), static_cast<int>(16 * scale));
    };
    HRGN orb = region("orb", true);
    if (!orb) { result->Error(malformed ? "INVALID_LAYOUT" : "INVALID_ORB_REGION"); return; }
    // Narrow decoration regions preserve visible arcs without giving the
    // transparent ring interior a desktop hit target.
    HRGN orbit = region("orbit", true);
    if (malformed) { DeleteObject(orb); result->Error("INVALID_LAYOUT"); return; }
    if (orbit) {
      RECT b; GetRgnBox(orbit, &b); DeleteObject(orbit);
      const double cx=(b.left+b.right)/2.0, cy=(b.top+b.bottom)/2.0;
      const double r=(b.right-b.left)/2.0;
      const int stroke=std::max(1, static_cast<int>(std::ceil(scale)));
      HRGN outer=CreateEllipticRgn(b.left-stroke,b.top-stroke,b.right+stroke,b.bottom+stroke);
      HRGN inner=CreateEllipticRgn(b.left+stroke,b.top+stroke,b.right-stroke,b.bottom-stroke);
      CombineRgn(outer,outer,inner,RGN_DIFF); DeleteObject(inner);
      const double arcs[][2] = {{-2.87,.58},{-.84,.57},{.24,.41},{.86,.45},{2.28,.62}};
      for (const auto& arc : arcs) {
        const double a=arc[0];
        std::vector<POINT> points{{static_cast<LONG>(cx),static_cast<LONG>(cy)}};
        for (int n=0;n<=16;++n) {
          const double t=a+arc[1]*n/16;
          points.push_back({static_cast<LONG>(cx+(r+4*scale)*std::cos(t)),static_cast<LONG>(cy+(r+4*scale)*std::sin(t))});
        }
        HRGN wedge=CreatePolygonRgn(points.data(),static_cast<int>(points.size()),WINDING);
        CombineRgn(wedge,wedge,outer,RGN_AND); CombineRgn(orb,orb,wedge,RGN_OR); DeleteObject(wedge);
        const int x=static_cast<int>(cx+r*std::cos(a+.23)), y=static_cast<int>(cy+r*std::sin(a+.23));
        const int d=static_cast<int>(std::ceil((r/scale > 200 ? 4 : 3)*scale));
        HRGN dot=CreateEllipticRgn(x-d,y-d,x+d,y+d); CombineRgn(orb,orb,dot,RGN_OR); DeleteObject(dot);
      }
      DeleteObject(outer);
    }
    HRGN panel = region("panel", false);
    if (panel) { CombineRgn(orb, orb, panel, RGN_OR); DeleteObject(panel); }
    HRGN controls = region("controls", false);
    if (controls) { CombineRgn(orb, orb, controls, RGN_OR); DeleteObject(controls); }
    if (malformed) { DeleteObject(orb); result->Error("INVALID_LAYOUT"); return; }
    const auto buttons_it = args->find(flutter::EncodableValue("buttons"));
    if (buttons_it != args->end() && !std::holds_alternative<std::monostate>(buttons_it->second)) {
      const auto* buttons = std::get_if<flutter::EncodableList>(&buttons_it->second);
      if (!buttons || buttons->size() > 8) { DeleteObject(orb); result->Error("INVALID_LAYOUT"); return; }
      for (const auto& button : *buttons) {
        int v[4];
        if (!box(button, v)) { DeleteObject(orb); result->Error("INVALID_LAYOUT"); return; }
        HRGN r = std::abs((v[2]-v[0])-(v[3]-v[1])) <= 1
            ? CreateEllipticRgn(v[0],v[1],v[2],v[3])
            : CreateRoundRectRgn(v[0],v[1],v[2],v[3],static_cast<int>(16*scale),static_cast<int>(16*scale));
        if (r) { CombineRgn(orb,orb,r,RGN_OR); DeleteObject(r); }
      }
    }
    // Windows owns the region after success; failed transfers must be freed.
    if (!SetWindowRgn(hwnd, orb, TRUE)) { DeleteObject(orb); result->Error("REGION_FAILED"); return; }
    clamp(); result->Success();
  });

  flutter_controller_->engine()->SetNextFrameCallback([&]() {
    this->Show();
  });

  // Flutter can complete the first frame before the "show window" callback is
  // registered. The following call ensures a frame is pending to ensure the
  // window is shown. It is a no-op if the first frame hasn't completed yet.
  flutter_controller_->ForceRedraw();

  return true;
}

void FlutterWindow::OnDestroy() {
  companion_channel_.reset();
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message,
                              WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  if ((message == WM_DPICHANGED || message == WM_DISPLAYCHANGE) && companion_channel_) {
    companion_channel_->InvokeMethod("metricsChanged", std::make_unique<flutter::EncodableValue>());
  }
  // Give Flutter, including plugins, an opportunity to handle window messages.
  if (flutter_controller_) {
    std::optional<LRESULT> result =
        flutter_controller_->HandleTopLevelWindowProc(hwnd, message, wparam,
                                                      lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}
