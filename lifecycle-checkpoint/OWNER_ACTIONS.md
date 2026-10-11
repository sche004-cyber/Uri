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

## 4. Optional: ordinary text that is hidden by mistake

All answered 2026-10-11: O1, O3, O4, O5 stay as they are; O2 (Hebrew points) will be fixed in IDN-1. Nothing waiting.


## Log
| Date | Change |
|---|---|
| 2026-10-11 | File created from the away-mode log, plans and decisions D1-D22. |
| 2026-10-11 | Answered: Q1 proposed site list; Q2 refresh only when you ask for the same data again; Q3 search only; Q4 no PDF copies (D24). O1 keep (confirmed after a clearer question), O2 allow Hebrew points (in IDN-1), O3/O4/O5 keep. Delegated to a PC thread (paste box given): A2, W1, W2, W3, W4. |
| 2026-10-11 | Q2 corrected by the owner: refresh whenever you visit the data again (ask for it or open it), not only when asking again. |
| 2026-10-11 | D25: the scam-list check is added security, never a blocker. A1 (URLhaus key) is now optional; LINK-REP-1 runs without it. |
| 2026-10-11 | D26: a Security tab in settings for the key (frozen exception: settings_shell.dart tab entry only). A1 now means pasting the key there. |
