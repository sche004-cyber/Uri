# Owner actions: everything waiting on you

One list of every item that needs you. Rule (owner, 2026-10-11, D23): every new item that needs the owner is added
here the same day, and removed only when it is done, with the date. Newest changes are in the log at the bottom.

## 1. Things to do

| # | What | Why | Blocks |
|---|---|---|---|
| A1 | Get a free key at urlhaus.abuse.ch and paste it in URI's new Settings > Security tab (after LINK-REP-1). | LINK-REP-1 checks addresses against this scam list. | Nothing: optional, turns on the live scam check |
| A2 | Make sure Tesseract OCR is installed on your PC. | W2 reads scanned PDFs with it. Not checkable from the cloud. | W2 scanned PDFs only |
| A3 | Remove the three leftover `url.insteadOf` test lines from `~/.gitconfig` (cloud container). | Left from earlier testing; I'm not allowed to change them. | Nothing (tidy-up) |
| A4 | Send the OFF-O6 approval text to the Office thread, if you haven't yet. | Lets the Office thread start the WebView2 work. | Office OFF-O6 |
| A5 | Let the cloud environment run Codex: in the environment settings (environment menu in the session title bar → Edit) add `npm install -g @openai/codex` to the Setup script, and add your OpenAI key as the environment variable `OPENAI_API_KEY` (Network secrets / API credentials if offered). Never paste the key in chat. Then start a new session or tell me. | You asked to use Codex as much as possible (D32). Codex is not installed here and I may not install it myself. | Codex reviewer/implementer; until then milestones keep using Claude |

## 2. Things to run on your Windows PC

| # | What | Why | Blocks |
|---|---|---|---|
| W1 | Confirm with the DEV-LIFECYCLE-2 thread that `tests/dev_workflow` and one real DEVTEST round passed on the PC. | Windows support for the dev skill stays "not verified" until then. | Trusting skill runs on the PC |
| W2 | Add a one-line note to the old `uri-development` skill: "for milestones, use uri-development-lifecycle". | It exists only on your PC. | Nothing (tidy-up) |
| W3 | SCHED-TOKEN-ACL fix: run it as a small milestone on the PC. | The scheduler's token file can be read by other local users. | Scheduler security |
| W4 | RW1: run its benchmark on the PC. | Needs Windows and WebView2. | RW1 |

## 3. Decisions (defaults apply until you decide)

| # | Question | Current default | Blocks |
|---|---|---|---|
| Q5 | Office thread: OFF-O1 to OFF-O5 (ask the Office thread to list them for you). | Not approved. | Office milestones |
| Q7 | SETTINGS-1 split: do 1a now (Settings > Security for search and scam-check keys, Windows-protected store, one-time `.env` import; no new frozen file) and plan 1b with frozen exceptions (Connections: Ollama, Tesseract, model paths, Google folder; one saved key-store password per install)? See "Known limitations" below. | SETTINGS-1 waits. | SETTINGS-1 (both parts) |

## 4. Optional: ordinary text that is hidden by mistake

All answered 2026-10-11: O1, O3, O4, O5 stay as they are; O2 (Hebrew points) will be fixed in IDN-1. Nothing waiting.


## 5. Known limitations (found 2026-10-12, waiting for your review)

| # | Limitation | Effect today | Fix proposed |
|---|---|---|---|
| L1 | The app's backend clears its environment at start, so settings in environment variables (Ollama address and model, Tesseract path, model paths, Google folder) never reach it; they are read only inside frozen code. | Those features use their built-in defaults on the working system. | SETTINGS-1b (frozen exceptions, Q7). |
| L2 | The backend picks a new random password for its encrypted key store on every start. | Model keys or connection passwords saved through it cannot be read after a restart. | SETTINGS-1b: one saved, Windows-protected password per install (Q7). |
| L3 | Web search keys reach the app only from a hand-placed `search_keys.json` or the source folder's `.env`; there is no screen to enter them. | Keys must be placed by hand. | SETTINGS-1a (Q7). |
| L4 | The old fixed default key-store password is still in the legacy launcher (`run_uri_server.py`, `server.py`). | Low: the app refuses the legacy server. | SETTINGS-1b or remove with the legacy path. |
| L5 | The chat's web search tool (`uri_core/tools/web_search.py`, frozen) reads `.env` from its working folder. | It likely finds no key on the working system. | SETTINGS-1b. |
| L6 | IDN-1b leftovers (LOW): a refused redirect target is counted under the redirecting site; percent escapes that decode to invisible characters get the "non-English letters" wording. | Count or wording slightly off; the site is still blocked. | Small optional follow-up IDN-1c. |

## Log
| Date | Change |
|---|---|
| 2026-10-11 | File created from the away-mode log, plans and decisions D1-D22. |
| 2026-10-11 | Answered: Q1 proposed site list; Q2 refresh only when you ask for the same data again; Q3 search only; Q4 no PDF copies (D24). O1 keep (confirmed after a clearer question), O2 allow Hebrew points (in IDN-1), O3/O4/O5 keep. Delegated to a PC thread (paste box given): A2, W1, W2, W3, W4. |
| 2026-10-11 | Q2 corrected by the owner: refresh whenever you visit the data again (ask for it or open it), not only when asking again. |
| 2026-10-11 | D25: the scam-list check is added security, never a blocker. A1 (URLhaus key) is now optional; LINK-REP-1 runs without it. |
| 2026-10-11 | D26: a Security tab in settings for the key (frozen exception: settings_shell.dart tab entry only). A1 now means pasting the key there. |
| 2026-10-11 | D27: Tavily key slot added to the planned Security tab. Nothing new for you to do: your current `.env` Tavily key keeps working. |
| 2026-10-11 | D28: all settings move into the app (SETTINGS-1); `.env` can be deleted after its one-time import. Nothing to do yet. |
| 2026-10-12 | Added Q6 (frozen-file exception for the IDN-1 message in the chat fetch tool). |
| 2026-10-12 | Q6 answered: yes. The chat fetch tool and the research note will say the site was not opened in URI for security reasons and can be opened in an external browser (IDN-1b, frozen exception D33). |
| 2026-10-12 | Added Q7 (SETTINGS-1 split) and section 5, Known limitations L1-L6 (owner: review on return). |
