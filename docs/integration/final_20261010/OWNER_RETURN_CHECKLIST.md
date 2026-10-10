# Owner-return checklist (deferred: owner unavailable from 2026-10-09)

Each item needs the owner's presence, login or decision. None of these was simulated or marked passed. Classification
follows the owner's deferred-qualification policy (2026-10-10).

| # | What the owner does | Why it waits for the owner | Class | Until done |
|---|---|---|---|---|
| 1 | Own-voice conversation: push-to-talk, ask 3 questions, hear the spoken replies (Living Companion, staging install) | Human-voice accuracy cannot be qualified with synthetic audio | NON-BLOCKING LIMITATION | voice works only as recorded by automated tests; no voice identity, so voice never authorises anything |
| 2 | Own-voice dictation: Drafting mode, dictate a short letter with a correction ("no, make that Friday"), check the corrected draft and that no words were lost | Same | NON-BLOCKING LIMITATION | approval gates stay explicit clicks |
| 3 | Optional: voice packs / tone settings | Enhancement | NON-BLOCKING LIMITATION | not built |
| 4 | Log in the Claude CLI on the client profile (`claude` → login) | Authentication is the owner's | ACTIVATION BLOCKER (real-Claude scheduled execution only) | real-Claude execution stays disabled |
| 5 | Approve or correct festival dates, the 09:00 IST default, and the first festival job | Owner preference and authority | ACTIVATION BLOCKER (festival jobs only) | no automatic job activates |
| 6 | Register the `URIScheduler` logon task (after 4 and a live PASS) | Windows startup change | ACTIVATION BLOCKER (scheduler autostart only) | not registered |
| 7 | Decide production cutover (`CUTOVER_PLAN.md`) | Changes the live installation, port 8000 and shortcuts | ACTIVATION BLOCKER (production only) | legacy `\URIServer` stays live |
| 8 | Look at the host-reset incident INC-1 (UPS / power / hardware) | Physical | NON-BLOCKING for development; input to item 7 | recorded |
| 9 | Accept or reject carried limitations (TI L-1..L-10, LV-1..3, WS GPU-2/3/4, R-SHUT, …) and the VRAM research verdict | Owner judgement | NON-BLOCKING LIMITATION | as documented |
| 10 | Pick the orb direction (UI living companions, solar R&D) | Preference | NON-BLOCKING LIMITATION | current selected appearance kept |
