// URI patch (PATCHES.md, P1). See uri_security.h.
#include "uri_security.h"

#include <wrl.h>

#include <algorithm>
#include <cwctype>
#include <sstream>

#include "util/string_converter.h"

using namespace Microsoft::WRL;

namespace uri_security {

namespace {

std::string JsonEscape(const std::string& s) {
  std::string out;
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') {
      out += '\\';
      out += static_cast<char>(c);
    } else if (c < 0x20) {
      char buf[8];
      snprintf(buf, sizeof(buf), "\\u%04x", c);
      out += buf;
    } else {
      out += static_cast<char>(c);
    }
  }
  return out;
}

bool IsAboutBlank(const std::wstring& uri) { return uri == L"about:blank"; }

}  // namespace

std::string OriginOf(const std::wstring& uri) {
  std::wstring lower(uri.size(), L'\0');
  std::transform(uri.begin(), uri.end(), lower.begin(), [](wchar_t c) { return std::towlower(c); });
  std::wstring scheme;
  size_t rest = 0;
  if (lower.rfind(L"https://", 0) == 0) {
    scheme = L"https";
    rest = 8;
  } else if (lower.rfind(L"http://", 0) == 0) {
    scheme = L"http";
    rest = 7;
  } else {
    return "";
  }
  size_t end = lower.find_first_of(L"/?#", rest);
  std::wstring authority = lower.substr(rest, end == std::wstring::npos ? std::wstring::npos : end - rest);
  if (authority.empty() || authority.find(L'@') != std::wstring::npos ||
      authority.find_first_of(L" \\\t\r\n") != std::wstring::npos) {
    return "";   // userinfo or odd characters: refuse rather than guess
  }
  if ((scheme == L"https" && authority.size() > 4 && authority.ends_with(L":443")) ||
      (scheme == L"http" && authority.size() > 3 && authority.ends_with(L":80"))) {
    authority = authority.substr(0, authority.rfind(L':'));
  }
  return util::Utf8FromUtf16((scheme + L"://" + authority).c_str());
}

void Policy::Set(std::set<std::string> navigation_origins, std::set<std::string> message_origins) {
  std::lock_guard<std::mutex> lock(mutex_);
  navigation_origins_ = std::move(navigation_origins);
  message_origins_ = std::move(message_origins);
  configured_ = true;
}

bool Policy::IsConfigured() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return configured_;
}

bool Policy::AllowsNavigation(const std::wstring& uri) const {
  if (IsAboutBlank(uri)) return true;
  std::lock_guard<std::mutex> lock(mutex_);
  const std::string origin = OriginOf(uri);
  return configured_ && !origin.empty() && navigation_origins_.count(origin) > 0;
}

bool Policy::AllowsRequest(const std::wstring& uri) const {
  std::lock_guard<std::mutex> lock(mutex_);
  const std::string origin = OriginOf(uri);
  return configured_ && !origin.empty() && navigation_origins_.count(origin) > 0;
}

bool Policy::AllowsMessageFrom(const std::wstring& source_uri) const {
  std::lock_guard<std::mutex> lock(mutex_);
  const std::string origin = OriginOf(source_uri);
  return configured_ && !origin.empty() && message_origins_.count(origin) > 0;
}

void Policy::Count(const char* what, const std::wstring& uri) {
  std::lock_guard<std::mutex> lock(mutex_);
  const std::string w(what);
  if (w == "request") ++blocked_requests_;
  else if (w == "navigation") ++cancelled_navigations_;
  else if (w == "frame_navigation") ++cancelled_frame_navigations_;
  else if (w == "external_scheme") ++cancelled_external_schemes_;
  else if (w == "window") ++denied_windows_;
  else if (w == "download") ++cancelled_downloads_;
  else if (w == "message") ++dropped_messages_;
  else if (w == "permission") ++denied_permissions_;
  std::string u = util::Utf8FromUtf16(uri.c_str());
  if (u.size() > 200) u = u.substr(0, 200);
  recent_.push_back(w + " " + u);
  while (recent_.size() > 64) recent_.pop_front();
}

void Policy::SetSettingsJson(std::string json) {
  std::lock_guard<std::mutex> lock(mutex_);
  settings_json_ = std::move(json);
}

std::string Policy::ReportJson() const {
  std::lock_guard<std::mutex> lock(mutex_);
  std::ostringstream o;
  o << "{\"configured\":" << (configured_ ? "true" : "false") << ",\"blocked_requests\":" << blocked_requests_
    << ",\"cancelled_navigations\":" << cancelled_navigations_
    << ",\"cancelled_frame_navigations\":" << cancelled_frame_navigations_
    << ",\"cancelled_external_schemes\":" << cancelled_external_schemes_ << ",\"denied_windows\":" << denied_windows_
    << ",\"cancelled_downloads\":" << cancelled_downloads_ << ",\"dropped_messages\":" << dropped_messages_
    << ",\"denied_permissions\":" << denied_permissions_ << ",\"settings\":"
    << (settings_json_.empty() ? "{}" : settings_json_) << ",\"recent\":[";
  bool first = true;
  for (const auto& r : recent_) {
    o << (first ? "" : ",") << "\"" << JsonEscape(r) << "\"";
    first = false;
  }
  o << "]}";
  return o.str();
}

void Install(ICoreWebView2* webview, Policy* policy, Tokens* tokens) {
  // Settings. Read back so the report shows what the runtime actually holds.
  wil::com_ptr<ICoreWebView2Settings> settings;
  std::ostringstream s;
  if (SUCCEEDED(webview->get_Settings(settings.put())) && settings) {
#ifdef NDEBUG
    settings->put_AreDevToolsEnabled(FALSE);
#endif
    settings->put_AreHostObjectsAllowed(FALSE);
    settings->put_AreDefaultScriptDialogsEnabled(FALSE);
    settings->put_IsWebMessageEnabled(TRUE);
    if (auto s3 = wil::com_ptr<ICoreWebView2Settings>(settings).try_query<ICoreWebView2Settings3>()) {
#ifdef NDEBUG
      s3->put_AreBrowserAcceleratorKeysEnabled(FALSE);
#endif
    }
    if (auto s4 = wil::com_ptr<ICoreWebView2Settings>(settings).try_query<ICoreWebView2Settings4>()) {
      s4->put_IsPasswordAutosaveEnabled(FALSE);
      s4->put_IsGeneralAutofillEnabled(FALSE);
    }
    if (auto s6 = wil::com_ptr<ICoreWebView2Settings>(settings).try_query<ICoreWebView2Settings6>()) {
      s6->put_IsSwipeNavigationEnabled(FALSE);
    }
    BOOL devtools = TRUE, host_objects = TRUE, dialogs = TRUE, accel = TRUE, password = TRUE, autofill = TRUE;
    settings->get_AreDevToolsEnabled(&devtools);
    settings->get_AreHostObjectsAllowed(&host_objects);
    settings->get_AreDefaultScriptDialogsEnabled(&dialogs);
    if (auto s3 = wil::com_ptr<ICoreWebView2Settings>(settings).try_query<ICoreWebView2Settings3>()) {
      s3->get_AreBrowserAcceleratorKeysEnabled(&accel);
    }
    if (auto s4 = wil::com_ptr<ICoreWebView2Settings>(settings).try_query<ICoreWebView2Settings4>()) {
      s4->get_IsPasswordAutosaveEnabled(&password);
      s4->get_IsGeneralAutofillEnabled(&autofill);
    }
    s << "{\"dev_tools\":" << (devtools ? "true" : "false") << ",\"host_objects\":" << (host_objects ? "true" : "false")
      << ",\"script_dialogs\":" << (dialogs ? "true" : "false")
      << ",\"browser_accelerator_keys\":" << (accel ? "true" : "false")
      << ",\"password_autosave\":" << (password ? "true" : "false")
      << ",\"general_autofill\":" << (autofill ? "true" : "false") << "}";
  }
  policy->SetSettingsJson(s.str());

  // WebRTC sends UDP that WebResourceRequested and the proxy do not see (found by the real-runtime probe,
  // 2026-10-11). Remove its constructors in every document and child frame before any page script runs.
  webview->AddScriptToExecuteOnDocumentCreated(
      L"(() => { for (const n of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', "
      L"'RTCIceTransport', 'RTCSctpTransport', 'RTCDtlsTransport', 'WebTransport']) { try { "
      L"Object.defineProperty(window, n, "
      L"{ value: undefined, configurable: false, writable: false }); } catch (e) {} } })();",
      nullptr);

  // Every network request, every context.
  webview->AddWebResourceRequestedFilter(L"*", COREWEBVIEW2_WEB_RESOURCE_CONTEXT_ALL);
  wil::com_ptr<ICoreWebView2Environment> env;
  if (auto w2 = wil::com_ptr<ICoreWebView2>(webview).try_query<ICoreWebView2_2>()) {
    w2->get_Environment(env.put());
  }
  webview->add_WebResourceRequested(
      Callback<ICoreWebView2WebResourceRequestedEventHandler>(
          [policy, env](ICoreWebView2*, ICoreWebView2WebResourceRequestedEventArgs* args) -> HRESULT {
            wil::com_ptr<ICoreWebView2WebResourceRequest> request;
            wil::unique_cotaskmem_string uri;
            if (FAILED(args->get_Request(request.put())) || !request || FAILED(request->get_Uri(&uri))) {
              return S_OK;
            }
            const std::wstring u = uri.get() ? uri.get() : L"";
            if (policy->AllowsRequest(u)) return S_OK;
            policy->Count("request", u);
            wil::com_ptr<ICoreWebView2WebResourceResponse> response;
            if (env && SUCCEEDED(env->CreateWebResourceResponse(nullptr, 403, L"Blocked by URI Office",
                                                                L"Content-Type: text/plain", response.put()))) {
              args->put_Response(response.get());
            }
            return S_OK;
          })
          .Get(),
      &tokens->web_resource_requested);

  webview->add_NavigationStarting(
      Callback<ICoreWebView2NavigationStartingEventHandler>(
          [policy](ICoreWebView2*, ICoreWebView2NavigationStartingEventArgs* args) -> HRESULT {
            wil::unique_cotaskmem_string uri;
            args->get_Uri(&uri);
            const std::wstring u = uri.get() ? uri.get() : L"";
            if (!policy->AllowsNavigation(u)) {
              args->put_Cancel(TRUE);
              policy->Count("navigation", u);
            }
            return S_OK;
          })
          .Get(),
      &tokens->navigation_starting);

  webview->add_FrameNavigationStarting(
      Callback<ICoreWebView2NavigationStartingEventHandler>(
          [policy](ICoreWebView2*, ICoreWebView2NavigationStartingEventArgs* args) -> HRESULT {
            wil::unique_cotaskmem_string uri;
            args->get_Uri(&uri);
            const std::wstring u = uri.get() ? uri.get() : L"";
            if (!policy->AllowsNavigation(u)) {
              args->put_Cancel(TRUE);
              policy->Count("frame_navigation", u);
            }
            return S_OK;
          })
          .Get(),
      &tokens->frame_navigation_starting);

  if (auto w18 = wil::com_ptr<ICoreWebView2>(webview).try_query<ICoreWebView2_18>()) {
    w18->add_LaunchingExternalUriScheme(
        Callback<ICoreWebView2LaunchingExternalUriSchemeEventHandler>(
            [policy](ICoreWebView2*, ICoreWebView2LaunchingExternalUriSchemeEventArgs* args) -> HRESULT {
              wil::unique_cotaskmem_string uri;
              args->get_Uri(&uri);
              args->put_Cancel(TRUE);
              policy->Count("external_scheme", uri.get() ? uri.get() : L"");
              return S_OK;
            })
            .Get(),
        &tokens->launching_external_uri_scheme);
  }
}

void Uninstall(ICoreWebView2* webview, Tokens* tokens) {
  if (!webview) return;
  webview->remove_WebResourceRequested(tokens->web_resource_requested);
  webview->remove_NavigationStarting(tokens->navigation_starting);
  webview->remove_FrameNavigationStarting(tokens->frame_navigation_starting);
  if (auto w18 = wil::com_ptr<ICoreWebView2>(webview).try_query<ICoreWebView2_18>()) {
    w18->remove_LaunchingExternalUriScheme(tokens->launching_external_uri_scheme);
  }
}

}  // namespace uri_security
