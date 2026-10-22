D=/c/Users/cheta/AppData/Local/Temp/mmfb_wfnr98go
cd $D/src
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. TEMP=$(cygpath -w $D) TMP=$(cygpath -w $D)
H=$D/ex/home_cli
mm(){ python -m scripts.dev_workflow.milestones --home $H --actor tester "$@" | tr -d '\n' | cut -c1-140; echo "  -> exit ${PIPESTATUS[0]}"; }
mm blocker-add M-ONE --kind OTHER --reason "pwd=abc,defghi9" --needs x
mm decision-add --title t --decision "passphrase = correct horse" --date 2026-10-22 --evidence-class OTHER --source chat
mm evidence-add M-ONE --kind log --ref x.log --result COMPLETED_WITH_RESULT --summary "token: abcdef" --no-hash
mm review-add M-ONE --commit $(printf 'a%.0s' {1..40}) --reviewer-kind subagent --reviewer-id r --assurance SUBAGENT --verdict ACCEPT --blocking-open 0 --findings-total 0 --result COMPLETED_WITH_RESULT --summary "secret=abc"
mm approval-request M-ONE --kind OTHER --question "password=abc"
mm resolve-conflict M-ONE --note "password=abc"
mm integration-record M-ONE --target-ref "refs/heads/x?token=abc" --target-commit $(printf 'b%.0s' {1..40})
mm assign M-ONE --worktree "password=abc"
mm release M-ONE --reason "password=abc"
mm implementer-add M-ONE "password=abc"
mm dep-remove M-ONE M-TWO --reason "password=abc"
