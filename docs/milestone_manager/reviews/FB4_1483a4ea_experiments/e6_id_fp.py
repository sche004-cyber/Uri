"""FB4 e6: refusal-direction false positives when a milestone id with a credential word is followed by ':' or '='."""
import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import model as M
texts = ["handoff for PASSWORD-RESET: password rotation design done", "PASSWORD-RESET: done",
 "PASSWORD-RESET: tests pass, ready for review", "Blocked: TOKEN-REFRESH: waiting on owner",
 "OAUTH-TOKEN: implemented refresh flow", "Next: SECRET-STORE: add keyring backend",
 "MM-PASSWORD-RESET: 12 tests added", "PASSWORD-RESET depends on TOKEN-REFRESH", "status of PASSWORD-RESET = IN_PROGRESS",
 "Milestone PASSWORD-RESET (in progress)", "- PASSWORD-RESET: ACCEPTED", "| PASSWORD-RESET | ACCEPTED |",
 "| PASSWORD-RESET | in review |", "API-KEY-ROTATION: done", "Token: see DEC-012",
 "Secret refusal: implemented for every write path", "Password reset: email flow designed",
 "token budget: 65536", "Session token: rotated hourly", "Secrets: kept in keyring"]
for t in texts:
    print(("REFUSED " if M.find_secret(t) else "ok      ") + t)
