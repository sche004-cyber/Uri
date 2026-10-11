#include "webview_host.h"

#include <wrl.h>

#include <future>
#include <iostream>

#include "util/rohelper.h"
#include "util/string_converter.h"

using namespace Microsoft::WRL;

// static
std::unique_ptr<WebviewHost> WebviewHost::Create(
    WebviewPlatform* platform, std::optional<std::wstring> user_data_directory,
    std::optional<std::wstring> browser_exe_path,
    std::optional<std::string> arguments) {
  // URI patch P2: options are always created. The user-data folder is opened for exclusive access (no other
  // process, Edge included, may share it), and a browser executable path is never honoured, so only the
  // installed Evergreen WebView2 runtime is used (no bundled or side-loaded Chromium).
  browser_exe_path = std::nullopt;
  wil::com_ptr<CoreWebView2EnvironmentOptions> opts =
      Microsoft::WRL::Make<CoreWebView2EnvironmentOptions>();
  if (auto opts2 = opts.try_query<ICoreWebView2EnvironmentOptions2>()) {
    opts2->put_ExclusiveUserDataFolderAccess(TRUE);
  }
  // URI patch P2: no network from this browser, whatever the page does. WebResourceRequested does not see
  // WebSocket handshakes (found by the real-runtime probe, 2026-10-11), so every connection, loopback included,
  // is sent to an unreachable proxy. The virtual-host page is served in-process and is unaffected. WebRTC may not
  // use direct UDP. These arguments always come first; Dart-supplied ones are appended after them.
  std::wstring warguments =
      L"--proxy-server=http://0.0.0.0:1 --proxy-bypass-list=<-loopback> "
      L"--force-webrtc-ip-handling-policy=disable_non_proxied_udp";
  if (arguments.has_value()) {
    warguments += L" " + util::Utf16FromUtf8(arguments.value());
  }
  opts->put_AdditionalBrowserArguments(warguments.c_str());

  std::promise<HRESULT> result_promise;
  wil::com_ptr<ICoreWebView2Environment> env;
  auto result = CreateCoreWebView2EnvironmentWithOptions(
      browser_exe_path.has_value() ? browser_exe_path->c_str() : nullptr,
      user_data_directory.has_value() ? user_data_directory->c_str() : nullptr,
      opts.get(),
      Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>(
          [&promise = result_promise, &ptr = env](
              HRESULT r, ICoreWebView2Environment* env) -> HRESULT {
            // The in-parameter is only borrowed for the duration of this
            // call, so take a real reference (AddRef) and publish it before
            // unblocking the waiting thread below.
            ptr = env;
            promise.set_value(r);
            return S_OK;
          })
          .Get());

  if (SUCCEEDED(result)) {
    // Blocks the calling thread until environment creation settles. This is
    // a one-time, fast operation and has been the field-proven behavior of
    // this plugin; the completion handler does not depend on this thread's
    // message pump being drained.
    result = result_promise.get_future().get();
    if (SUCCEEDED(result) && env) {
      auto webview_env3 = env.try_query<ICoreWebView2Environment3>();
      if (webview_env3) {
        return std::unique_ptr<WebviewHost>(
            new WebviewHost(platform, std::move(webview_env3)));
      }
    }
  }

  return {};
}

WebviewHost::WebviewHost(WebviewPlatform* platform,
                         wil::com_ptr<ICoreWebView2Environment3> webview_env)
    : webview_env_(webview_env) {
  compositor_ = platform->graphics_context()->CreateCompositor();
}

void WebviewHost::CreateWebview(HWND hwnd, HWND flutter_view_hwnd,
                                bool offscreen_only, bool owns_window,
                                WebviewCreationCallback callback) {
  CreateWebViewCompositionController(
      hwnd, [=, self = this](
                wil::com_ptr<ICoreWebView2CompositionController> controller,
                std::unique_ptr<WebviewCreationError> error) {
        if (controller) {
          std::unique_ptr<Webview> webview(
              new Webview(std::move(controller), self, hwnd, flutter_view_hwnd,
                          owns_window, offscreen_only));
          if (webview->IsValid()) {
            callback(std::move(webview), nullptr);
          } else {
            // The composition controller was created, but the webview itself
            // failed to initialize (unsupported runtime interface or surface
            // creation failure). It would silently no-op every call, so report
            // an error instead of handing back a dead instance.
            callback(nullptr, WebviewCreationError::create(
                                  E_FAIL, "Webview initialization failed."));
          }
        } else {
          callback(nullptr, std::move(error));
        }
      });
}

void WebviewHost::CreateWebViewPointerInfo(
    PointerInfoCreationCallback callback) {
  wil::com_ptr<ICoreWebView2PointerInfo> pointer;
  auto hr = webview_env_->CreateCoreWebView2PointerInfo(pointer.put());

  if (FAILED(hr)) {
    callback(nullptr, WebviewCreationError::create(
                          hr, "CreateWebViewPointerInfo failed."));
  } else {
    callback(std::move(pointer), nullptr);
  }
}

void WebviewHost::CreateWebViewCompositionController(
    HWND hwnd, CompositionControllerCreationCallback callback) {
  auto hr = webview_env_->CreateCoreWebView2CompositionController(
      hwnd,
      Callback<
          ICoreWebView2CreateCoreWebView2CompositionControllerCompletedHandler>(
          [callback](HRESULT hr,
                     ICoreWebView2CompositionController* compositionController)
              -> HRESULT {
            if (SUCCEEDED(hr)) {
              callback(
                  wil::com_ptr<ICoreWebView2CompositionController>(
                      compositionController),
                  nullptr);
            } else {
              callback(nullptr, WebviewCreationError::create(
                                    hr,
                                    "CreateCoreWebView2CompositionController "
                                    "completion handler failed."));
            }

            return S_OK;
          })
          .Get());

  if (FAILED(hr)) {
    callback(nullptr,
             WebviewCreationError::create(
                 hr, "CreateCoreWebView2CompositionController failed."));
  }
}
