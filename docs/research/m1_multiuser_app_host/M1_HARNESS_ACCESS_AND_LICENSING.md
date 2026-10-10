# M1 harness access and licensing

**Not legal advice.** The owner must decide every interpretation marked D-4.

**Source grading:**
- **EXT-P (primary):** fetched live from the provider on 2026-10-10.
- **EXT-S (secondary):** search-result summaries, because the provider page could not be reached from this sandbox.
  `developers.openai.com`, `openai.com`, `support.google.com`, `developers.google.com` and `youtube.com` all failed DNS
  here.

## 1. What the repository already does

These points come from the capability inventory:

| Harness behaviour | Where |
|---|---|
| Only the unmodified `claude` and `codex` CLIs are invoked. Bypass flags are refused on every argv. | `uri_core/client_runtime/harness.py:33,52` |
| `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are never forwarded to harnesses. | `harness.py:37` |
| Users sign in with each CLI's own native login. URI only *probes* login status and never reads credential files. | `uri_harness_adapters/__init__.py:21-24`; `uri_supervisor_bridge/qualification.py:454` |
| Each client gets its own CLI home and a pinned `CODEX_HOME`. A shared owner login is a stop condition. | `qualification.py:377-390` |
| `CLAUDE_CODE_OAUTH_TOKEN` is on the environment allow-list for Claude Code. | `uri_harness_adapters/__init__.py:20` |
| The project decided that subscription login is not used as URI's own Brain transport. | `docs/plans/M31_MODEL_BRAIN_UX_PLAN.md:84-110` |

**Gaps:**
- Harnesses run as the same Windows user. That is "logical isolation", not protection against same-user code
  (`SERVER_CLIENT_INTERFACE_PLAN.md:68-70`).
- Remote users cannot complete a native login today.
- The scheduler runs Claude unattended (`SCHEDULER_ARCHITECTURE.md:75`).

## 2. Provider terms: technically possible vs permitted

| Pattern | Possible? | Permitted? | Source |
|---|---|---|---|
| One owner Claude Pro/Max login used by all three users | Yes | **No.** "You may not share your Account login information… You also may not make your Account available to anyone else." | EXT-P anthropic.com/legal/consumer-terms |
| URI collects, stores or injects users' Claude.ai tokens | Yes | **No** for third-party developers: "may not collect, store, or intermediate Claude.ai credentials or session tokens — sign-in to a Claude account must complete through Anthropic's own flow" | EXT-P code.claude.com/docs/en/legal-and-compliance |
| Each user signs in to the **unmodified** Claude Code with **their own** subscription, on a host that runs it | Yes | **Allowed by the wording.** "Nor does it prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription, including where a platform hosts Claude Code." Whether a household server is a "product or service" that needs the Commercial Terms is **D-4a**. | EXT-P, same page |
| The owner provisions an Anthropic **API key** for URI's authorized users, billed to the owner | Yes | **Allowed** when usage is billed to the key owner and not resold: "configuring an API key … for use by the customer's own authorized users … provided the resulting usage is billed to the key owner" | EXT-P, same page |
| Claude Team or Enterprise: one seat per person | Yes | Allowed. Each member signs in themselves; commercial terms apply. | EXT-P (same page lists Team/Enterprise OAuth) |
| Unattended or scheduled runs on a consumer subscription | Yes | **Risky.** Consumer terms bar automated access "except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it". Plan limits "assume ordinary, individual usage". | EXT-P (both pages) |
| One ChatGPT/Codex login shared by three users | Yes | **No.** OpenAI's help centre says an account is for the individual who created it. | EXT-S |
| Each user runs `codex login` in their own `CODEX_HOME` | Yes (already pinned) | Yes, as individual use. Treat `auth.json` like a password; the keyring store is available (`cli_auth_credentials_store`). | EXT-S |
| ChatGPT Business or Enterprise seats, or an OpenAI API key billed to the owner | Yes | Normal business use under OpenAI's business terms. A seat is used by one end user. | EXT-S |
| Gemini CLI with a personal Google login | — (no adapter) | Reported as retired for personal accounts in mid-2026; OAuth use from third-party tools is a violation. **Unverified**; nothing in M1 depends on it. | EXT-S |

## 3. Compliant access modes URI supports

| Mode | Who pays | How URI routes it | When to use it |
|---|---|---|---|
| **M-1. Individual subscription** (default for interactive harness work) | Each user | The user's own CLI home and Windows account, native login | Interactive coding and agent tasks the user starts and watches |
| **M-2. Organization seats** (Claude Team, ChatGPT Business) | The owner's organization | Same as M-1, one seat per user | If D-4a says a hosted harness for others needs commercial terms |
| **M-3. API key owned by the owner** | The owner | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` held by the server and **not** passed through the CLI allow-list. Used by URI-built agents or by CLIs started explicitly in API mode, under per-user usage ceilings (M22.7) and the CLOUD single-use approval policy. | Unattended and scheduled work; users without subscriptions |
| **M-4. Local Brain** | Nobody (power) | Runtime v1 through the fair queue | Default for chat, web summarisation, scheduled briefings |

## 4. Rules for M1

1. **No shared logins.** Every harness invocation is bound to the requesting user's own CLI home. The routing table is
   `user_id → (windows_account, cli_home, mode)`. A missing entry is refused, never filled in from the owner's entry.
2. **Native sign-in only.**
   - A remote user signs in through the CLI's own flow, in a terminal session under *their* Windows account on the
     server (`codex login --device-auth`; Claude's URL/code flow).
   - URI does not relay or display codes, which avoids "intermediating" risk.
   - **Uncertain:** whether showing the CLI's own URL inside URI's UI would count as intermediation. It is avoided
     until D-4b.
3. **Drop `CLAUDE_CODE_OAUTH_TOKEN` from server-side forwarding** unless the owner decides otherwise (D-4b). It lets a
   token be injected without Anthropic's sign-in flow on that host. This is a frozen-file change, made in the harness
   slice.
4. **Unattended work never uses M-1.** The scheduler's Claude template moves to M-3 or M-4 for jobs that run without the
   user present, or runs only when the user confirms each occurrence. This changes the scheduler's authority table
   (owner decision).
5. **Display honesty.** Each run records `{user, harness, mode, account kind}` in the audit log. The owner's usage is
   never attributed to another user.
6. **Binary integrity.** CLIs are installed from the vendor, unmodified, with version recorded. The existing
   qualification records bind CLI version and hashes (`qualification.py`).

## 5. Uncertainty

- **D-4a:** whether hosting Claude Code for household members needs the Commercial Terms.
- Codex, ChatGPT and Gemini terms are EXT-S only.
- Re-check every term at implementation time. Terms change, and two of the sources were updated in 2026.
