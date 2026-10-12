#!/usr/bin/env bash
cd "C:/Users/cheta/.codex/worktrees/uri-phase2a/evidence/phase2oq_review" || exit 2
mkdir -p round2
PROMPT='Read and follow exactly the mandate in C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\MANDATE_round2.md (the subject is in ROUND2_SUBJECT.txt beside it). You are the independent reviewer. Write your report where the mandate says.'
timeout 5400 codex exec --skip-git-repo-check --json -m gpt-6-sol -c model_reasoning_effort=medium -s workspace-write \
  -C "C:/Users/cheta/.codex/worktrees/uri-phase2a" -o round2/codex_round2_last_message.md "$PROMPT" \
  < /dev/null > round2/codex_round2_events.jsonl 2> round2/codex_round2_stderr.txt
echo "EXIT=$?" >> round2/codex_round2_stderr.txt
