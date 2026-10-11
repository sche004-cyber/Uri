# Lifecycle checkpoint — restore after a container reset

Written 2026-10-11 before the owner's 10+ day absence. The milestone branches were local-only in the cloud container;
this directory keeps them durable on the session branch `ccr-cab5ed06-9hwyc4` (the only branch this session may push,
besides D1 integration into canonical). Updated by each unattended check-in.

## Contents

- `milestones.bundle` — git bundle of every local-only branch (prerequisite: `origin/integration/git-sync-20261008`).
  `REFS.txt` lists each branch tip at checkpoint time.
- `lifecycle-runs/` — lifecycle configs, hash-chained state (`events.jsonl`, `state.json`), receipts, reports, logs,
  `SSRF-1_PLAN_DRAFT.md`, `W1-A0-closure/C3_CORRECTION.md`.
- `venv-requirements.txt` — the driver/test Python environment (`python3 -m venv /tmp/claude-0/venv`).
- `AWAY_MODE.md` — what runs unattended, and its limits.

## Restore (fresh container)

Restore tested 2026-10-11 from a fresh clone of the pushed branch: bundle verified, milestone branches recreated at
the tips in `REFS.txt`.

```
cd /home/user/Uri && git fetch origin integration/git-sync-20261008
git bundle verify lifecycle-checkpoint/milestones.bundle
git fetch lifecycle-checkpoint/milestones.bundle 'refs/heads/*:refs/heads/*'     # recreates the milestone branches
git branch milestone/dev-lifecycle-20261011 1f4aeddf50d4eb2d024af7132b443b5dc57591df  # already in canonical, so not in the bundle
mkdir -p /home/user/uri-wt && cp -r lifecycle-checkpoint/lifecycle-runs /home/user/uri-wt/lifecycle-runs
for b in a0:milestone/a0-assist-foundation-20261010 lifecycle:milestone/dev-lifecycle-20261011 \
         w1:milestone/w1-web-intelligence-20261010 w2:milestone/w2-site-document-search \
         rw1:milestone/rw1-native-rendered-web lc-report:feature/lifecycle-visual-report \
         rea:research/rea-discovery-20261010; do git worktree add /home/user/uri-wt/${b%%:*} ${b#*:}; done
git worktree add --detach /tmp/claude-0/lc-driver-canon ce1a90c046d2e9566a86d8dccf25df0e2bc98c80
python3 -m venv /tmp/claude-0/venv && /tmp/claude-0/venv/bin/python -m pip install -r lifecycle-checkpoint/venv-requirements.txt
cd /tmp/claude-0/lc-driver-canon && /tmp/claude-0/venv/bin/python -m scripts.dev_workflow.lifecycle verify /home/user/uri-wt/lifecycle-runs/W1-A0-closure.json
```

Then resume with `lifecycle run <config>`: the driver re-pins the candidate, re-checks the control-state anchor and
resumes at the checkpointed stage. A new container has a different reviewer CLI path/version or git config, so the
driver may stop with TAMPER (GIT_CONTROL): that stop is correct and is recorded; it is cleared only with an
`unblock --note` that states the container reset and what was inspected — never silently.

Interrupted review/repair rounds are not trusted: the driver discards partial worker output and re-runs the round.
