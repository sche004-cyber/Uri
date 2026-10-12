# ONBOARD-1 — first-use ability explainers (plan draft)

**Owner request (2026-10-11):** "a small brief pop up explainer for the first time a new URI ability is used, like
this URI Assist."

## What the user sees

The first time a user starts an ability (Assist, web research, document search, Office sheets panel, dictation,
scheduler), URI shows one short card before the ability acts:

- **What it does:** one sentence.
- **What it can see or send:** one sentence, matching the real permissions (e.g. Assist: "only page text the screen
  shows, pixel-checked; field values hidden by default").
- **What it never does:** one sentence (e.g. "never submits forms or learns from sensitive data").
- **How to stop it:** one sentence.
- Buttons: **Got it**, and **Show me later**, which shows the card again next time.

The card is shown once per ability **per user**, not per install. A user can reopen any explainer from Help.

## Rules

- **Not a permission:** the explainer is never a permission grant. For abilities that need a grant (Assist Observe,
  D5), it appears together with the existing grant prompt and does not replace it; declining the grant still works
  as today.
- **Accurate text:** every sentence is tied to a code fact and a test, so the text cannot drift from what the
  ability actually does (D5/D7/D8/D10/D13 wording).
- **No new runtime dependencies, permissions or data collection.** "Seen" status is a per-user preference stored
  next to `completedOnboarding`; nothing else is recorded.
- **Frozen files untouched:** `settings_shell.dart` is frozen, so the reopen entry lives in a non-frozen Help screen.

## Acceptance criteria

| # | Criterion |
|---|---|
| OB-AC1 | A static registry lists each ability with id, title and the four sentences; one test per ability checks each sentence against the code fact it states. |
| OB-AC2 | Shown on first use per user, before the ability acts; not shown again after "Got it"; shown again after "Show me later". Two users on one install each see it once. |
| OB-AC3 | For Assist, the card sits with the Observe grant prompt and never grants anything; tests prove no grant without the existing grant action. |
| OB-AC4 | Rendered as an A2UI surface (Card/Text/Button) using only existing catalog components; "Got it" and "Show me later" are allow-listed actions with no side effect beyond the per-user flag. |
| OB-AC5 | Help screen lists all explainers; reopening one changes nothing. |
| OB-AC6 | No frozen file, new dependency or new permission; independent review; D1 integration. |
| OB-AC7 | Every later ability milestone (W2a, W2b, RW1, Office) adds its own registry entry; W2 plan gets this as an acceptance criterion. |

## Queue position

After GRAPHIFY-LEAK-1 and before W2a, so W2 registers its explainer from the start. Windows UI rendering of the
Flutter card: NOT VERIFIED from the cloud (unit and widget tests only).
