#!/usr/bin/env bash
# Independent review launch: fresh codex exec session, stdin closed, 90-minute deadline, diagnostics kept.
cd "C:/Users/cheta/.codex/worktrees/uri-phase2a/evidence/phase2close_review" || exit 2
mkdir -p round5
PROMPT='Read and follow exactly the mandate in C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\MANDATE_round5.md (the subject is in ROUND5_SUBJECT.txt beside it). You are the independent reviewer. Write your report where the mandate says.'
timeout 5400 codex exec --skip-git-repo-check --json -m gpt-6-sol -c model_reasoning_effort=medium -s workspace-write \
  -C "C:/Users/cheta/.codex/worktrees/uri-phase2a" -o round5/codex_round5_last_message.md "$PROMPT" \
  < /dev/null > round5/codex_round5_events.jsonl 2> round5/codex_round5_stderr.txt
echo "EXIT=$?" >> round5/codex_round5_stderr.txt
