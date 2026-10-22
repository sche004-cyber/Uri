D=/c/Users/cheta/AppData/Local/Temp/mmfb_wfnr98go
cd $D/src
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. TEMP=$(cygpath -w $D) TMP=$(cygpath -w $D)
H=$D/ex/home_cli; rm -rf $H
mm(){ python -m scripts.dev_workflow.milestones --home $H --actor tester "$@"; echo "  -> exit $?"; }
mm init --host-id hosta
mm milestone-add M-ONE --title "first"
echo "### refusals expected"
mm milestone-update M-ONE --objective "password=hunter2"
mm milestone-update M-ONE --objective 'password: ${PASSWORD} hunter2'
mm milestone-update M-ONE --next-action 'token=abc'
mm milestone-update M-ONE --worktree 'D:/x?password=abc'
mm status-set M-ONE PAUSED --reason 'api_key: $uperS3cret!'
mm blocker-add M-ONE --kind other --reason "pwd=abc,defghi9" --needs x
mm handoff M-ONE --summary "secret: /s3cret99"
mm decision-add --title t --decision "passphrase = correct horse" --date 2026-10-22 --evidence-class OWNER_STATED --source chat
mm reanchor --reason "password=abc"
mm recover --reason "password=abc"
mm --actor 'password=abc' milestone-update M-ONE --objective ok
mm --session 'token=abcd' milestone-update M-ONE --objective ok
echo "### bypass candidates"
mm milestone-update M-ONE --objective "DB_PASSWORD=hunter2bypass1"
mm milestone-update M-ONE --next-action '{"password": "hunter2bypass2"}'
mm handoff M-ONE --summary "github_token=abcdefbypass3 and myPassword=bypass4"
mm milestone-update M-ONE --objective "password=HUNTER_BYPASS_FIVE"
echo "### false positive candidates"
mm milestone-update M-ONE --objective "Brain at token: 128k context"
mm milestone-update M-ONE --objective "token = see docs/x.md"
mm milestone-update M-ONE --objective "set OPENAI_API_KEY; ctx 65536; path D:/secrets/readme"
echo "### grep segment"
for s in hunter2 abc,defghi9 uperS3cret s3cret99 "correct horse" bypass1 bypass2 bypass3 bypass4 BYPASS_FIVE; do printf "%-15s " "$s"; grep -rl -- "$s" $H/events 2>/dev/null | wc -l; done
