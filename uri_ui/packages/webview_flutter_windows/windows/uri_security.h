// URI patch (PATCHES.md, P1): host-level lockdown for the URI Office panel. Not part of upstream
// webview_flutter_windows 1.2.0.
//
// Fail-closed and always on. A new webview allows nothing but about:blank until the Dart side calls
// setNetworkPolicy. After that:
//   * every network request (WebResourceRequested, filter "*", all contexts) whose origin is not in
//     navigation_origins gets a 403 response from the host; data: and blob: URLs are handled inside the
//     renderer and never reach this filter;
//   * every top-level and frame navigation (including each redirect hop) to anything other than an allowed
//     origin or about:blank is cancelled; this covers file:, custom schemes and data: navigations;
//   * launching external URI scheme handlers is cancelled;
//   * new windows are always refused, downloads are always cancelled, permission requests are always denied;
//   * web messages are delivered only when the sending document's origin is in message_origins;
//   * WebRTC constructors are removed in every document and child frame before page scripts run;
//   * developer tools and browser accelerator keys are off in release builds; host objects, default script
//     dialogs, password saving and general autofill are off.
// Counters and the last blocked URIs are kept for tests (getSecurityReport).
// This is not a general-purpose browser sandbox; RW1 reuse needs its own qualification.
#pragma once

#include <WebView2.h>
#include <wil/com.h>

#include <deque>
#include <mutex>
#include <set>
#include <string>

namespace uri_security {

// "scheme://host[:port]" in lower case with default ports removed, or "" when |uri| has no origin we accept
// (file:, data:, blob:, custom schemes, malformed input). Only http and https have origins here.
std::string OriginOf(const std::wstring& uri);

struct Tokens {
  EventRegistrationToken web_resource_requested{};
  EventRegistrationToken navigation_starting{};
  EventRegistrationToken frame_navigation_starting{};
  EventRegistrationToken launching_external_uri_scheme{};
};

class Policy {
 public:
  void Set(std::set<std::string> navigation_origins, std::set<std::string> message_origins);
  bool IsConfigured() const;
  bool AllowsNavigation(const std::wstring& uri) const;
  bool AllowsRequest(const std::wstring& uri) const;
  bool AllowsMessageFrom(const std::wstring& source_uri) const;

  void Count(const char* what, const std::wstring& uri);
  void SetSettingsJson(std::string json);
  std::string ReportJson() const;

 private:
  mutable std::mutex mutex_;
  bool configured_ = false;
  std::set<std::string> navigation_origins_;
  std::set<std::string> message_origins_;
  long blocked_requests_ = 0;
  long cancelled_navigations_ = 0;
  long cancelled_frame_navigations_ = 0;
  long cancelled_external_schemes_ = 0;
  long denied_windows_ = 0;
  long cancelled_downloads_ = 0;
  long dropped_messages_ = 0;
  long denied_permissions_ = 0;
  std::deque<std::string> recent_;   // "kind uri", newest last, at most 64
  std::string settings_json_;
};

// Applies the settings and registers the request, navigation and external-scheme handlers.
void Install(ICoreWebView2* webview, Policy* policy, Tokens* tokens);
void Uninstall(ICoreWebView2* webview, Tokens* tokens);

}  // namespace uri_security
