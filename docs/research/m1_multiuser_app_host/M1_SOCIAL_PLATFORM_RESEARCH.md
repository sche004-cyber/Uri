# M1 social and video platform research

**Status:** research only. URI has **no** social-platform integration today (`M1_REPOSITORY_CAPABILITY_INVENTORY.md`
§3). The existing `skill.yt_dlp` is deliberately pinned to Wikimedia Commons URLs.

**Grading:**
- **EXT-P:** fetched live.
- **EXT-S:** search-result summaries from 2026, because YouTube, Google, Reddit and Meta pages were unreachable from this
  sandbox (DNS).
- Every figure below must be re-checked against the provider's own page before implementation.

**Rule applied throughout:**
- Use official APIs first, then public feeds, then user-directed browsing of the user's *own* account.
- **Never** evade CAPTCHAs, rate limits, paywalls, login walls or anti-automation terms.
- "Publicly visible" does not mean "permitted to automate".

## 1. Platform matrix

### YouTube

| Aspect | Findings |
|---|---|
| Official API | YouTube Data API v3. Default quota 10,000 units/day per project; `search.list` costs 100 units. More quota needs an audit form, with no paid tier. |
| Captions and transcripts | `captions.download` reportedly needs OAuth from the video's owner or editor. Third-party transcripts are **not** available through the official API. |
| Auth | An API key for public metadata; OAuth for the user's own channel. |
| Cost and limits | Free within quota. About 100 searches/day per project, **shared by all URI users**. |
| Terms | Terms bar automated access "except public search engines per robots.txt or with prior written permission". Downloading is limited to YouTube-provided features. |
| Freshness and reliability | Near real-time via the API |
| M1 recommendation | **P3:** search and metadata through the Data API, with a per-user quota budget. Transcripts **only** for (a) the user's own videos via OAuth, (b) a transcript the user supplies, or (c) media the user uploads. Otherwise the result is labelled `metadata_only`. Do **not** widen `yt_dlp` to YouTube. |

Sources: EXT-S, with the terms clause EXT-S quoting youtube.com/terms.

### Reddit

| Aspect | Findings |
|---|---|
| Official API | Data API. **Pre-approval is required** under the Responsible Builder Policy (Nov 2025, updated Jun 2026). |
| Auth | OAuth client, approval required |
| Cost and limits | Reported free non-commercial tier of 100 QPM per client; commercial use needs a written agreement. Approval rates are reported as low. |
| Terms | Approval-gated; data-use restrictions apply |
| Freshness and reliability | Good once approved |
| M1 recommendation | **P3, conditional:** apply for approval as a personal, non-commercial assistant. Until approved, there is no Reddit retrieval beyond a user opening a link themselves. |

Sources: EXT-S.

### X / Twitter

| Aspect | Findings |
|---|---|
| Official API | X API, pay-per-use since early 2026. Basic and Pro are legacy. |
| Auth | OAuth 2.0 app plus a payment card |
| Cost and limits | About $0.005 per post read and $0.010 per user read; a cap of about 2-3M reads/month |
| Terms | Developer agreement; automated access outside the API is prohibited |
| Freshness and reliability | Real-time |
| M1 recommendation | **P6:** owner-paid credits, metered per user through the existing usage ceilings and single-use spend approval (the CLOUD policy pattern) |

Sources: EXT-S.

### Facebook

| Aspect | Findings |
|---|---|
| Official API | Graph API. **Page Public Content Access** needs App Review plus business verification, and possibly contracts. CrowdTangle is closed. Meta Content Library is for vetted researchers only. |
| Auth | Meta app plus a user or page token |
| Cost and limits | Free, but approval-gated |
| Terms | Automated collection outside the API is prohibited |
| Freshness and reliability | Good where approved |
| M1 recommendation | **P6:** only pages the user administers, via their own token. Public-page research is not feasible for a household app; label such requests `unsupported`. |

Sources: EXT-P (Meta docs page summary, updated 2026-07-01) and EXT-S.

### Instagram

| Aspect | Findings |
|---|---|
| Official API | Instagram Graph API for professional accounts only. Business Discovery covers other *professional* accounts. Hashtag search needs Public Content Access review, and is limited to 30 hashtags per 7 days and 24 h of recent media. |
| Auth | A Meta app with review |
| Cost and limits | Free, approval-gated |
| Terms | Scraping is prohibited |
| Freshness and reliability | Limited |
| M1 recommendation | **P6:** the user's own professional account only |

Sources: EXT-S.

### LinkedIn

| Aspect | Findings |
|---|---|
| Official API | Partner Program for almost everything. Self-serve covers sign-in and posting. |
| Auth | OAuth plus partner approval |
| Cost and limits | Low per-token limits (reported) |
| Terms | The User Agreement prohibits scraping; LinkedIn has enforced this (for example, Proxycurl shut down after litigation in 2025, per a secondary source) |
| Freshness and reliability | — |
| M1 recommendation | **P6:** posting to the user's own account through the self-serve share API, after approval. No research or collection. |

Sources: EXT-S.

### Bluesky (AT Protocol)

| Aspect | Findings |
|---|---|
| Official API | Open protocol. The public AppView serves reads. Whether search works without an app password is reported inconsistently. |
| Auth | None for reads; an app password for some endpoints |
| Cost and limits | Reported about 3,000 requests per 5 minutes per IP |
| Terms | Open protocol; follow the developer guidelines |
| Freshness and reliability | Real-time |
| M1 recommendation | **P6, early candidate:** a low-risk official route |

Sources: EXT-S.

### Mastodon / fediverse

| Aspect | Findings |
|---|---|
| Official API | A REST API on each instance; public timelines and search depend on the instance |
| Auth | Per-instance app or token |
| Cost and limits | Per-instance limits |
| Terms | Each instance's rules |
| Freshness and reliability | Varies |
| M1 recommendation | **P6** |

Sources: not verified in this session.

### Other public sources

| Source | Notes | Phase |
|---|---|---|
| RSS/Atom feeds (government notifications, news, YouTube channel feeds) | Published for automated consumption | **P3, preferred route for monitoring** |
| Wikipedia/Wikimedia APIs | Documented public APIs | P3 |
| Hacker News API | Public | P3 |
| arXiv API | Public | P3 |

YouTube channel feeds are reported to exist at `/feeds/videos.xml?channel_id=` (EXT-S, unverified).

## 2. Video intelligence (YouTube and others)

| Step | Method | What URI can honestly claim |
|---|---|---|
| Search | YouTube Data API `search.list` (100 units) or a channel RSS feed | Titles, channels, dates, descriptions: `metadata_only` |
| Transcript | One of three permitted routes: (a) the user's own video captions via OAuth; (b) a transcript the user supplies; (c) audio from a file the **user uploads** with rights to it, transcribed locally with faster-whisper (already in the voice stack). Run (c) on CPU, or on GPU only under `gpu_lease` with the Brain idle. | `transcript` scope. Content can be summarised and timestamped. |
| Timestamps | From transcript segment times (faster-whisper segments or caption cues) | Cited as `url&t=<seconds>` links |
| Summarise and compare | Brain through the fair queue, over SourceRecords | Each video is labelled `transcript` or `metadata_only`. A comparison that mixes the two says so explicitly. |
| Not done | Downloading YouTube media with yt-dlp; scraping watch pages for captions; bypassing age or region gates | — |

**Resource note:** transcribing one hour of audio with faster-whisper on the 5900X CPU has not been measured here.
Running ASR on the GPU competes with the 15.6 GB Brain allocation (GPU-1/GPU-3). Measure on the PC first.

## 3. Browser automation on social platforms

- Platform terms (YouTube, X, Meta, LinkedIn) restrict automated access even for logged-in users.
- Browser automation on these sites is therefore limited to **interactive, user-initiated, low-volume** actions on the
  user's own account: drafting a post the user then approves, or downloading the user's own data export.
- It is never used for bulk collection.
- See `M1_BROWSER_AUTOMATION_AND_SECURITY.md` §5 for the per-site policy table that enforces this.

## 4. Operating cost sketch (owner-paid keys, M1 scale)

These numbers are rough and use EXT-S prices.

| Service | Usage assumption | Monthly cost |
|---|---|---|
| Tavily | 3 users × 20 searches/day ≈ 1,800/month, about 1,000 free credits | About $6-8 |
| YouTube Data API | 100 searches/day | Free, but a hard cap shared by everyone |
| X API (if enabled) | 1,000 post reads/day | About $150/month. **Gate behind an explicit owner decision.** |

## 5. Uncertainty

- Every price, quota and policy here is EXT-S unless marked otherwise.
- Reddit approval is uncertain.
- The YouTube captions-ownership rule must be confirmed against `developers.google.com/youtube/v3/docs/captions`.
- Facebook, Instagram and LinkedIn public research is likely **not achievable** through legitimate means at household
  scale. That conclusion should be read as "not supported", not as a gap to engineer around.
