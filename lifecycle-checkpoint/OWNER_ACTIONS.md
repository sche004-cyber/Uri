# Owner actions: everything waiting on you

One list of every item that needs you. Rule (owner, 2026-10-11, D23): every new item that needs the owner is added
here the same day, and removed only when it is done, with the date. Newest changes are in the log at the bottom.

## 1. Things to do

| # | What | Why | Blocks |
|---|---|---|---|
| A1 | Get a free key at urlhaus.abuse.ch and add `URLHAUS_AUTH_KEY=...` to URI's `.env`. | LINK-REP-1 checks addresses against this scam list. | LINK-REP-1 |
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
| Q1 | Approved website list for W2 document search. | Proposal list only. | Not blocking |
| Q2 | W2: refresh documents on a schedule? | No, manual only. | Not blocking |
| Q3 | W2: names and personal data found in public documents. | Searchable only, never saved to memory or learning. | Not blocking |
| Q4 | W2: keep permanent copies of PDFs? | No. | Not blocking |
| Q5 | Office thread: OFF-O1 to OFF-O5. | Not approved. | Office milestones |

## 4. Optional: ordinary text that is hidden by mistake

These are readability costs of the link check. Say if any matters to you and I'll narrow it.

| # | Example | Hidden because |
|---|---|---|
| O1 | Portuguese "café com leite" | "com" after a space counts as a domain. |
| O2 | Hebrew with vowel points ("שָׁלוֹם") | A point named "SHIN DOT" counts as a dot. |
| O3 | "Tokyo 東京 is big" (no brackets) | A short foreign word before a domain-like word (D17). |
| O4 | "the org chart" | "org" after a space counts as a domain. |
| O5 | "Profit, net" | An older comma rule. |

## Log
| Date | Change |
|---|---|
| 2026-10-11 | File created from the away-mode log, plans and decisions D1-D22. |
