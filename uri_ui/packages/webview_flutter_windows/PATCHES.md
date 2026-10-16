# URI changes to the vendored `webview_flutter_windows` 1.2.0

## Approval and scope

- **Owner approval:** OFF-O6 option (a), 2026-10-11. One new vendored dependency, used by the URI Office panel only.
- **Not qualified for RW1:** this host is qualified for the Office page. Reusing it for RW1 (general web content) is a separate qualification decision. Do not treat it as a safe general-purpose browser.

## Source

| Item | Value |
|---|---|
| Package | `webview_flutter_windows` 1.2.0, published 2026-09-01 |
| Archive | `https://pub.dev/api/archives/webview_flutter_windows-1.2.0.tar.gz` |
| Archive SHA-256 | `5e1222be978b408b7f4297eec7ff6048000de92f29dbb6cbd04155c11d53677c` (equal to the `archive_sha256` pub.dev publishes) |
| Upstream repository | `https://github.com/omar-hanafy/webview_flutter_windows`, a fork of `jnschulze/flutter-webview-windows` |
| Licence | BSD-3-Clause, `LICENSE` kept unchanged |
| Unmodified baseline | commit `9765e780` on `phase/uri-office` (identical to the pub.dev archive). The diff from that commit is exactly the patches below plus this file. Line endings are kept as upstream has them (upstream mixes LF and CRLF files); patched files are not re-encoded. |

## Build-time downloads

These are made by the package's own CMake into the Flutter build folder. Nothing is installed system-wide and nothing needs elevation.

| What | Version | Pin |
|---|---|---|
| `nuget.exe` (upstream) | 7.6.0 | SHA-256 `751ee5e79481626a428c1241dc7f94bca2739b32588e669715bc5fb54d8fb8a2` (upstream pin) |
| `Microsoft.Web.WebView2` (SDK headers and loader) | 1.0.3967.48 | `.nupkg` SHA-256 `c66357ac7f324ec9bcafe5241706a023b4122d8c22300c31de4b0eb220db689e`; equals nuget.org catalog SHA-512 `50aQQCAY6Y78fcULLIsli750tq+VdLrJsdq7leYk5Zbbbi510kCjLBAG9EoZyEBAa7tlKpqnJ+5F7yuJXn3pfg==` (P3) |
| `Microsoft.Windows.ImplementationLibrary` (WIL headers) | 1.0.260126.7 | `.nupkg` SHA-256 `7d67bc71dd0edc342db44ea0334ac9b6a1776514f81694b0b5b3c7ac9d608e42`; equals catalog SHA-512 `kFZSUpWI7YXoV8aTJENnHH2KKssHI8adLqQtv/XfehlOodXY7x75fRJQS3iSaG64dN5jMVpP2yR9Slnmq9fHoA==` (P3) |

The WebView2 browser itself is the Evergreen runtime installed with Windows. No Chromium is bundled or downloaded.

## P1: fail-closed host lockdown

Files: new `windows/uri_security.h` and `windows/uri_security.cc`; edits in `windows/webview.h`, `windows/webview.cc`, `windows/webview_bridge.cc`, `windows/CMakeLists.txt`, `lib/src/webview.dart`.

| Behaviour | Upstream | URI |
|---|---|---|
| Network requests | all allowed | `AddWebResourceRequestedFilter("*", COREWEBVIEW2_WEB_RESOURCE_CONTEXT_ALL)`. Every request whose origin is not in the navigation allow-list gets a host-made 403. Before `setNetworkPolicy` the allow-list is empty, so everything is refused. |
| Top-level navigation | all allowed | `NavigationStarting` cancels anything but an allowed origin or `about:blank`. This fires for each redirect hop, so redirects out are cancelled, and it covers `file:`, `data:`, `blob:` and custom schemes. |
| Frame navigation | all allowed | `FrameNavigationStarting`, same rule |
| External scheme handlers | OS default | `LaunchingExternalUriScheme` is always cancelled |
| New windows | Dart policy (`allow`, `deny` or `sameWindow`) | always refused; the Dart policy is ignored |
| Downloads | ran to the default Downloads folder, progress reported to Dart | always cancelled before anything is written |
| Permissions (camera, microphone, location, notifications, clipboard, ...) | forwarded to a Dart callback | always denied without a prompt, never forwarded |
| Web messages | all delivered | delivered only when `get_Source` has an origin in the message allow-list; otherwise dropped and counted |
| Developer tools | on | `AreDevToolsEnabled = FALSE` and `openDevTools()` refused, in release builds (`NDEBUG`) |
| Browser accelerator keys (F12, Ctrl+Shift+I, Ctrl+P, ...) | on | off in release builds |
| Host objects | allowed (none added) | `AreHostObjectsAllowed = FALSE` |
| Script dialogs (alert, confirm, prompt) | on | off |
| Web messages from the page | `IsWebMessageEnabled` left at the runtime default | set to `TRUE` explicitly in `uri_security::Install`, so the page-to-host channel the Office panel depends on does not rest on a default; delivery is still limited by the message allow-list above |
| WebRTC and WebTransport in pages | available | `uri_security::Install` adds a document-created script that redefines `RTCPeerConnection`, `webkitRTCPeerConnection`, `RTCDataChannel`, `RTCIceTransport`, `RTCSctpTransport`, `RTCDtlsTransport` and `WebTransport` as non-configurable `undefined` in every document and child frame before any page script runs. Reason: WebRTC sends UDP that `WebResourceRequested` and the proxy (P2) do not see (real-runtime probe, 2026-10-11). |
| Password saving and general autofill | on | off (`ICoreWebView2Settings4`), per D5 |
| Swipe navigation | on | off |
| Upstream permission helpers | used | `CW2PermissionKindToPermissionKind` and `WebViewPermissionStateToCW2PermissionState` in `webview.cc` are no longer called (permissions are denied, not forwarded) and are marked `[[maybe_unused]]` so the build stays warning-clean; they are kept to keep the diff small |
| New Dart API | — | `setNetworkPolicy({navigationOrigins, messageOrigins})`, which refuses non-canonical origins; `getSecurityReport()` returns counters, the settings read back from the runtime and the last 64 blocked URIs. There is no API to turn the lockdown off. |

**Internal resources that bypass the request filter, and why they are allowed:**

- `data:` and `blob:` URLs are resolved inside the renderer and never become network requests. The Office page uses them for:
  - inline images and fonts in Univer's CSS (`img-src`/`font-src data:`);
  - blob URLs Univer creates for its own drawing and clipboard data (`img-src blob:`).
- They cannot reach another origin. Top-level navigation to them is cancelled (they have no allowed origin).
- The page's own CSP refuses `fetch` of `data:` (`connect-src 'self'`).
- The Office page is served from the virtual host `https://office.uri.local`, which `SetVirtualHostNameToFolderMapping` maps to the verified page folder (cross-origin access kind `deny`). Its requests are the only allowed ones.

## P2: environment

File: `windows/webview_host.cc`.

- Environment options are always created.
- `ExclusiveUserDataFolderAccess = TRUE`, so no other process (Edge included) can share the user-data folder.
- A browser executable path is never honoured (`browser_exe_path` is forced to `nullopt`), so only the installed Evergreen runtime runs.
- **Network kill switch.** These browser arguments are always set, before any Dart-supplied arguments (which are appended after them, not instead of them):
  - `--proxy-server=http://0.0.0.0:1` and `--proxy-bypass-list=<-loopback>`: every connection, loopback included, goes to an unreachable proxy. Reason: `WebResourceRequested` (P1) does not see WebSocket handshakes (real-runtime probe, 2026-10-11). The virtual-host page is served in-process and is unaffected.
  - `--force-webrtc-ip-handling-policy=disable_non_proxied_udp`: WebRTC may not use direct UDP. Together with the WebRTC/WebTransport constructor removal in P1 this closes the UDP path the request filter and the proxy cannot see.

Not in this package: the URI host (`uri_ui/lib/living/webview_host/webview2_office_surface.dart`, `prepareUserDataFolder`) passes its own user-data folder, `%LOCALAPPDATA%\URI\office\webview2`, and restricts it to the current user (one inheritable full-control entry, inheritance removed) before the environment starts; if that fails, the host refuses to start.

## P3: pinned NuGet packages

File: `windows/cmake/nuget.cmake`.

- `ensure_nuget_package` now refuses to configure unless the package's `.nupkg` SHA-256 equals the pin above.
- The check runs on every configure, not only after a download.
- A package without a pin also fails.

## Changes to this file list

Any further change to this package must be added here, with its reason, before it is committed.
