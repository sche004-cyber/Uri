# Harness-first URI: manual test (EXPERIMENTAL build)

This runs the experimental branch `claude/harness-first-edge` in its own folder with its own data. Your normal URI folder, data and branch are not touched.

## One-time setup (one command)

In PowerShell:

```
git -C C:\Users\cheta\Development\uri-agent worktree add C:\Users\cheta\Development\uri-harness-first claude/harness-first-edge
```

## Launch (one click)

Double-click `C:\Users\cheta\Development\uri-harness-first\Launch URI Harness-First.bat`.

It starts Ollama if needed, warms the Edge chat model (`qwen3:0.6b`), pauses the normal URI backend if it is running, starts this build's backend on the usual port with `URI_HARNESS_FIRST=1`, and opens the URI desktop app. This build has its own accounts, so sign up a test account the first time.

To go back: double-click `Restore normal URI.bat` in the same folder.

## What to try

| Prompt | Expected handler | Expected time |
|---|---|---|
| hello / hey there / good morning | Edge (local small model), natural reply | under 1 s |
| thanks / Thank you so much! / ok cool | Edge | under 1 s |
| bye / good night / see you tomorrow | Edge | under 1 s |
| what can you do? / what's your name? | Edge | under 1 s |
| How much memory is this computer using right now? | Main Brain (normal path) | as today |
| hi, how much RAM is this PC using? | Main Brain (a greeting wrapped around work is not small talk) | as today |
| Search the web for NAAC criterion 3 guidelines. | Main Brain | as today |

## How to tell who answered

- The model caption under the reply shows `ollama (edge) · qwen3:0.6b` for Edge turns and the Main Brain model (e.g. `qwen3.5:9b`) otherwise. `uri (deterministic)` means the Edge model failed validation or timed out and URI used a fixed line.
- Settings > Edge Lab / Developer trace shows the decision `HARNESS_EDGE_CHAT` for Edge turns and `MAIN_BRAIN` for the normal path.
- The API response field `harness_route` carries the class (`HARNESS_PLUS_EDGE` or `HARNESS_COMPLETE`), the Edge latency and the reason.

## Switching the Edge chat model

Edit the `-EdgeChatModel` default in `scripts\launch_uri_harness_first.ps1` (any installed Ollama model; measured candidates: qwen3:0.6b, gemma3:270m, granite4:350m-h, qwen3.5:0.8b). The slot is a replaceable specialist; routing still goes through S6.

## What this build does not do yet

Only purely social turns use the Edge path. File references, tool choice, extraction and labels still go to the Main Brain, because no small model measured well enough on them (see `HARNESS_FIRST_EDGE_DEV_RESULTS.md`).
