# Tool and repository evaluation (W1 / A0)

Licences were read from the packages' own PyPI metadata on 2026-10-10 (`pip download --no-deps`, METADATA
`License`/`License-Expression`/classifier); SearXNG and Mozilla Readability from their repositories' declared licences
(not re-downloaded here: marked "declared"). None of these was added as a dependency.

| Candidate | Licence | What it would give | Cost / risk | Decision |
|---|---|---|---|---|
| SearXNG | AGPL-3.0 (declared) | self-hosted meta-search, JSON API | a separate service to run and patch; AGPL applies to the service, not to URI calling it; result quality depends on upstream engines that rate-limit scrapers | **Optional provider** (`URI_SEARXNG_URL`), owner-hosted only; not bundled |
| Brave Search API | commercial API terms | independent index, clean JSON | paid key; per-query cost | **Optional provider** (`BRAVE_SEARCH_API_KEY`) |
| Tavily (already used) | commercial API terms | research-oriented results + snippets | existing key convention | **Default provider** (reuse) |
| trafilatura 2.3.1 | Apache-2.0 | best-in-class main-text and metadata extraction | lxml + several deps; larger attack surface | **Not adopted now**; stdlib extractor meets the fixtures. Candidate if real-page extraction quality proves insufficient on the PC |
| Mozilla Readability (JS) | Apache-2.0 (declared) | reader-mode extraction in the browser | runs in page JS | Not adopted; extension snapshot uses visible-text walk |
| readability-lxml 0.9 | Apache-2.0 | Python port | lxml dep | Not adopted |
| markitdown 0.1.8 | MIT | many formats → Markdown | many optional deps; PDF/Office already covered by Core's file extraction | Not adopted |
| feedparser 6.0.14 | BSD-2-Clause | tolerant RSS/Atom parsing | one dep; its sanitizer is HTML-focused | Not adopted; stdlib parser with DOCTYPE/ENTITY refusal covers RSS 2.0 / RSS 1.0 / Atom |
| Playwright 1.63 (py) / 1.56 (node, preinstalled) | Apache-2.0 | real-browser automation | browser binaries (hundreds of MB), new automation surface | **Test harness only** (runs the extension snapshot in real Chromium). Not a runtime dependency |
| browser-use 0.13.11 | MIT | LLM-driven browser agent | autonomous operation is out of scope by mandate; would hand a model a browser | **Rejected** |
| Chromium extension (MV3) `activeTab` + `scripting` (+ Side Panel later) | platform API | per-tab, user-click-gated page access; no host permissions | needs a native-messaging channel to URI (not built in A0) | **Adopted** for structured browser perception (snapshot script built and tested) |
| Windows UI Automation | platform API | window/control tree, IsPassword flag | Windows-only; needs a COM client (comtypes/pywinauto) on the PC | **Planned** (contract `uri.assist.uia.v1` defined; adapter NOT IMPLEMENTED) |
| atproto 0.0.72 | MIT | AT Protocol SDK | dependency for what three GET calls do | Not adopted; public AppView `getAuthorFeed` via SafeFetcher |
| Mastodon REST API | API docs | public timelines/statuses | instances may require auth → UNAVAILABLE | Adopted via SafeFetcher (read-only) |
| PowerToys | MIT | reference for unobtrusive productivity UX | — | Reference only (quiet suggestions, no modal interruptions) |
| Figma / Blender MCP | — | design exploration | not authorized/available in this session | Not used; an HTML prototype is provided instead |

Resource notes: everything adopted runs on the CPU in the worker process except on-demand vision, which reuses the
already-resident Runtime v1 projector (no new VRAM).
